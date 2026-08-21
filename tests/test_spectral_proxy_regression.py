import math
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from hrv_live_processing_engine import HRVProcessingEngine


def replay_sinusoidal_rr(freq_hz: float, duration_sec: float = 330.0, base_rr_ms: float = 1000.0, amplitude_ms: float = 60.0):
    engine = HRVProcessingEngine()
    elapsed = 0.0
    latest = None
    while elapsed < duration_sec:
        rr_ms = base_rr_ms if freq_hz == 0.0 else base_rr_ms + amplitude_ms * math.sin(2.0 * math.pi * freq_hz * elapsed)
        elapsed += rr_ms / 1000.0
        latest = engine.add_rr_interval(rr_ms, timestamp=elapsed)
    assert latest is not None
    return latest["sample"]


class SpectralProxyRegressionTests(unittest.TestCase):
    def test_constant_rr_has_no_proxy_or_lf_hf_ratio(self):
        sample = replay_sinusoidal_rr(0.0)
        self.assertIsNone(sample["respirationProxyHz"])
        self.assertIsNone(sample["lfHfRatio"])

    def test_out_of_band_low_frequency_is_not_snapped_to_proxy_boundary(self):
        sample = replay_sinusoidal_rr(0.05)
        self.assertIsNone(sample["respirationProxyHz"])

    def test_out_of_band_high_frequency_alias_is_not_reported_as_proxy(self):
        sample = replay_sinusoidal_rr(0.55)
        self.assertIsNone(sample["respirationProxyHz"])

    def test_lower_boundary_is_not_snapped_when_resolution_is_ambiguous(self):
        sample = replay_sinusoidal_rr(0.06)
        self.assertIsNone(sample["respirationProxyHz"])

    def test_in_band_frequencies_are_detected(self):
        for freq_hz in (0.10, 0.15, 0.25, 0.40):
            with self.subTest(freq_hz=freq_hz):
                sample = replay_sinusoidal_rr(freq_hz)
                self.assertIsNotNone(sample["respirationProxyHz"])
                self.assertLessEqual(abs(sample["respirationProxyHz"] - freq_hz), 0.015)

    def test_upper_boundary_can_be_detected_when_rr_sampling_supports_it(self):
        sample = replay_sinusoidal_rr(0.50, base_rr_ms=800.0)
        self.assertIsNotNone(sample["respirationProxyHz"])
        self.assertLessEqual(abs(sample["respirationProxyHz"] - 0.50), 0.015)


if __name__ == "__main__":
    unittest.main()
