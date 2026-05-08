from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ml.raptormaps_classifier import (  # noqa: E402
    RaptorMapsClassifierClient,
    load_raptormaps_records,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run the RaptorMaps supervised classifier on one image.")
    parser.add_argument("--artifact", default="data/models/raptormaps_classifier.pt")
    parser.add_argument("--image", default=None, help="Image path. If omitted, --sample-id is used.")
    parser.add_argument("--sample-id", default="6722", help="RaptorMaps numeric image id.")
    parser.add_argument("--data-root", default="data/external/raptormaps/raw/InfraredSolarModules")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.image:
        image_path = Path(args.image)
    else:
        records = {record.image_id: record for record in load_raptormaps_records(args.data_root)}
        image_path = records[args.sample_id].image_path

    client = RaptorMapsClassifierClient(artifact_path=args.artifact)
    prediction = client.predict(image_path)
    print(json.dumps(prediction.__dict__, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()

