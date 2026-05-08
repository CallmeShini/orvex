from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.ai_service import OrvexAIService  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run Orvex classifier mode through the InspectionResult contract.")
    parser.add_argument("--artifact", default="data/models/raptormaps_classifier.pt")
    parser.add_argument("--sample", default="raptormaps-hot_spot-06722")
    parser.add_argument("--output", default=None, help="Optional JSON output path.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    os.environ["ORVEX_CLASSIFIER_ARTIFACT"] = args.artifact
    service = OrvexAIService(mode="classifier")
    result = service.analyze_image(sample_name=args.sample)
    payload = result.model_dump(mode="json")
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()

