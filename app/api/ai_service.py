from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import BinaryIO

from app.api.schemas import InspectionResult, result_from_mapping


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = PROJECT_ROOT / "data"
SAMPLES_DIR = DATA_DIR / "samples"
UPLOADS_DIR = DATA_DIR / "uploads"


class AiServiceError(RuntimeError):
    """Raised when the AI service cannot produce an inspection result."""


class OrvexAIService:
    def __init__(self, mode: str | None = None, samples_dir: Path = SAMPLES_DIR) -> None:
        self.mode = mode or os.getenv("AI_MODE", "mock")
        self.samples_dir = samples_dir

    def list_samples(self) -> list[dict[str, str]]:
        samples: list[dict[str, str]] = []
        for path in sorted(self.samples_dir.glob("*.json")):
            result = self._load_sample(path.stem)
            samples.append(
                {
                    "name": path.stem,
                    "priority": result.priority.value,
                    "summary": result.summary,
                }
            )
        return samples

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

        result = self._load_sample(sample_name or self._choose_sample_from_filename(filename))
        result.model_mode = self.mode
        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

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
