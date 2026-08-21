"""
Live HRV processing engine for dashboard backends.

Scientific caution:
- HRV-derived scores are experimental state estimates, not diagnostic outputs.
- LF/HF is exposed only as one input to an "Autonomic Balance Index"; it must
  not be interpreted as a direct sympathetic marker.
- respirationProxyHz is inferred from RR interval dynamics; it is not measured
  respiration.
- Stress Score and Recovery Score are research-prototype composite indices.

This module intentionally contains no plotting or UI code. The return value of
HRVProcessingEngine.add_rr_interval() is JSON-safe and can be streamed via a
WebSocket, FastAPI endpoint, message queue, or another bridge.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import time
from collections import deque
from dataclasses import dataclass, field
from typing import Any, Deque, Dict, Iterable, List, Optional, Tuple

import numpy as np
from scipy import signal


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------


@dataclass
class HRVConfig:
    rr_min_ms: float = 300.0
    rr_max_ms: float = 2000.0
    time_window_sec: float = 60.0
    heart_rate_window_sec: float = 10.0
    short_time_window_sec: float = 30.0
    baevsky_window_sec: float = 30.0
    psd_window_sec: float = 300.0
    psd_min_duration_sec: float = 30.0
    psd_max_trend_ms_per_sec: float = 1.2
    psd_full_quality_trend_ms_per_sec: float = 0.25
    interp_fs: float = 4.0
    lf_band: Tuple[float, float] = (0.04, 0.15)
    hf_band: Tuple[float, float] = (0.15, 0.40)
    resp_search_band: Tuple[float, float] = (0.06, 0.50)
    # Diagnostic guard band and validity checks prevent numerical PSD residue
    # and edge leakage from becoming plausible-looking respiration estimates.
    resp_diagnostic_band: Tuple[float, float] = (0.02, 0.70)
    resp_bw: float = 0.05
    psd_min_rr_variability_ms: float = 1.0
    resp_nyquist_safety_fraction: float = 0.80
    resp_min_peak_to_background: float = 3.0
    baseline_min_sec: float = 120.0
    baseline_max_sec: float = 300.0
    max_buffer_sec: float = 900.0
    recent_artifact_window_sec: float = 60.0
    recent_median_beats: int = 25
    artifact_mad_multiplier: float = 6.0
    artifact_min_jump_ms: float = 260.0
    artifact_relative_jump: float = 0.35
    nn_local_window_beats: int = 11
    nn_max_relative_deviation: float = 0.24
    nn_min_abs_deviation_ms: float = 120.0
    nn_max_abs_deviation_ms: float = 240.0
    nn_max_successive_change_ratio: float = 0.30
    rmssd_window_sec: float = 30.0
    rmssd_max_diff_ms: float = 90.0
    rmssd_max_diff_ratio: float = 0.14
    rmssd_min_pairs: int = 8
    stress_ema_alpha: float = 0.25


# ---------------------------------------------------------------------------
# JSON-safe helpers and pure functions
# ---------------------------------------------------------------------------


def is_finite(value: Any) -> bool:
    try:
        return bool(np.isfinite(value))
    except Exception:
        return False


def clamp(value: float, low: float, high: float) -> float:
    return float(min(high, max(low, value)))


def clamp01(value: float) -> float:
    return clamp(value, 0.0, 1.0)


def sigmoid(value: float) -> float:
    value = clamp(float(value), -60.0, 60.0)
    return 1.0 / (1.0 + math.exp(-value))


def to_json_safe(value: Any) -> Any:
    if isinstance(value, dict):
        return {k: to_json_safe(v) for k, v in value.items()}
    if isinstance(value, list):
        return [to_json_safe(v) for v in value]
    if isinstance(value, tuple):
        return [to_json_safe(v) for v in value]
    if isinstance(value, np.generic):
        value = value.item()
    if isinstance(value, float):
        return value if math.isfinite(value) else None
    return value


def finite_array(values: Iterable[float]) -> np.ndarray:
    arr = np.asarray(list(values), dtype=float)
    return arr[np.isfinite(arr)]


def rmssd(rr_ms: Iterable[float]) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < 3:
        return None
    return float(np.sqrt(np.mean(np.diff(rr) ** 2)))


def live_rmssd(rr_ms: Iterable[float], config: HRVConfig) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < config.rmssd_min_pairs + 1:
        return None
    diffs: List[float] = []
    for left, right in zip(rr[:-1], rr[1:]):
        local_level = max(1.0, (float(left) + float(right)) / 2.0)
        diff = abs(float(right) - float(left))
        max_diff = min(config.rmssd_max_diff_ms, local_level * config.rmssd_max_diff_ratio)
        if diff <= max_diff:
            diffs.append(diff)
    if len(diffs) < config.rmssd_min_pairs:
        return None
    arr = np.asarray(diffs, dtype=float)
    return float(np.sqrt(np.mean(arr ** 2)))


def live_pnn50(rr_ms: Iterable[float], config: HRVConfig) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < config.rmssd_min_pairs + 1:
        return None
    valid_diffs: List[float] = []
    for left, right in zip(rr[:-1], rr[1:]):
        local_level = max(1.0, (float(left) + float(right)) / 2.0)
        diff = abs(float(right) - float(left))
        max_diff = min(config.rmssd_max_diff_ms, local_level * config.rmssd_max_diff_ratio)
        if diff <= max_diff:
            valid_diffs.append(diff)
    if len(valid_diffs) < config.rmssd_min_pairs:
        return None
    return float(np.mean(np.asarray(valid_diffs, dtype=float) > 50.0) * 100.0)


def sdnn(rr_ms: Iterable[float]) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < 2:
        return None
    return float(np.std(rr, ddof=1))


def detrended_sdnn(rr_ms: Iterable[float]) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < 8:
        return sdnn(rr)
    x = np.arange(rr.size, dtype=float)
    slope, intercept = np.polyfit(x, rr, 1)
    residual = rr - ((slope * x) + intercept)
    return float(np.std(residual, ddof=1))


def pnn50(rr_ms: Iterable[float]) -> Optional[float]:
    rr = finite_array(rr_ms)
    if rr.size < 3:
        return None
    return float(np.mean(np.abs(np.diff(rr)) > 50.0) * 100.0)


def clean_nn_mask(rr_ms: Iterable[float], config: HRVConfig) -> np.ndarray:
    """Return a conservative NN mask for HRV metrics.

    Live single-lead ECG can produce missed or extra R-peaks during motion. Those
    errors appear as abrupt short-long RR pairs and inflate RMSSD, pNN50, SDNN,
    and HF power. This mask keeps gradual heart-rate changes but rejects local
    beat-to-beat discontinuities that are implausible for sinus rhythm.
    """

    rr = np.asarray(list(rr_ms), dtype=float)
    mask = np.isfinite(rr) & (rr >= config.rr_min_ms) & (rr <= config.rr_max_ms)
    if rr.size < 5:
        return mask

    half = max(2, int(config.nn_local_window_beats) // 2)
    for i, value in enumerate(rr):
        if not mask[i]:
            continue
        lo = max(0, i - half)
        hi = min(rr.size, i + half + 1)
        local = rr[lo:hi]
        local_mask = mask[lo:hi].copy()
        local_mask[i - lo] = False
        local = local[local_mask]
        if local.size < 4:
            local = rr[mask]
        if local.size < 4:
            continue
        median = float(np.median(local))
        allowed = max(
            config.nn_min_abs_deviation_ms,
            min(config.nn_max_abs_deviation_ms, median * config.nn_max_relative_deviation),
        )
        if abs(float(value) - median) > allowed:
            mask[i] = False

    # Pair-wise quotient filter. If two adjacent intervals jump too much, reject
    # the one farther from the local median. This targets false/missed R-peaks.
    for _ in range(2):
        accepted_idx = np.flatnonzero(mask)
        if accepted_idx.size < 4:
            break
        rr_acc = rr[accepted_idx]
        med_all = float(np.median(rr_acc))
        max_ratio = 1.0 + config.nn_max_successive_change_ratio
        min_ratio = 1.0 / max_ratio
        changed = False
        for left_pos, right_pos in zip(accepted_idx[:-1], accepted_idx[1:]):
            left = float(rr[left_pos])
            right = float(rr[right_pos])
            if left <= 0 or right <= 0:
                continue
            ratio = right / left
            if min_ratio <= ratio <= max_ratio:
                continue
            reject_pos = left_pos if abs(left - med_all) > abs(right - med_all) else right_pos
            mask[reject_pos] = False
            changed = True
        if not changed:
            break

    return mask


def clean_nn(rr_ms: Iterable[float], config: HRVConfig) -> np.ndarray:
    rr = np.asarray(list(rr_ms), dtype=float)
    if rr.size == 0:
        return rr
    return rr[clean_nn_mask(rr, config)]


def trend_abs_ms_per_sec(times_sec: Iterable[float], rr_ms: Iterable[float]) -> Optional[float]:
    times = finite_array(times_sec)
    rr = finite_array(rr_ms)
    if times.size != rr.size or rr.size < 8:
        return None
    duration = float(times[-1] - times[0])
    if duration <= 0:
        return None
    slope, _ = np.polyfit(times, rr, 1)
    return abs(float(slope))


def stationarity_score(trend_ms_per_sec: Optional[float], config: HRVConfig) -> float:
    if trend_ms_per_sec is None:
        return 1.0
    if trend_ms_per_sec <= config.psd_full_quality_trend_ms_per_sec:
        return 1.0
    if trend_ms_per_sec >= config.psd_max_trend_ms_per_sec:
        return 0.0
    span = config.psd_max_trend_ms_per_sec - config.psd_full_quality_trend_ms_per_sec
    return clamp01(1.0 - ((trend_ms_per_sec - config.psd_full_quality_trend_ms_per_sec) / span))


def baevsky_si(rr_ms: Iterable[float], bin_ms: float = 50.0) -> Optional[float]:
    """Baevsky Stress Index over RR intervals in milliseconds.

    SI = AMo / (2 * Mo * MxDMn)
    Mo and MxDMn are kept in milliseconds here, so SI is a relative live index,
    not an absolute clinical diagnostic measurement.
    """

    rr = finite_array(rr_ms)
    if rr.size < 5:
        return None
    mxdmn = float(np.max(rr) - np.min(rr))
    if mxdmn <= 0:
        return None
    low = math.floor(float(np.min(rr)) / bin_ms) * bin_ms
    high = math.ceil(float(np.max(rr)) / bin_ms) * bin_ms + bin_ms
    bins = np.arange(low, high + bin_ms, bin_ms)
    hist, edges = np.histogram(rr, bins=bins)
    if hist.size == 0 or int(np.max(hist)) == 0:
        return None
    idx = int(np.argmax(hist))
    mo = float((edges[idx] + edges[idx + 1]) / 2.0)
    amo = float(hist[idx] / rr.size * 100.0)
    if mo <= 0:
        return None
    return float(amo / (2.0 * mo * mxdmn))


def band_power(freqs: np.ndarray, power: np.ndarray, fmin: float, fmax: float) -> Optional[float]:
    mask = (freqs >= fmin) & (freqs <= fmax)
    if not np.any(mask):
        return None
    trapezoid = getattr(np, "trapezoid", None)
    if trapezoid is None:
        trapezoid = getattr(np, "trapz")
    return float(trapezoid(power[mask], x=freqs[mask]))


def robust_stats(values: Iterable[float]) -> Optional[Dict[str, float]]:
    arr = finite_array(values)
    if arr.size < 5:
        return None
    median = float(np.median(arr))
    mad = float(np.median(np.abs(arr - median)))
    std = float(np.std(arr, ddof=1)) if arr.size > 1 else 0.0
    return {"median": median, "mad": mad, "std": std, "n": int(arr.size)}


def robust_z(value: Optional[float], median: Optional[float], mad: Optional[float], std: Optional[float] = None) -> Optional[float]:
    if value is None or median is None or not is_finite(value) or not is_finite(median):
        return None
    if mad is not None and is_finite(mad) and mad > 0:
        return float((value - median) / (1.4826 * mad))
    if std is not None and is_finite(std) and std > 0:
        return float((value - median) / std)
    return None


def weighted_stress_score(
    directional_components: Dict[str, Optional[float]],
    weights: Dict[str, float],
    freq_keys: Iterable[str],
    psd_readiness: float,
    respiration_proxy_hz: Optional[float],
    respiration_proxy_confidence: Optional[float],
) -> Optional[float]:
    adjusted: Dict[str, Tuple[float, float]] = {}
    freq_multiplier = 0.2 + 0.8 * clamp01(psd_readiness)

    slow_breathing_multiplier = 1.0
    if respiration_proxy_hz is not None and respiration_proxy_confidence is not None and respiration_proxy_confidence >= 0.50:
        slow_likelihood = sigmoid((0.15 - respiration_proxy_hz) * 35.0)
        slow_breathing_multiplier = 1.0 - 0.65 * slow_likelihood

    freq_key_set = set(freq_keys)
    for key, component in directional_components.items():
        if component is None or not is_finite(component):
            continue
        weight = weights.get(key, 0.0)
        if key in freq_key_set:
            weight *= freq_multiplier * slow_breathing_multiplier
        if weight > 0:
            adjusted[key] = (float(component), float(weight))

    if len(adjusted) < 2:
        return None

    total_weight = sum(weight for _, weight in adjusted.values())
    if total_weight <= 0:
        return None
    stress_z = sum(component * weight for component, weight in adjusted.values()) / total_weight
    stress_z = clamp(stress_z, -3.0, 3.0)
    return float(100.0 * sigmoid(stress_z))


def recovery_completion(peak: float, current: float, baseline: float) -> float:
    if peak <= baseline:
        return 0.0
    return clamp(100.0 * (peak - current) / (peak - baseline), 0.0, 100.0)


# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class RRRecord:
    rr_ms: float
    timestamp: float
    elapsed_sec: float


@dataclass
class ArtifactRecord:
    elapsed_sec: float
    accepted: bool


@dataclass
class BaselineStats:
    values: Dict[str, List[float]] = field(default_factory=dict)
    stats: Dict[str, Dict[str, float]] = field(default_factory=dict)
    initialized: bool = False

    def add(self, features: Dict[str, Optional[float]]) -> None:
        for key, value in features.items():
            if value is not None and is_finite(value):
                self.values.setdefault(key, []).append(float(value))

    def recompute(self) -> None:
        self.stats = {}
        for key, values in self.values.items():
            stat = robust_stats(values)
            if stat is not None:
                self.stats[key] = stat

    def z(self, key: str, value: Optional[float]) -> Optional[float]:
        stat = self.stats.get(key)
        if stat is None:
            return None
        return robust_z(value, stat.get("median"), stat.get("mad"), stat.get("std"))

    def median(self, key: str) -> Optional[float]:
        stat = self.stats.get(key)
        return None if stat is None else stat.get("median")


@dataclass
class StressEvent:
    id: int
    start_sec: float
    baseline_stress_score: float
    peak_sec: Optional[float]
    end_sec: Optional[float]
    peak_stress_score: float
    current_stress_score: float
    recovery_reached_sec: Optional[float] = None
    recovered_stress_score: Optional[float] = None
    status: str = "Recovering"
    recovery_started: bool = False
    low_since_sec: Optional[float] = None
    unstable: bool = False

    def to_dict(self) -> Dict[str, Any]:
        if self.peak_sec is None:
            recovery_slope = None
            time_to_recovery = None
        elif self.recovery_reached_sec is not None and self.recovered_stress_score is not None:
            time_to_recovery = max(0.0, self.recovery_reached_sec - self.peak_sec)
            recovery_slope = None if time_to_recovery <= 0 else (self.peak_stress_score - self.recovered_stress_score) / time_to_recovery
        else:
            seconds_since_peak = max(0.0, self.current_elapsed_for_slope - self.peak_sec) if hasattr(self, "current_elapsed_for_slope") else None
            time_to_recovery = None
            recovery_slope = None
            if seconds_since_peak is not None and seconds_since_peak > 0:
                recovery_slope = (self.peak_stress_score - self.current_stress_score) / seconds_since_peak

        completion = recovery_completion(self.peak_stress_score, self.current_stress_score, self.baseline_stress_score)
        return {
            "id": self.id,
            "startSec": self.start_sec,
            "peakSec": self.peak_sec,
            "endSec": self.end_sec,
            "baselineStressScore": self.baseline_stress_score,
            "peakStressScore": self.peak_stress_score,
            "currentStressScore": self.current_stress_score,
            "timeToRecoverySec": time_to_recovery,
            "recoveryCompletion": completion,
            "recoverySlope": recovery_slope,
            "status": self.status,
        }


# ---------------------------------------------------------------------------
# Buffers and artifact handling
# ---------------------------------------------------------------------------


class ArtifactDetector:
    def __init__(self, config: HRVConfig):
        self.config = config

    def should_accept(self, rr_ms: float, recent_accepted_rr: Iterable[float]) -> Tuple[bool, str]:
        if not is_finite(rr_ms):
            return False, "non_finite"
        if rr_ms < self.config.rr_min_ms:
            return False, "below_min"
        if rr_ms > self.config.rr_max_ms:
            return False, "above_max"

        recent = finite_array(recent_accepted_rr)
        if recent.size < 8:
            return True, "accepted"
        median = float(np.median(recent))
        mad = float(np.median(np.abs(recent - median)))
        mad_limit = self.config.artifact_mad_multiplier * mad if mad > 0 and is_finite(mad) else self.config.artifact_min_jump_ms
        threshold = max(
            140.0,
            min(
                self.config.artifact_min_jump_ms,
                median * self.config.artifact_relative_jump,
                mad_limit,
            ),
        )
        if abs(rr_ms - median) > threshold:
            return False, "median_mad_outlier"
        last_rr = float(recent[-1])
        if last_rr > 0:
            ratio = rr_ms / last_rr
            max_ratio = 1.0 + self.config.nn_max_successive_change_ratio
            if ratio > max_ratio or ratio < (1.0 / max_ratio):
                return False, "successive_rr_jump"
        return True, "accepted"


class RRStreamBuffer:
    def __init__(self, config: HRVConfig):
        self.config = config
        self.artifacts = ArtifactDetector(config)
        self.accepted: Deque[RRRecord] = deque()
        self.raw_quality: Deque[ArtifactRecord] = deque()
        self.recent_raw_rr: Deque[float] = deque(maxlen=12)
        self.raw_count = 0
        self.valid_count = 0
        self.rejected_count = 0
        self.last_rejection_reason: Optional[str] = None
        self.consecutive_rejections = 0
        self.elapsed_sec = 0.0
        self.start_timestamp: Optional[float] = None
        self.last_valid_elapsed_sec: Optional[float] = None

    def add(self, rr_ms: float, timestamp: Optional[float] = None) -> Tuple[bool, str]:
        self.raw_count += 1
        rr_value = float(rr_ms)
        if is_finite(rr_value):
            self.recent_raw_rr.append(rr_value)
        if timestamp is None:
            if is_finite(rr_ms) and rr_ms > 0:
                self.elapsed_sec += float(rr_ms) / 1000.0
            timestamp = self.elapsed_sec
        else:
            if self.start_timestamp is None:
                self.start_timestamp = float(timestamp)
            self.elapsed_sec = max(0.0, float(timestamp) - self.start_timestamp)

        recent_rr = [record.rr_ms for record in list(self.accepted)[-self.config.recent_median_beats :]]
        accepted, reason = self.artifacts.should_accept(float(rr_ms), recent_rr)
        if not accepted and self._should_resync_from_raw_rr(float(rr_ms)):
            accepted = True
            reason = "accepted_resync"
        self.raw_quality.append(ArtifactRecord(self.elapsed_sec, accepted))
        if accepted:
            self.valid_count += 1
            self.consecutive_rejections = 0
            self.last_rejection_reason = None
            self.last_valid_elapsed_sec = self.elapsed_sec
            self.accepted.append(RRRecord(float(rr_ms), float(timestamp), self.elapsed_sec))
        else:
            self.rejected_count += 1
            self.consecutive_rejections += 1
            self.last_rejection_reason = reason

        self._trim()
        return accepted, reason

    def _should_resync_from_raw_rr(self, rr_ms: float) -> bool:
        if self.consecutive_rejections < 10:
            return False
        raw = finite_array(self.recent_raw_rr)
        if raw.size < 8:
            return False
        if np.any(raw < self.config.rr_min_ms) or np.any(raw > self.config.rr_max_ms):
            return False
        median = float(np.median(raw))
        mad = float(np.median(np.abs(raw - median)))
        max_deviation = float(np.max(np.abs(raw - median)))
        if median <= 0:
            return False
        stable_enough = max_deviation <= max(140.0, median * 0.22)
        not_erratic = mad <= max(45.0, median * 0.08)
        current_plausible = abs(rr_ms - median) <= max(140.0, median * 0.22)
        return stable_enough and not_erratic and current_plausible

    def _trim(self) -> None:
        min_elapsed = self.elapsed_sec - self.config.max_buffer_sec
        while self.accepted and self.accepted[0].elapsed_sec < min_elapsed:
            self.accepted.popleft()
        quality_min = self.elapsed_sec - max(self.config.max_buffer_sec, self.config.recent_artifact_window_sec)
        while self.raw_quality and self.raw_quality[0].elapsed_sec < quality_min:
            self.raw_quality.popleft()

    def recent_records(self, seconds: float) -> List[RRRecord]:
        cutoff = self.elapsed_sec - seconds
        return [record for record in self.accepted if record.elapsed_sec >= cutoff]

    def recent_rr(self, seconds: float) -> np.ndarray:
        return finite_array(record.rr_ms for record in self.recent_records(seconds))

    def recent_artifact_ratio(self, seconds: Optional[float] = None) -> float:
        seconds = self.config.recent_artifact_window_sec if seconds is None else seconds
        cutoff = self.elapsed_sec - seconds
        records = [record for record in self.raw_quality if record.elapsed_sec >= cutoff]
        if not records:
            return 0.0
        rejected = sum(1 for record in records if not record.accepted)
        return float(rejected / len(records))

    def seconds_since_last_valid(self) -> Optional[float]:
        if self.last_valid_elapsed_sec is None:
            return None
        return max(0.0, self.elapsed_sec - self.last_valid_elapsed_sec)


# ---------------------------------------------------------------------------
# Metrics and frequency analysis
# ---------------------------------------------------------------------------


class HRVMetricsCalculator:
    def __init__(self, config: HRVConfig):
        self.config = config

    def calculate(self, buffer: RRStreamBuffer) -> Dict[str, Optional[float]]:
        heart_rate_rr_raw = buffer.recent_rr(self.config.heart_rate_window_sec)
        rr_raw = buffer.recent_rr(self.config.time_window_sec)
        rmssd_rr_raw = buffer.recent_rr(self.config.rmssd_window_sec)
        baevsky_rr_raw = buffer.recent_rr(self.config.baevsky_window_sec)
        heart_rate_rr = clean_nn(heart_rate_rr_raw, self.config)
        rr = clean_nn(rr_raw, self.config)
        rmssd_rr = clean_nn(rmssd_rr_raw, self.config)
        baevsky_rr = clean_nn(baevsky_rr_raw, self.config)
        heart_rate = None
        if heart_rate_rr.size >= 3:
            median_rr = float(np.median(heart_rate_rr))
            heart_rate = 60000.0 / median_rr if median_rr > 0 else None

        if rr.size < 5:
            return {
                "heartRate": heart_rate,
                "rmssd": None,
                "sdnn": None,
                "sdnnDetrended": None,
                "pnn50": None,
                "baevskySI": None,
            }

        return {
            "heartRate": heart_rate,
            "rmssd": live_rmssd(rmssd_rr, self.config),
            "sdnn": sdnn(rr),
            "sdnnDetrended": detrended_sdnn(rr),
            "pnn50": live_pnn50(rmssd_rr, self.config),
            "baevskySI": baevsky_si(baevsky_rr),
        }


class FrequencyDomainAnalyzer:
    def __init__(self, config: HRVConfig):
        self.config = config

    def analyze(self, buffer: RRStreamBuffer) -> Dict[str, Any]:
        records = buffer.recent_records(self.config.psd_window_sec)
        result = {
            "lfPower": None,
            "hfPower": None,
            "lfHfRatio": None,
            "psdReadiness": 0.0,
            "psdStationarity": 1.0,
            "freqs": None,
            "power": None,
            "psdWindowFilledSec": 0.0,
            "medianRrMs": None,
            "rrSpectralVariabilityMs": None,
            "freqResolutionHz": None,
        }
        if len(records) < 2:
            return result

        times_raw = np.asarray([record.elapsed_sec for record in records], dtype=float)
        rr_raw = np.asarray([record.rr_ms for record in records], dtype=float)
        nn_mask = clean_nn_mask(rr_raw, self.config)
        times = times_raw[nn_mask]
        rr = rr_raw[nn_mask]
        if rr.size < 2:
            return result
        duration = float(times[-1] - times[0])
        result["psdWindowFilledSec"] = max(0.0, duration)
        recent_records = buffer.recent_records(self.config.time_window_sec)
        recent_times = [record.elapsed_sec for record in recent_records]
        recent_rr = clean_nn([record.rr_ms for record in recent_records], self.config)
        if len(recent_times) == len(recent_records) and recent_rr.size == len(recent_records):
            trend = trend_abs_ms_per_sec(recent_times, recent_rr)
        else:
            trend = trend_abs_ms_per_sec(times[-min(len(times), 80) :], rr[-min(len(rr), 80) :])
        stationarity = stationarity_score(trend, self.config)
        result["psdStationarity"] = stationarity
        result["psdReadiness"] = clamp01(duration / self.config.psd_window_sec) * stationarity

        if duration < self.config.psd_min_duration_sec or rr.size < 20 or stationarity <= 0.0:
            return result

        t_even = np.arange(times[0], times[-1], 1.0 / self.config.interp_fs)
        if t_even.size < 60:
            return result
        rr_interp = np.interp(t_even, times, rr)
        rr_interp = signal.detrend(rr_interp, type="linear")
        spectral_variability = float(np.std(rr_interp))
        result["rrSpectralVariabilityMs"] = spectral_variability
        result["medianRrMs"] = float(np.median(rr))
        if spectral_variability < self.config.psd_min_rr_variability_ms:
            return result
        n = rr_interp.size
        nperseg = int(min(max(128, n // 4), 512))
        if nperseg >= n:
            nperseg = max(8, n // 2)
        noverlap = nperseg // 2
        freqs, power = signal.welch(
            rr_interp,
            fs=self.config.interp_fs,
            nperseg=nperseg,
            noverlap=noverlap,
            window="hamming",
            detrend=False,
        )
        if freqs.size > 1:
            result["freqResolutionHz"] = float(np.median(np.diff(freqs)))
        lf = band_power(freqs, power, *self.config.lf_band)
        hf = band_power(freqs, power, *self.config.hf_band)
        ratio = lf / hf if lf is not None and hf is not None and hf > 0 else None
        result.update({"lfPower": lf, "hfPower": hf, "lfHfRatio": ratio, "freqs": freqs, "power": power})
        return result


class RespirationProxyAnalyzer:
    def __init__(self, config: HRVConfig):
        self.config = config

    def analyze(
        self,
        freqs: Optional[np.ndarray],
        power: Optional[np.ndarray],
        median_rr_ms: Optional[float] = None,
        freq_resolution_hz: Optional[float] = None,
    ) -> Dict[str, Optional[float]]:
        if freqs is None or power is None:
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        broad_mask = (freqs >= self.config.resp_diagnostic_band[0]) & (freqs <= self.config.resp_diagnostic_band[1])
        if not np.any(broad_mask):
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}

        df = float(freq_resolution_hz) if freq_resolution_hz is not None and is_finite(freq_resolution_hz) and freq_resolution_hz > 0 else None
        if df is None and freqs.size > 1:
            df = float(np.median(np.diff(freqs)))
        df = 0.0 if df is None or not is_finite(df) else df

        lower, configured_upper = self.config.resp_search_band
        reliable_upper = configured_upper
        if median_rr_ms is not None and is_finite(median_rr_ms) and median_rr_ms > 0:
            beat_nyquist_hz = 0.5 / (float(median_rr_ms) / 1000.0)
            reliable_upper = min(configured_upper, beat_nyquist_hz * self.config.resp_nyquist_safety_fraction)
        upper_with_tolerance = reliable_upper + (0.5 * df)

        broad_freqs = freqs[broad_mask]
        broad_power = power[broad_mask]
        if broad_power.size < 5 or not np.any(np.isfinite(broad_power)):
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        broad_idx = int(np.nanargmax(broad_power))
        broad_peak_freq = float(broad_freqs[broad_idx])

        mask = (freqs >= lower) & (freqs <= upper_with_tolerance)
        if not np.any(mask):
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        search_freqs = freqs[mask]
        search_power = power[mask]
        if search_power.size < 5:
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        idx = int(np.argmax(search_power))
        peak_freq = float(search_freqs[idx])
        peak_power = float(search_power[idx])
        if broad_peak_freq < lower or broad_peak_freq > upper_with_tolerance:
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        if abs(peak_freq - broad_peak_freq) > max(1.1 * df, 1e-12):
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}

        median_power = float(np.median(broad_power))
        if median_power > 0 and peak_power / median_power < self.config.resp_min_peak_to_background:
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        if peak_power <= 0 or not is_finite(peak_power):
            return {"respirationProxyHz": None, "respirationProxyConfidence": None}
        if peak_power + median_power <= 0:
            confidence = None
        else:
            conf_raw = (peak_power - median_power) / (peak_power + median_power)
            confidence = clamp01((conf_raw + 1.0) / 2.0)
        return {"respirationProxyHz": peak_freq, "respirationProxyConfidence": confidence}


# ---------------------------------------------------------------------------
# Scores, events, labels
# ---------------------------------------------------------------------------


class StressScoreCalculator:
    def __init__(self, config: HRVConfig):
        self.config = config
        self.smoothed: Optional[float] = None

    def calculate(
        self,
        sample: Dict[str, Optional[float]],
        baseline: BaselineStats,
        psd_readiness: float,
    ) -> Optional[float]:
        if not baseline.initialized:
            return None

        ln_hf = math.log(sample["hfPower"] + 1e-9) if sample.get("hfPower") is not None and sample["hfPower"] > 0 else None
        ln_lfhf = math.log(sample["lfHfRatio"] + 1e-9) if sample.get("lfHfRatio") is not None and sample["lfHfRatio"] > 0 else None

        components = {
            "heartRate": baseline.z("heartRate", sample.get("heartRate")),
            "rmssdInverse": _neg(baseline.z("rmssd", sample.get("rmssd"))),
            "hfInverse": _neg(baseline.z("lnHfPower", ln_hf)),
            "autonomicBalance": baseline.z("lnLfHfRatio", ln_lfhf),
            "baevskySI": baseline.z("baevskySI", sample.get("baevskySI")),
        }
        weights = {
            "heartRate": 0.35,
            "rmssdInverse": 0.25,
            "hfInverse": 0.15,
            "autonomicBalance": 0.10,
            "baevskySI": 0.15,
        }
        raw = weighted_stress_score(
            components,
            weights,
            freq_keys=("hfInverse", "autonomicBalance"),
            psd_readiness=psd_readiness,
            respiration_proxy_hz=sample.get("respirationProxyHz"),
            respiration_proxy_confidence=sample.get("respirationProxyConfidence"),
        )
        if raw is None:
            return None
        if self.smoothed is None:
            self.smoothed = raw
        else:
            alpha = self.config.stress_ema_alpha
            self.smoothed = alpha * raw + (1.0 - alpha) * self.smoothed
        return float(self.smoothed)


def _neg(value: Optional[float]) -> Optional[float]:
    return None if value is None else -float(value)


class EventDetector:
    def __init__(self):
        self.events: List[StressEvent] = []
        self.next_id = 1
        self.stress_history: Deque[Tuple[float, float]] = deque(maxlen=600)

    def update(self, elapsed_sec: float, stress_score: Optional[float]) -> List[StressEvent]:
        if stress_score is None:
            return self.events[-5:]
        stress = float(stress_score)
        self.stress_history.append((elapsed_sec, stress))

        active = self.active_event()
        rising = self._slope(10.0) is not None and self._slope(10.0) > 0.15
        high_for_5 = self._above_for(65.0, 5.0, elapsed_sec)
        baseline_stress = self._recent_baseline_stress()

        if active is None and (high_for_5 or (stress >= baseline_stress + 20.0 and rising)):
            active = StressEvent(
                id=self.next_id,
                start_sec=elapsed_sec,
                baseline_stress_score=baseline_stress,
                peak_sec=elapsed_sec,
                end_sec=None,
                peak_stress_score=stress,
                current_stress_score=stress,
            )
            self.next_id += 1
            self.events.append(active)

        if active is not None:
            active.current_stress_score = stress
            active.current_elapsed_for_slope = elapsed_sec  # type: ignore[attr-defined]
            if stress > active.peak_stress_score:
                active.peak_stress_score = stress
                active.peak_sec = elapsed_sec
            slope = self._slope(10.0)
            if active.peak_sec is not None and stress <= active.peak_stress_score - 5.0 and slope is not None and slope < 0:
                active.recovery_started = True
            if active.recovery_started:
                active.status = "Recovering"
            if active.recovery_started and stress > 65.0:
                active.unstable = True
                active.status = "Unstable Recovery"
            if active.peak_sec is not None:
                seconds_since_peak = elapsed_sec - active.peak_sec
                completion = recovery_completion(active.peak_stress_score, stress, active.baseline_stress_score)
                if seconds_since_peak > 180.0 and (stress > 65.0 or completion < 40.0):
                    active.status = "Sustained Activation"
            recovery_threshold = max(45.0, active.baseline_stress_score + 10.0)
            if stress <= recovery_threshold:
                if active.low_since_sec is None:
                    active.low_since_sec = elapsed_sec
                elif elapsed_sec - active.low_since_sec >= 15.0:
                    active.status = "Recovered"
                    active.end_sec = elapsed_sec
                    active.recovery_reached_sec = elapsed_sec
                    active.recovered_stress_score = stress
            else:
                active.low_since_sec = None

        return self.events[-5:]

    def active_event(self) -> Optional[StressEvent]:
        for event in reversed(self.events):
            if event.end_sec is None:
                return event
        return None

    def _slope(self, window_sec: float) -> Optional[float]:
        if len(self.stress_history) < 2:
            return None
        end_t, end_v = self.stress_history[-1]
        candidates = [(t, v) for t, v in self.stress_history if end_t - t >= window_sec]
        if not candidates:
            return None
        start_t, start_v = candidates[-1]
        dt = end_t - start_t
        return None if dt <= 0 else (end_v - start_v) / dt

    def _above_for(self, threshold: float, duration_sec: float, now: float) -> bool:
        recent = [(t, v) for t, v in self.stress_history if now - t <= duration_sec]
        if not recent:
            return False
        return now - recent[0][0] >= duration_sec * 0.8 and all(v >= threshold for _, v in recent)

    def _recent_baseline_stress(self) -> float:
        if not self.stress_history:
            return 50.0
        vals = [v for _, v in list(self.stress_history)[-120:] if v < 65.0]
        return float(np.median(vals)) if vals else 50.0


class RecoveryScoreCalculator:
    def calculate(
        self,
        elapsed_sec: float,
        stress_score: Optional[float],
        rmssd_value: Optional[float],
        baseline: BaselineStats,
        active_or_last_event: Optional[StressEvent],
    ) -> Optional[float]:
        if not baseline.initialized or stress_score is None:
            return None

        baseline_rmssd = baseline.median("rmssd")
        rmssd_rebound = None
        if baseline_rmssd is not None and baseline_rmssd > 0 and rmssd_value is not None:
            rmssd_rebound = 100.0 * clamp01(rmssd_value / baseline_rmssd)

        if active_or_last_event is None:
            base = 100.0 - max(0.0, stress_score - 30.0)
            if rmssd_rebound is not None:
                return clamp(0.75 * base + 0.25 * rmssd_rebound, 0.0, 100.0)
            return clamp(base, 0.0, 100.0)

        event = active_or_last_event
        completion = recovery_completion(event.peak_stress_score, stress_score, event.baseline_stress_score)
        if event.peak_sec is None:
            seconds_since_peak = 0.0
        elif event.recovery_reached_sec is not None:
            seconds_since_peak = event.recovery_reached_sec - event.peak_sec
        else:
            seconds_since_peak = elapsed_sec - event.peak_sec
        speed = 100.0 * clamp01(1.0 - seconds_since_peak / 180.0)
        recent_stability = 100.0 if stress_score < 55.0 else clamp(100.0 - (stress_score - 55.0) * 3.0, 0.0, 100.0)

        parts = {"completion": (completion, 0.40), "speed": (speed, 0.30), "stability": (recent_stability, 0.20)}
        if rmssd_rebound is not None:
            parts["rmssdRebound"] = (rmssd_rebound, 0.10)
        total_w = sum(weight for _, weight in parts.values())
        return clamp(sum(value * weight for value, weight in parts.values()) / total_w, 0.0, 100.0)


class PhysiologicalStateLabeler:
    def label(
        self,
        signal_confidence: float,
        seconds_since_last_valid: Optional[float],
        baseline_initialized: bool,
        stress_score: Optional[float],
        recovery_score: Optional[float],
        active_event: Optional[StressEvent],
        stress_slope: Optional[float],
    ) -> str:
        if seconds_since_last_valid is not None and seconds_since_last_valid > 5.0:
            return "Signal Lost"
        if signal_confidence < 0.35:
            return "Low Confidence"
        if not baseline_initialized:
            return "Initializing"
        if active_event is not None and active_event.status == "Sustained Activation":
            return "Sustained Activation"
        if stress_score is not None and stress_score >= 65.0 and stress_slope is not None and stress_slope > 0:
            return "Reactive"
        if active_event is not None and active_event.recovery_started:
            return "Recovering"
        if stress_score is not None and recovery_score is not None and stress_score < 45.0 and recovery_score >= 70.0:
            return "Stabilized"
        return "Baseline"


# ---------------------------------------------------------------------------
# Main processing engine
# ---------------------------------------------------------------------------


class HRVProcessingEngine:
    def __init__(self, config: Optional[HRVConfig] = None):
        self.config = config or HRVConfig()
        self.buffer = RRStreamBuffer(self.config)
        self.metrics = HRVMetricsCalculator(self.config)
        self.frequency = FrequencyDomainAnalyzer(self.config)
        self.respiration = RespirationProxyAnalyzer(self.config)
        self.baseline = BaselineStats()
        self.stress = StressScoreCalculator(self.config)
        self.events = EventDetector()
        self.recovery = RecoveryScoreCalculator()
        self.labeler = PhysiologicalStateLabeler()

    def add_rr_interval(self, rr_ms: float, timestamp: Optional[float] = None) -> Dict[str, Any]:
        self.buffer.add(rr_ms, timestamp)
        elapsed = self.buffer.elapsed_sec

        time_metrics = self.metrics.calculate(self.buffer)
        freq = self.frequency.analyze(self.buffer)
        resp = self.respiration.analyze(
            freq["freqs"],
            freq["power"],
            median_rr_ms=freq.get("medianRrMs"),
            freq_resolution_hz=freq.get("freqResolutionHz"),
        )
        psd_readiness = float(freq["psdReadiness"])

        ln_hf = math.log(freq["hfPower"] + 1e-9) if freq["hfPower"] is not None and freq["hfPower"] > 0 else None
        ln_lfhf = math.log(freq["lfHfRatio"] + 1e-9) if freq["lfHfRatio"] is not None and freq["lfHfRatio"] > 0 else None
        baseline_features = {
            "heartRate": time_metrics["heartRate"],
            "rmssd": time_metrics["rmssd"],
            "sdnn": time_metrics["sdnn"],
            "sdnnDetrended": time_metrics["sdnnDetrended"],
            "baevskySI": time_metrics["baevskySI"],
            "lnHfPower": ln_hf,
            "lnLfHfRatio": ln_lfhf,
        }
        baseline_quality_ok = self.buffer.recent_artifact_ratio() <= 0.12 and len(self.buffer.recent_records(30.0)) >= 20
        if elapsed <= self.config.baseline_max_sec and baseline_quality_ok:
            self.baseline.add(baseline_features)
            self.baseline.recompute()
        if elapsed >= self.config.baseline_min_sec and len(self.baseline.stats) >= 2:
            self.baseline.initialized = True

        autonomic_balance = None
        z_balance = self.baseline.z("lnLfHfRatio", ln_lfhf)
        if z_balance is not None:
            autonomic_balance = 100.0 * sigmoid(clamp(z_balance, -3.0, 3.0))

        sample: Dict[str, Optional[float]] = {
            **time_metrics,
            "lfPower": freq["lfPower"],
            "hfPower": freq["hfPower"],
            "lfHfRatio": freq["lfHfRatio"],
            "autonomicBalanceIndex": autonomic_balance,
            "respirationProxyHz": resp["respirationProxyHz"],
            "respirationProxyConfidence": resp["respirationProxyConfidence"],
        }
        stress_score = self.stress.calculate({**sample, **resp}, self.baseline, psd_readiness)
        event_list = self.events.update(elapsed, stress_score)
        active = self.events.active_event()
        last_event = active or (self.events.events[-1] if self.events.events else None)
        recovery_score = self.recovery.calculate(elapsed, stress_score, time_metrics["rmssd"], self.baseline, last_event)

        signal_confidence = self._signal_confidence()
        signal_status = self._signal_status(signal_confidence)
        stress_slope = self.events._slope(10.0)
        state = self.labeler.label(
            signal_confidence,
            self.buffer.seconds_since_last_valid(),
            self.baseline.initialized,
            stress_score,
            recovery_score,
            active,
            stress_slope,
        )

        output = {
            "sample": {
                "timestamp": float(timestamp) if timestamp is not None else float(elapsed),
                "elapsedSec": float(elapsed),
                "rrMs": float(rr_ms),
                "heartRate": sample["heartRate"],
                "rmssd": sample["rmssd"],
                "sdnn": sample["sdnn"],
                "sdnnDetrended": sample["sdnnDetrended"],
                "pnn50": sample["pnn50"],
                "baevskySI": sample["baevskySI"],
                "lfPower": sample["lfPower"],
                "hfPower": sample["hfPower"],
                "lfHfRatio": sample["lfHfRatio"],
                "autonomicBalanceIndex": sample["autonomicBalanceIndex"],
                "respirationProxyHz": sample["respirationProxyHz"],
                "respirationProxyConfidence": sample["respirationProxyConfidence"],
                "psdReadiness": psd_readiness,
                "psdStationarity": freq["psdStationarity"],
                "artifactRatio": self.buffer.recent_artifact_ratio(),
                "signalConfidence": signal_confidence,
                "stressScore": stress_score,
                "recoveryScore": recovery_score,
                "physiologicalState": state,
            },
            "events": [event.to_dict() for event in event_list],
            "quality": {
                "nRawRR": self.buffer.raw_count,
                "nValidRR": self.buffer.valid_count,
                "nRejectedRR": self.buffer.rejected_count,
                "lastRejectionReason": self.buffer.last_rejection_reason,
                "artifactRatioRecent": self.buffer.recent_artifact_ratio(),
                "signalStatus": signal_status,
                "psdWindowFilledSec": freq["psdWindowFilledSec"],
                "psdReadiness": psd_readiness,
                "psdStationarity": freq["psdStationarity"],
            },
        }
        return to_json_safe(output)

    def _signal_confidence(self) -> float:
        artifact_ratio = self.buffer.recent_artifact_ratio()
        recent_valid = len(self.buffer.recent_records(self.config.time_window_sec))
        recent_rr = self.buffer.recent_rr(self.config.short_time_window_sec)
        mean_rr = float(np.mean(recent_rr)) if recent_rr.size else 800.0
        expected_beats = max(1.0, self.config.time_window_sec / max(0.3, mean_rr / 1000.0))
        rr_quality = 1.0 - artifact_ratio
        beat_density = clamp01(recent_valid / expected_beats)
        seconds_since_valid = self.buffer.seconds_since_last_valid()
        if seconds_since_valid is None:
            freshness = 0.0
        elif seconds_since_valid <= 3.0:
            freshness = 1.0
        elif seconds_since_valid >= 10.0:
            freshness = 0.0
        else:
            freshness = 1.0 - ((seconds_since_valid - 3.0) / 7.0)
        return clamp01(0.5 * rr_quality + 0.3 * beat_density + 0.2 * freshness)

    def _signal_status(self, signal_confidence: float) -> str:
        seconds_since_valid = self.buffer.seconds_since_last_valid()
        if signal_confidence < 0.35 or (seconds_since_valid is not None and seconds_since_valid > 5.0):
            return "Signal Lost"
        if signal_confidence >= 0.75:
            return "Active"
        if signal_confidence >= 0.50:
            return "Noisy"
        return "Low Confidence"


# ---------------------------------------------------------------------------
# Simulator
# ---------------------------------------------------------------------------


def simulate_rr_stream(duration_sec: Optional[float] = None, seed: int = 42) -> Iterable[Tuple[float, float]]:
    rng = random.Random(seed)
    elapsed = 0.0
    while duration_sec is None or elapsed < duration_sec:
        if elapsed < 180:
            base_rr, variability = 820.0, 35.0
        elif elapsed < 300:
            progress = (elapsed - 180.0) / 120.0
            base_rr, variability = 820.0 - 180.0 * progress, 18.0
        elif elapsed < 390:
            base_rr, variability = 620.0, 12.0
        else:
            progress = min(1.0, (elapsed - 390.0) / 180.0)
            base_rr, variability = 620.0 + 190.0 * progress, 25.0 + 10.0 * progress

        rr = rng.gauss(base_rr, variability)
        if rng.random() < 0.015:
            rr *= rng.choice([0.45, 1.75])
        if 470 <= elapsed <= 490 and rng.random() < 0.30:
            rr *= rng.choice([0.5, 1.6])

        elapsed += max(0.25, rr / 1000.0)
        yield rr, elapsed


def run_demo() -> None:
    engine = HRVProcessingEngine()
    next_print = 0.0
    latest = None
    for rr_ms, elapsed in simulate_rr_stream():
        latest = engine.add_rr_interval(rr_ms, timestamp=elapsed)
        if elapsed >= next_print and latest is not None:
            print(json.dumps(latest, indent=2))
            next_print += 1.0


def main() -> None:
    parser = argparse.ArgumentParser(description="Live HRV processing engine demo")
    parser.add_argument("--demo", action="store_true", help="Run an endless RR simulator and print JSON-ready states")
    args = parser.parse_args()
    if args.demo:
        run_demo()
    else:
        print("Instantiate HRVProcessingEngine and call add_rr_interval(rr_ms, timestamp=None). Use --demo to simulate.")


if __name__ == "__main__":
    main()


