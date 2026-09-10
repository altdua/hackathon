"""Shared stage discovery, settings and persisted run metadata."""

from datetime import datetime, timezone
import json
from pathlib import Path
import uuid

ROOT = Path(__file__).resolve().parents[1]
RUNS = ROOT / "runs"
SETTINGS = ROOT / "dashboard_settings.json"
STAGES = (
    {"id": "feature_engineering", "title": "Feature Engineering", "number": "01",
     "description": "Combine numerical indicators with documented facts from notes."},
    {"id": "risk_modelling", "title": "Risk Modelling", "number": "02",
     "description": "Turn engineered features into risk estimates using your future model."},
    {"id": "risk_output", "title": "Risk Output", "number": "03",
     "description": "Present risk estimates, explanations and analysis from your future output agent."},
)


def stage_info(stage_id):
    return next(s for s in STAGES if s["id"] == stage_id)


def is_available(stage_id):
    stage_info(stage_id)
    return (ROOT / stage_id / "agent.py").is_file()


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def default_settings():
    return {s["id"]: {"input": str(ROOT / "feature_engineering/examples/citizens.json") if i == 0 else "",
                       "config": {"as_of": "2026-09-10", "extractor": "demo", "model": ""} if i == 0 else {}}
            for i, s in enumerate(STAGES)}


def load_settings():
    defaults = default_settings()
    if not SETTINGS.exists():
        return defaults
    saved = json.loads(SETTINGS.read_text(encoding="utf-8"))
    if not isinstance(saved, dict):
        raise ValueError("Settings must be an object")
    for stage in defaults:
        if stage in saved:
            entry = saved[stage]
            if not isinstance(entry, dict) or not isinstance(entry.get("input"), str) or not isinstance(entry.get("config"), dict):
                raise ValueError("Invalid stage settings")
            defaults[stage] = entry
    return defaults


def prepare_run(stage_id, input_path, config, parent_run=None, runs_dir=RUNS):
    if not is_available(stage_id):
        raise ValueError(f"{stage_info(stage_id)['title']} is not connected yet")
    source = Path(input_path).expanduser().resolve()
    if not source.is_file():
        raise ValueError("Choose an existing input file")
    if not isinstance(config, dict):
        raise ValueError("Agent settings must be a JSON object")
    now = datetime.now(timezone.utc)
    run_id = now.strftime("%Y%m%d-%H%M%S") + "-" + uuid.uuid4().hex[:8]
    directory = Path(runs_dir) / run_id
    directory.mkdir(parents=True)
    request = {"id": run_id, "stage": stage_id, "input": str(source), "config": config,
               "created_at": now.isoformat(), "parent_run": parent_run}
    write_json(directory / "request.json", request)
    write_json(directory / "status.json", {**request, "status": "queued", "primary_artifact": None})
    return directory


def list_runs(runs_dir=RUNS):
    result = []
    if Path(runs_dir).exists():
        for path in Path(runs_dir).glob("*/status.json"):
            try:
                value = json.loads(path.read_text(encoding="utf-8"))
                value["directory"] = str(path.parent)
                result.append(value)
            except (OSError, ValueError):
                continue
    return sorted(result, key=lambda r: r.get("created_at", ""), reverse=True)


def safe_artifact(output_dir, relative_path):
    root = Path(output_dir).resolve()
    if not isinstance(relative_path, str) or not relative_path:
        raise ValueError("Agent must return a primary_artifact filename")
    path = (root / relative_path).resolve()
    if not path.is_relative_to(root) or not path.is_file():
        raise ValueError("Agent artifact must be a file inside its output directory")
    return path
