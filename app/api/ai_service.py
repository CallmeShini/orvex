from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Any, BinaryIO

from app.api.schemas import InspectionResult, result_from_mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"
EVALUATION_DIR = DATA_DIR / "evaluation"
EXPECTED_OUTPUTS_DIR = EVALUATION_DIR / "expected_outputs"
RAPTORMAPS_MANIFEST_PATH = EVALUATION_DIR / "raptormaps_manifest.jsonl"
DEMO_PATH = EVALUATION_DIR / "demo_path.json"


class AiServiceError(RuntimeError):
    """Raised when the AI service cannot produce an inspection result."""


class OrvexAIService:
    def __init__(self, mode: str | None = None, samples_dir: Path = SAMPLES_DIR) -> None:
        self.mode = mode or os.getenv("AI_MODE", "mock")
        self.samples_dir = samples_dir

    def list_samples(self) -> list[dict[str, Any]]:
        samples: list[dict[str, Any]] = []
        demo_metadata = self._load_demo_path()
        for path in sorted(self.samples_dir.glob("*.json")):
            result = self._load_sample(path.stem)
            demo_entry = demo_metadata.get(path.stem, {})
            samples.append(
                {
                    "name": path.stem,
                    "dataset": "Orvex mock samples",
                    "kind": "mock",
                    "priority": result.priority.value,
                    "summary": result.summary,
                    "source_label": "",
                    "orvex_bucket": "",
                    "image_available": False,
                    "is_demo": bool(demo_entry),
                    "demo_order": demo_entry.get("order"),
                    "demo_stage": demo_entry.get("stage", ""),
                    "demo_title": demo_entry.get("demo_title", ""),
                    "demo_role": demo_entry.get("demo_role", ""),
                    "demo_reason": demo_entry.get("reason", ""),
                    "expected_output_source": demo_entry.get("expected_output_source", ""),
                    "claim_boundary": demo_entry.get("claim_boundary", ""),
                    "needs_human_review_reason": demo_entry.get("needs_human_review_reason", ""),
                    "visual_limitations": demo_entry.get("visual_limitations", ""),
                    "commercial_use_status": demo_entry.get("commercial_use_status", ""),
                    "license": "",
                }
            )

        for sample_id, manifest_entry in self._load_manifest().items():
            expected_path = EXPECTED_OUTPUTS_DIR / f"{sample_id}.json"
            if not expected_path.exists():
                continue
            result = self._load_expected_sample(sample_id)
            image_path = PROJECT_ROOT / manifest_entry["local_path"]
            demo_entry = demo_metadata.get(sample_id, {})
            samples.append(
                {
                    "name": sample_id,
                    "dataset": manifest_entry["dataset"],
                    "kind": "dataset_expected",
                    "priority": result.priority.value,
                    "summary": result.summary,
                    "source_label": manifest_entry["source_label"],
                    "orvex_bucket": manifest_entry["orvex_bucket"],
                    "image_available": image_path.exists(),
                    "is_demo": bool(demo_entry),
                    "demo_order": demo_entry.get("order"),
                    "demo_stage": demo_entry.get("stage", ""),
                    "demo_title": demo_entry.get("demo_title", ""),
                    "demo_role": demo_entry.get("demo_role", ""),
                    "demo_reason": demo_entry.get("reason", ""),
                    "expected_output_source": demo_entry.get("expected_output_source", ""),
                    "claim_boundary": demo_entry.get("claim_boundary", ""),
                    "needs_human_review_reason": demo_entry.get("needs_human_review_reason", ""),
                    "visual_limitations": demo_entry.get("visual_limitations", ""),
                    "commercial_use_status": demo_entry.get("commercial_use_status", ""),
                    "license": manifest_entry["license"],
                }
            )
        return sorted(
            samples,
            key=lambda sample: (
                sample["demo_order"] is None,
                sample["demo_order"] or 999,
                sample["kind"],
                sample["name"],
            ),
        )

    def analyze_image(
        self,
        sample_name: str | None = None,
        filename: str | None = None,
        file_obj: BinaryIO | None = None,
    ) -> InspectionResult:
        started = time.perf_counter()

        if file_obj and filename:
            self._save_upload(filename, file_obj)

        if self.mode != "mock":
            raise AiServiceError("Only AI_MODE=mock is implemented in the local Day 1 build.")

        selected_sample = sample_name or self._choose_sample_from_filename(filename)
        if selected_sample and self._expected_sample_exists(selected_sample):
            result = self._load_expected_sample(selected_sample)
            result.model_mode = f"{self.mode}:dataset_expected"
        else:
            result = self._load_sample(selected_sample)
            result.model_mode = self.mode

        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    def get_sample_image_path(self, sample_name: str) -> Path:
        manifest_entry = self._load_manifest().get(sample_name)
        if not manifest_entry:
            raise FileNotFoundError(f"Sample image not found: {sample_name}")

        image_path = PROJECT_ROOT / manifest_entry["local_path"]
        if not image_path.exists():
            raise FileNotFoundError(f"Sample image file is not available locally: {sample_name}")
        return image_path

    def inconclusive_result(self, raw_output: str | None = None) -> InspectionResult:
        payload = {
            "image_modality": "unknown",
            "contains_solar_panel": False,
            "inspection_confidence": 0.15,
            "overall_risk_score": 0.0,
            "priority": "inconclusive",
            "findings": [],
            "human_review_required": True,
            "summary": "The inspection could not be completed reliably and requires human review.",
            "raw_model_output": raw_output,
            "model_mode": self.mode,
        }
        return result_from_mapping(payload)

    def _load_sample(self, sample_name: str) -> InspectionResult:
        safe_name = sample_name.strip().lower().replace(" ", "_")
        path = self.samples_dir / f"{safe_name}.json"
        if not path.exists():
            path = self.samples_dir / "inconclusive.json"

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        return result_from_mapping(payload)

    @staticmethod
    def _load_manifest() -> dict[str, dict[str, str]]:
        if not RAPTORMAPS_MANIFEST_PATH.exists():
            return {}

        entries: dict[str, dict[str, str]] = {}
        with RAPTORMAPS_MANIFEST_PATH.open("r", encoding="utf-8") as handle:
            for line in handle:
                if not line.strip():
                    continue
                payload = json.loads(line)
                entries[payload["sample_id"]] = payload
        return entries

    @staticmethod
    def _load_demo_path() -> dict[str, dict[str, Any]]:
        if not DEMO_PATH.exists():
            return {}

        payload = json.loads(DEMO_PATH.read_text(encoding="utf-8"))
        return {entry["sample_id"]: entry for entry in payload}

    @staticmethod
    def _expected_sample_exists(sample_name: str) -> bool:
        return (EXPECTED_OUTPUTS_DIR / f"{sample_name}.json").exists()

    @staticmethod
    def _load_expected_sample(sample_name: str) -> InspectionResult:
        path = EXPECTED_OUTPUTS_DIR / f"{sample_name}.json"
        if not path.exists():
            raise AiServiceError(f"Expected output not found for sample: {sample_name}")

        with path.open("r", encoding="utf-8") as handle:
            payload = json.load(handle)

        return result_from_mapping(payload)

    @staticmethod
    def _choose_sample_from_filename(filename: str | None) -> str:
        if not filename:
            return "hotspot"
        lowered = filename.lower()
        for candidate in ("clean", "hotspot", "soiling", "inconclusive"):
            if candidate in lowered:
                return candidate
        return "hotspot"

    @staticmethod
    def _save_upload(filename: str, file_obj: BinaryIO) -> None:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        safe_name = Path(filename).name
        destination = UPLOADS_DIR / safe_name
        with destination.open("wb") as handle:
            handle.write(file_obj.read())
