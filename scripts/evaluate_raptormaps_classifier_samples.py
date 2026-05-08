from __future__ import annotations

import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ml.raptormaps_classifier import RaptorMapsClassifierClient  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Evaluate a RaptorMaps classifier artifact against the curated Orvex sample manifest."
    )
    parser.add_argument("--artifact", default="data/models/raptormaps_classifier.pt")
    parser.add_argument("--manifest", default="data/evaluation/raptormaps_manifest.jsonl")
    parser.add_argument("--confidence-floor", type=float, default=0.45)
    parser.add_argument("--output", default=None)
    return parser.parse_args()


def load_manifest(path: Path) -> list[dict[str, Any]]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def summarize_evaluation_rows(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(rows)
    source_counts = Counter(row["source_label"] for row in rows)
    prediction_counts = Counter(row["predicted_label"] for row in rows)
    per_source: dict[str, dict[str, int]] = defaultdict(
        lambda: {
            "total": 0,
            "exact_matches": 0,
            "anomaly_binary_matches": 0,
            "confident_predictions": 0,
        }
    )

    exact_matches = 0
    anomaly_binary_matches = 0
    confident_predictions = 0
    for row in rows:
        source_label = row["source_label"]
        bucket = per_source[source_label]
        bucket["total"] += 1
        if row["exact_match"]:
            exact_matches += 1
            bucket["exact_matches"] += 1
        if row["anomaly_binary_match"]:
            anomaly_binary_matches += 1
            bucket["anomaly_binary_matches"] += 1
        if row["confident"]:
            confident_predictions += 1
            bucket["confident_predictions"] += 1

    def ratio(value: int) -> float:
        return round(value / total, 6) if total else 0.0

    return {
        "total": total,
        "exact_matches": exact_matches,
        "exact_accuracy": ratio(exact_matches),
        "anomaly_binary_matches": anomaly_binary_matches,
        "anomaly_binary_accuracy": ratio(anomaly_binary_matches),
        "confident_predictions": confident_predictions,
        "confident_rate": ratio(confident_predictions),
        "source_label_distribution": dict(sorted(source_counts.items())),
        "predicted_label_distribution": dict(sorted(prediction_counts.items())),
        "per_source_label": dict(sorted(per_source.items())),
    }


def evaluate_manifest(
    *,
    artifact: Path,
    manifest_path: Path,
    confidence_floor: float,
) -> dict[str, Any]:
    client = RaptorMapsClassifierClient(artifact_path=artifact)
    rows = []
    for item in load_manifest(manifest_path):
        image_path = Path(item["local_path"])
        if not image_path.exists():
            raise FileNotFoundError(f"Manifest image path does not exist: {image_path}")
        prediction = client.predict(image_path)
        source_is_anomaly = item["source_label"] != "No-Anomaly"
        predicted_is_anomaly = prediction.label != "No-Anomaly"
        rows.append(
            {
                "sample_id": item["sample_id"],
                "source_label": item["source_label"],
                "predicted_label": prediction.label,
                "confidence": round(prediction.confidence, 6),
                "confident": prediction.confidence >= confidence_floor,
                "exact_match": prediction.label == item["source_label"],
                "anomaly_binary_match": predicted_is_anomaly == source_is_anomaly,
            }
        )

    return {
        "artifact": str(artifact),
        "manifest": str(manifest_path),
        "confidence_floor": confidence_floor,
        "summary": summarize_evaluation_rows(rows),
        "rows": rows,
    }


def main() -> None:
    args = parse_args()
    payload = evaluate_manifest(
        artifact=Path(args.artifact),
        manifest_path=Path(args.manifest),
        confidence_floor=args.confidence_floor,
    )
    text = json.dumps(payload, indent=2, ensure_ascii=False, sort_keys=True) + "\n"
    if args.output:
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(text, encoding="utf-8")
    print(text, end="")


if __name__ == "__main__":
    main()
