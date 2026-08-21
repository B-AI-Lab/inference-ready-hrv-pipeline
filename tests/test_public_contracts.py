import sys
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from hrv_ble_sse_bridge import parse_heart_rate_measurement
from hrv_live_processing_engine import HRVConfig, HRVProcessingEngine
from hrv_serial_sse_bridge import parse_rr_line


class PublicContractTests(unittest.TestCase):
    def test_serial_rr_line_contract(self):
        self.assertEqual(parse_rr_line("RR_MS,800,BPM,75,TS_MS,1234"), (800.0, 75.0, 1234.0))
        self.assertEqual(parse_rr_line("rr_ms=1000"), (1000.0, None, None))
        self.assertEqual(parse_rr_line("1000"), (1000.0, 60.0, None))

    def test_polar_rr_conversion_contract(self):
        bpm, rr_values = parse_heart_rate_measurement(bytes([0x10, 60, 0x00, 0x04]))
        self.assertEqual(bpm, 60.0)
        self.assertEqual(rr_values, [1000.0])

    def test_canonical_spectral_constants(self):
        config = HRVConfig()
        self.assertEqual(config.interp_fs, 4.0)
        self.assertEqual(config.lf_band, (0.04, 0.15))
        self.assertEqual(config.hf_band, (0.15, 0.40))
        self.assertEqual(config.resp_search_band, (0.06, 0.50))

    def test_engine_payload_shape(self):
        engine = HRVProcessingEngine()
        state = None
        for rr_ms in [800, 810, 790, 805, 815, 795, 802, 798, 806, 812, 799, 804]:
            state = engine.add_rr_interval(rr_ms)
        self.assertIsInstance(state, dict)
        self.assertIn("sample", state)
        self.assertIn("quality", state)
        self.assertEqual(state["sample"]["rrMs"], 804)
        self.assertIn("signalConfidence", state["sample"])


if __name__ == "__main__":
    unittest.main()
