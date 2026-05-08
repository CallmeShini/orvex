from __future__ import annotations

import argparse
import json
import sys
import time
import traceback
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.ai_service import OrvexAIService


DEFAULT_SAMPLES = [
    "raptormaps-no_anomaly-10000",
    "raptormaps-hot_spot-06722",
    "raptormaps-soiling-08157",
    "raptormaps-cracking-06971",
    "raptormaps-offline_module-00000",
]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run local VLM smoke tests against multiple Orvex samples.")
    parser.add_argument("--samples", nargs="*", default=DEFAULT_SAMPLES, help="Dataset sample ids to analyze.")
    parser.add_argument(
        "--output-dir",
        default="data/external/smoke_results",
        help="Ignored directory where smoke result JSON files are written.",
    )
    return parser.parse_args()


def summarize_result(record: dict[str, Any]) -> dict[str, Any]:
    keys = (
        "sample_id",
        "status",
        "elapsed_s",
        "priority",
        "risk",
        "confidence",
        "findings_count",
        "error",
    )
    return {key: record[key] for key in keys if key in record}


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    service = OrvexAIService(mode="local")
    summary: list[dict[str, Any]] = []

    for sample_id in args.samples:
        started = time.perf_counter()
        try:
            result = service.analyze_image(sample_name=sample_id)
            record: dict[str, Any] = {
                "sample_id": sample_id,
                "status": "ok",
                "elapsed_s": round(time.perf_counter() - started, 3),
                "priority": result.priority.value,
                "risk": result.overall_risk_score,
                "confidence": result.inspection_confidence,
                "findings_count": len(result.findings),
                "model_name": result.model_name,
                "model_mode": result.model_mode,
                "result": result.model_dump(mode="json"),
            }
        except Exception as exc:  # noqa: BLE001 - smoke runner must record per-sample failures.
            record = {
                "sample_id": sample_id,
                "status": "error",
                "elapsed_s": round(time.perf_counter() - started, 3),
                "error": repr(exc),
                "traceback": traceback.format_exc(),
            }

        (output_dir / f"{sample_id}.json").write_text(
            json.dumps(record, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
        summary_record = summarize_result(record)
        summary.append(summary_record)
        print(json.dumps(summary_record, ensure_ascii=False), flush=True)

    (output_dir / "summary.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    print(f"SMOKE_RESULTS_DIR {output_dir}", flush=True)

    if any(record["status"] == "error" for record in summary):
        raise SystemExit(1)


if __name__ == "__main__":
    main()
