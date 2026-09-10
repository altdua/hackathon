import json
from pathlib import Path
import unittest
from unittest.mock import patch, MagicMock

from .pipeline import build_features
from .text import DemoExtractor, OpenAIExtractor, unknown_observations, validate_observations


class FeatureTests(unittest.TestCase):
    def setUp(self):
        self.citizen = json.loads((Path(__file__).parent / "examples/citizens.json").read_text())[0]

    def build(self):
        return build_features(self.citizen, "2026-09-10", DemoExtractor())

    def test_combined_features(self):
        f = self.build()["features"]
        self.assertEqual(f["rent_arrears_amount"], 750)
        self.assertEqual(f["arrears_change_observed_90d"], 500)
        self.assertEqual(f["missed_appointments_90d"], 2)
        self.assertAlmostEqual(f["missed_appointment_rate_90d"], 2 / 3)
        self.assertEqual(f["text_social_isolation"], 1)
        self.assertIsNone(f["text_safeguarding_concern"])

    def test_missing_versus_empty(self):
        self.citizen["appointments"] = None
        self.assertIsNone(self.build()["features"]["missed_appointments_90d"])
        self.citizen["appointments"] = []
        f = self.build()["features"]
        self.assertEqual(f["missed_appointments_90d"], 0)
        self.assertIsNone(f["missed_appointment_rate_90d"])

    def test_future_and_late_received_records_excluded(self):
        self.citizen["housing"].append({"date": "2026-09-11", "recorded_at": "2026-09-11", "arrears_amount": 1000})
        self.citizen["notes"][0]["recorded_at"] = "2026-09-11"
        f = self.build()["features"]
        self.assertEqual(f["rent_arrears_amount"], 750)
        self.assertIsNone(f["text_social_isolation"])

    def test_window_boundary_and_cancelled_appointments(self):
        self.citizen["appointments"] = [
            {"appointment_id": "old", "date": "2026-06-12", "recorded_at": "2026-06-12", "status": "missed"},
            {"appointment_id": "new", "date": "2026-09-10", "recorded_at": "2026-09-10", "status": "cancelled"}]
        f = self.build()["features"]
        self.assertEqual(f["missed_appointments_90d"], 0)
        self.assertIsNone(f["missed_appointment_rate_90d"])

    def test_conflicting_text_is_not_zero(self):
        self.citizen["notes"].append({"note_id": "n3", "date": "2026-09-02", "recorded_at": "2026-09-02", "text": "DEMO social_isolation: absent."})
        f = self.build()["features"]
        self.assertIsNone(f["text_social_isolation"])
        self.assertEqual(f["text_social_isolation_conflicting"], 1)

    def test_duplicate_appointments_rejected(self):
        self.citizen["appointments"].append(self.citizen["appointments"][0])
        with self.assertRaises(ValueError):
            self.build()

    def test_invalid_numbers_rejected(self):
        for value in (-1, True, float("nan"), float("inf"), "750"):
            self.citizen["housing"][0]["arrears_amount"] = value
            with self.assertRaises(ValueError):
                self.build()

    def test_fabricated_evidence_rejected(self):
        result = unknown_observations()
        result["social_isolation"] = {"status": "present", "evidence": [{"note_id": "n1", "quote": "invented"}]}
        with self.assertRaises(ValueError):
            validate_observations(result, self.citizen["notes"])

    def test_no_notes_skips_provider(self):
        self.citizen["notes"] = []
        provider = MagicMock(name="provider")
        build_features(self.citizen, "2026-09-10", provider)
        provider.extract.assert_not_called()

    @patch.dict("os.environ", {"OPENAI_API_KEY": "synthetic-test-key"})
    @patch("feature_engineering.text.urlopen")
    def test_openai_adapter_with_mocked_response(self, send):
        response = MagicMock()
        response.read.return_value = json.dumps({"status": "completed", "output": [
            {"type": "message", "content": [{"type": "output_text", "text": json.dumps(unknown_observations())}]}]}).encode()
        send.return_value.__enter__.return_value = response
        result = OpenAIExtractor("test-model").extract(self.citizen["notes"])
        self.assertEqual(result, unknown_observations())
        payload = json.loads(send.call_args.args[0].data)
        self.assertFalse(payload["store"])
        self.assertTrue(payload["text"]["format"]["strict"])


if __name__ == "__main__":
    unittest.main()
