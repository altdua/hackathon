# AI Risk Analysis workspace

A local desktop GUI for setting up, running and inspecting the three analysis
stages. Feature Engineering is connected. Risk Modelling and Risk Output are
reserved for your future implementations and show as pending.

## Start the GUI

From this folder, use Python 3.10+ with Tk support:

```powershell
python main.py
```

No pip packages are required. On Windows, the standard Python installer includes
Tk when its Tcl/Tk option is selected. You can also use the supplied
`start_dashboard.bat`, which tries Python and then the bundled Codex runtime.

1. Select Feature Engineering in the left sidebar.
2. Click **Load synthetic example**, then **Run this agent**.
3. Inspect the live log. On completion, inspect **Results & evidence**.
4. Select an artifact, search records, and click a row for its full data and
   source evidence. Export a JSON or CSV file with **Export file**.
5. Use **Run history** to inspect earlier runs, including failed runs.

The demo is offline and recognises synthetic markers only. For ordinary notes,
select openai, enter a structured-output-capable model ID, and launch the app
with OPENAI_API_KEY set in its environment. The GUI does not store API keys.
LLM mode sends eligible notes to the API; use appropriately prepared data.

**Save settings** persists all stage settings to dashboard_settings.json.
Starting a run also saves settings. Unsaved edits are retained while switching
stages, but not after closing. Settings are ordinary local JSON: do not put
secrets in the future stages' JSON configuration fields.

## Folder layout

```text
ai_risk_analysis/
  main.py                    Desktop entry point
  start_dashboard.bat        Windows launcher
  dashboard/                 GUI, runner and persisted run handling
  feature_engineering/       Connected numerical and text extraction agent
  risk_modelling/            Future model implementation
  risk_output/               Future output implementation
  runs/                      Generated run history (ignored by Git)
  dashboard_settings.json    Saved local settings (ignored by Git)
```

Each run has a unique directory containing request.json, status.json, an input
snapshot, run.log and output/. Failed and cancelled runs are retained for
inspection; their partial artifacts are not offered as completed results.
Interrupted runs remain visible in history. Runs and snapshots can contain
sensitive data; local storage has no additional encryption or access control.

JSON, CSV and text artifacts have inline previews. Other file types can be
exported. Previews accept files up to 20 MB; tables display up to 500 matching
rows at once. Search operates over all loaded rows. The full artifact is always
available for export. No browser, web server or external hosting is required.

## Connect the next agents

Create `risk_modelling/agent.py` and later `risk_output/agent.py`. Each implements:

```python
from pathlib import Path
from typing import Callable

def run(input_path: Path, output_dir: Path, config: dict,
        log: Callable[[str], None]) -> dict:
    log("Loading input")
    # Read input_path and execute your actual model/output implementation.
    # Write results inside output_dir, for example risk_scores.json.
    # Raise an exception if the run cannot complete.
    return {"primary_artifact": "risk_scores.json"}
```

This is an interface example, not a runnable model. The returned artifact must
exist inside output_dir. Additional JSON-serialisable summary fields can be
returned. For convenient result tables, use a JSON list of citizen objects,
e.g. with citizen_id plus your actual output fields. Feature Engineering outputs
a list with citizen_id, as_of, features and audit. Adapt the model to that
contract. The GUI does not invent scores or impose your future model schema.

Click **Refresh stages** after adding an adapter. The GUI discovers files at
these fixed folder paths; it does not execute code during discovery. Each run
imports the agent in a fresh Python process, so code changes apply to the next
run without restarting the GUI. Stage code is trusted local project code, not
sandboxed code. Keep work in that worker process; agents should not launch
detached child processes if they need the Stop run button to cancel all work.

**Use latest previous result** picks the latest successful immediate upstream
artifact. You can also browse to a specific run's artifact. **Run connected
pipeline** starts at Feature Engineering and executes contiguous connected
stages in order, handing each primary artifact to the next stage and recording
the parent run ID. It stops at the first pending stage, failure or cancellation.
Each stage's saved configuration is used. One run is active at a time per app
window. Use one app window per project to avoid competing configuration edits.

## Checks

```powershell
python -m unittest feature_engineering.test_pipeline dashboard.test_core -v
```

The feature adapter and orchestration tests use synthetic data, temporary run
folders and no network calls. Live LLM output quality is not evaluated here.

With a desktop session available, run `python -m unittest dashboard.test_gui -v`
for an additional hidden-window check of setup, execution, evidence viewing,
search, saved settings and selection of the previous stage's result.
