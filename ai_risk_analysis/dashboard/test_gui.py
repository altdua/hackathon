"""Optional Tk smoke test; creates a withdrawn desktop window."""

from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

from . import app, core


class DesktopSmokeTest(unittest.TestCase):
    def test_setup_run_results_search_and_pending_stage(self):
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            def prepare(stage, source, config, parent=None):
                return core.prepare_run(stage, source, config, parent, runs_dir=directory / "runs")
            with patch.object(app, "prepare_run", side_effect=prepare), \
                 patch.object(app, "list_runs", side_effect=lambda: core.list_runs(directory / "runs")), \
                 patch.object(app, "SETTINGS", directory / "settings.json"), \
                 patch.object(app, "load_settings", side_effect=core.default_settings):
                window = app.Dashboard()
                window.withdraw()
                try:
                    window.update()
                    window.select_stage("risk_modelling")
                    self.assertEqual(str(window.run_button["state"]), "disabled")
                    window.select_stage("feature_engineering")
                    window.load_example()
                    window.run_selected()
                    deadline = time.monotonic() + 10
                    while window.process and time.monotonic() < deadline:
                        window.update()
                        time.sleep(0.03)
                    self.assertIsNone(window.process, "Worker did not finish")
                    self.assertEqual(window.viewed_run["status"], "completed")
                    self.assertEqual(len(window.records), 2)
                    window.search_var.set("synthetic-001")
                    window.update()
                    self.assertEqual(len(window.table.get_children()), 1)
                    self.assertIn("text_observations", window.detail.get("1.0", "end"))
                    window.artifact_var.set("features.csv")
                    window.show_artifact()
                    self.assertEqual(len(window.records), 2)
                    window.save_settings()
                    self.assertTrue((directory / "settings.json").exists())
                    self.assertEqual(len(window.history_items), 1)
                    window.select_stage("risk_modelling")
                    window.use_previous()
                    self.assertTrue(Path(window.input_var.get()).is_file())
                finally:
                    if window.process:
                        window.process.terminate()
                        window.process.wait(timeout=5)
                        window.log_handle.close()
                    window.destroy()


if __name__ == "__main__":
    unittest.main()
