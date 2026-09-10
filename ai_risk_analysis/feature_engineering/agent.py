"""Dashboard adapter for the feature engineering stage."""

import csv
import json

from .pipeline import build_features, parse_date
from .text import DemoExtractor, OpenAIExtractor


def run(input_path, output_dir, config, log):
    cutoff = config.get("as_of", "")
    parse_date(cutoff)
    mode = config.get("extractor", "demo")
    if mode not in ("demo", "openai"):
        raise ValueError("Extractor must be demo or openai")
    extractor = DemoExtractor() if mode == "demo" else OpenAIExtractor(config.get("model"))
    citizens = json.loads(input_path.read_text(encoding="utf-8-sig"))
    if not isinstance(citizens, list) or not citizens or any(not isinstance(c, dict) for c in citizens):
        raise ValueError("Input must be a nonempty JSON list of citizen objects")
    ids = [c.get("citizen_id") for c in citizens]
    if any(not isinstance(i, str) or not i.strip() for i in ids) or len(ids) != len(set(ids)):
        raise ValueError("Citizen IDs must be unique nonempty strings")
    log(f"Loaded {len(citizens)} citizens. Extractor: {extractor.name}. Cutoff: {cutoff}.")
    results = []
    for index, citizen in enumerate(citizens, 1):
        results.append(build_features(citizen, cutoff, extractor))
        log(f"Processed {index} of {len(citizens)} citizens")
    output_dir.mkdir(parents=True, exist_ok=True)
    (output_dir / "features.json").write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
    rows = [{"citizen_id": r["citizen_id"], "as_of": r["as_of"], **r["features"]} for r in results]
    with (output_dir / "features.csv").open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return {"primary_artifact": "features.json", "record_count": len(results), "extractor": extractor.name}
