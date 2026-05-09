from __future__ import annotations

import json
import os
import re
import time
from pathlib import Path
from typing import Any, BinaryIO
from uuid import uuid4

from app.api.json_utils import JsonExtractionError, extract_json_object
from app.api.local_vlm import LocalVLMClient, LocalVLMError
from app.api.prompting import build_solar_inspection_prompt
from app.api.schemas import InspectionResult, result_from_mapping
from app.ml.raptormaps_classifier import (
    RaptorMapsClassifierClient,
    RaptorMapsClassifierError,
    prediction_to_result,
)


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
    def __init__(
        self,
        mode: str | None = None,
        samples_dir: Path = SAMPLES_DIR,
        local_vlm_client: LocalVLMClient | None = None,
        classifier_client: RaptorMapsClassifierClient | None = None,
    ) -> None:
        self.mode = mode or os.getenv("AI_MODE", "mock")
        self.samples_dir = samples_dir
        self.local_vlm_client = local_vlm_client
        self.classifier_client = classifier_client

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
        image_path: Path | None = None,
    ) -> InspectionResult:
        started = time.perf_counter()
        upload_path: Path | None = image_path

        if file_obj and filename:
            upload_path = self._save_upload(filename, file_obj)

        if self.mode == "mock":
            result = self._analyze_mock(sample_name=sample_name, filename=filename)
        elif self.mode in {"local", "vlm", "qwen"}:
            image_path = self._resolve_input_image_path(sample_name=sample_name, upload_path=upload_path)
            result = self._analyze_local_vlm(image_path=image_path, sample_name=sample_name)
        elif self.mode in {"classifier", "supervised", "raptormaps", "raptormaps_classifier", "supervised_baseline"}:
            image_path = self._resolve_input_image_path(sample_name=sample_name, upload_path=upload_path)
            result = self._analyze_classifier(image_path=image_path, sample_name=sample_name)
        else:
            raise AiServiceError(f"Unsupported AI_MODE: {self.mode}")

        result.latency_ms = int((time.perf_counter() - started) * 1000)
        return result

    def _analyze_mock(self, sample_name: str | None, filename: str | None) -> InspectionResult:
        selected_sample = sample_name or self._choose_sample_from_filename(filename)
        if selected_sample and self._expected_sample_exists(selected_sample):
            result = self._load_expected_sample(selected_sample)
            result.model_mode = f"{self.mode}:dataset_expected"
        else:
            result = self._load_sample(selected_sample)
            result.model_mode = self.mode

        return result

    def _analyze_local_vlm(self, image_path: Path, sample_name: str | None) -> InspectionResult:
        if self.local_vlm_client is None:
            self.local_vlm_client = LocalVLMClient()
        client = self.local_vlm_client
        prompt = build_solar_inspection_prompt()

        try:
            raw_output = client.analyze(image_path=image_path, prompt=prompt)
            payload = extract_json_object(raw_output)
            payload = normalize_local_vlm_payload(payload)
            payload.setdefault("inspection_id", sample_name or f"orvex-local-{int(time.time())}")
            payload["raw_model_output"] = raw_output
            payload["model_mode"] = self.mode
            payload["model_name"] = client.model_name
            return result_from_mapping(payload)
        except (JsonExtractionError, LocalVLMError, ValueError) as exc:
            raise AiServiceError(f"Local VLM output could not be validated: {exc}") from exc

    def _analyze_classifier(self, image_path: Path, sample_name: str | None) -> InspectionResult:
        if self.classifier_client is None:
            self.classifier_client = RaptorMapsClassifierClient()

        try:
            prediction = self.classifier_client.predict(image_path)
            return prediction_to_result(prediction=prediction, sample_name=sample_name)
        except (RaptorMapsClassifierError, ValueError) as exc:
            raise AiServiceError(f"RaptorMaps classifier could not produce a validated result: {exc}") from exc

    def _resolve_input_image_path(self, sample_name: str | None, upload_path: Path | None) -> Path:
        if upload_path is not None:
            return upload_path

        if sample_name:
            try:
                return self.get_sample_image_path(sample_name)
            except FileNotFoundError as exc:
                raise AiServiceError(
                    f"AI_MODE={self.mode} requires a local image file for sample '{sample_name}'."
                ) from exc

        raise AiServiceError(f"AI_MODE={self.mode} requires an uploaded image or dataset sample image.")

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
    def _save_upload(filename: str, file_obj: BinaryIO) -> Path:
        UPLOADS_DIR.mkdir(parents=True, exist_ok=True)
        source_name = Path(filename).name
        safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(source_name).stem).strip(".-")
        safe_stem = safe_stem[:80] or "inspection-upload"
        safe_suffix = Path(source_name).suffix.lower()[:12]
        safe_name = f"{int(time.time())}-{uuid4().hex[:10]}-{safe_stem}{safe_suffix}"
        destination = UPLOADS_DIR / safe_name
        with destination.open("wb") as handle:
            handle.write(file_obj.read())
        return destination


def normalize_local_vlm_payload(payload: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(payload)
    normalized.setdefault("human_review_required", True)
    if not normalized.get("summary"):
        normalized["summary"] = build_local_vlm_summary(normalized)
    return normalized


def build_local_vlm_summary(payload: dict[str, Any]) -> str:
    if payload.get("contains_solar_panel") is False:
        return "The image does not clearly show a photovoltaic module and requires human review."

    priority = str(payload.get("priority") or "inconclusive")
    findings = payload.get("findings")
    if isinstance(findings, list) and findings:
        first_finding = findings[0] if isinstance(findings[0], dict) else {}
        defect_type = str(first_finding.get("defect_type") or "visual anomaly")
        return f"Possible {defect_type} pattern with {priority} priority requires human review."

    if priority == "inconclusive":
        return "The inspection could not identify a reliable defect pattern and requires human review."

    return f"The local VLM returned {priority} triage priority and requires human review."
