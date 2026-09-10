import argparse
import csv
import json
from pathlib import Path
from urllib.error import HTTPError, URLError

from .pipeline import build_features
from .text import DemoExtractor, OpenAIExtractor


def main():
    parser = argparse.ArgumentParser(description="Combine numerical and text citizen features")
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--as-of", required=True, help="YYYY-MM-DD cutoff")
    parser.add_argument("--extractor", choices=("demo", "openai"), required=True)
    parser.add_argument("--model", help="Required for openai; no model is selected automatically")
    args = parser.parse_args()
    try:
        citizens = json.loads(args.input.read_text(encoding="utf-8"))
        if not isinstance(citizens, list) or not citizens:
            raise ValueError("Input must be a nonempty JSON list of citizen objects")
        if any(not isinstance(c, dict) for c in citizens):
            raise ValueError("Every citizen must be an object")
        ids = [c.get("citizen_id") for c in citizens]
        if any(not isinstance(i, str) for i in ids) or len(ids) != len(set(ids)):
            raise ValueError("Citizen IDs must be unique strings")
        extractor = DemoExtractor() if args.extractor == "demo" else OpenAIExtractor(args.model)
        results = [build_features(c, args.as_of, extractor) for c in citizens]
        args.output.mkdir(parents=True, exist_ok=True)
        (args.output / "features.json").write_text(json.dumps(results, indent=2, allow_nan=False), encoding="utf-8")
        rows = [{"citizen_id": r["citizen_id"], "as_of": r["as_of"], **r["features"]} for r in results]
        with (args.output / "features.csv").open("w", newline="", encoding="utf-8") as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    except HTTPError as exc:
        parser.exit(1, f"LLM request failed (HTTP {exc.code}); no fallback features were substituted.\n")
    except (ValueError, KeyError, TypeError, OSError, URLError) as exc:
        parser.exit(1, f"Feature extraction failed: {exc}\n")
    print(f"Created features for {len(results)} citizens in {args.output}")


if __name__ == "__main__":
    main()
