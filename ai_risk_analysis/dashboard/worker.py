"""Run one locally trusted stage in an isolated process."""

import argparse
from datetime import datetime, timezone
import importlib
import json
from pathlib import Path
import shutil
import sys
import traceback

from .core import is_available, safe_artifact, write_json


def execute(directory):
    directory = Path(directory)
    request = json.loads((directory / "request.json").read_text(encoding="utf-8"))
    state = {**request, "status": "running", "primary_artifact": None}
    write_json(directory / "status.json", state)
    try:
        stage = request["stage"]
        if not is_available(stage):
            raise ValueError("Stage is not connected")
        source = Path(request["input"])
        snapshot = directory / ("input" + source.suffix)
        shutil.copyfile(source, snapshot)
        output = directory / "output"
        output.mkdir()
        print(f"Starting {stage}", flush=True)
        agent = importlib.import_module(f"{stage}.agent")
        result = agent.run(snapshot, output, request["config"], lambda message: print(str(message), flush=True))
        if not isinstance(result, dict):
            raise ValueError("Agent run() must return an object")
        primary = safe_artifact(output, result.get("primary_artifact"))
        state.update(status="completed", primary_artifact=str(primary), result=result)
        print("Run completed. Results saved.", flush=True)
        return_code = 0
    except Exception as exc:
        state.update(status="failed", error=str(exc))
        traceback.print_exc()
        return_code = 1
    state["finished_at"] = datetime.now(timezone.utc).isoformat()
    write_json(directory / "status.json", state)
    return return_code


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("directory", type=Path)
    sys.exit(execute(parser.parse_args().directory))
