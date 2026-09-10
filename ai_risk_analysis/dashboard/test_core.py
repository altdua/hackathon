import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from .core import ROOT, is_available, list_runs, prepare_run, safe_artifact
from .worker import execute


class RunnerTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.directory = Path(self.temp.name)
        self.input = ROOT / "feature_engineering/examples/citizens.json"
        self.config = {"as_of": "2026-09-10", "extractor": "demo", "model": ""}

    def tearDown(self):
        self.temp.cleanup()

    def prepare(self, **kwargs):
        return prepare_run("feature_engineering", self.input, self.config, runs_dir=self.directory, **kwargs)

    def test_worker_end_to_end(self):
        run = self.prepare()
        result = subprocess.run([sys.executable, "-m", "dashboard.worker", str(run)], cwd=ROOT, capture_output=True, text=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        state = json.loads((run / "status.json").read_text())
        self.assertEqual(state["status"], "completed")
        records = json.loads(Path(state["primary_artifact"]).read_text())
        self.assertEqual(len(records), 2)
        self.assertEqual(records[0]["features"]["rent_arrears_amount"], 750)
        self.assertTrue((run / "output/features.csv").is_file())
        self.assertEqual((run / "input.json").read_bytes(), self.input.read_bytes())

    def test_failed_run_is_persisted(self):
        self.config["as_of"] = "invalid"
        run = self.prepare()
        self.assertEqual(execute(run), 1)
        state = json.loads((run / "status.json").read_text())
        self.assertEqual(state["status"], "failed")
        self.assertIsNone(state["primary_artifact"])

    def test_pending_stage_cannot_run(self):
        with patch("dashboard.core.is_available", return_value=False):
            with self.assertRaises(ValueError):
                prepare_run("risk_modelling", self.input, {}, runs_dir=self.directory)

    def test_adapter_discovery(self):
        self.assertTrue(is_available("feature_engineering"))

    def test_artifact_cannot_escape_output(self):
        output = self.directory / "output"
        output.mkdir()
        (self.directory / "outside.json").write_text("{}")
        with self.assertRaises(ValueError):
            safe_artifact(output, "../outside.json")

    def test_unique_history_and_parent_link(self):
        first = self.prepare()
        second = self.prepare(parent_run=first.name)
        self.assertNotEqual(first, second)
        runs = list_runs(self.directory)
        self.assertEqual(len(runs), 2)
        self.assertEqual(runs[0]["parent_run"], first.name)

    def test_missing_input_does_not_create_run(self):
        with self.assertRaises(ValueError):
            prepare_run("feature_engineering", self.directory / "missing.json", self.config, runs_dir=self.directory)
        self.assertEqual(list_runs(self.directory), [])


if __name__ == "__main__":
    unittest.main()
