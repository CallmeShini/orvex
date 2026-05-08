from __future__ import annotations

import json
import os
import random
import time
from collections import Counter, defaultdict
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image

from app.api.schemas import (
    DefectType,
    Finding,
    ImageModality,
    InspectionResult,
    Priority,
)


PROJECT_ROOT = Path(__file__).resolve().parents[2]
DEFAULT_RAPTORMAPS_ROOT = PROJECT_ROOT / "data" / "external" / "raptormaps" / "raw" / "InfraredSolarModules"
DEFAULT_CLASSIFIER_ARTIFACT = PROJECT_ROOT / "data" / "models" / "raptormaps_classifier.pt"
DEFAULT_IMAGE_SIZE = (24, 40)
DEFAULT_CONFIDENCE_FLOOR = 0.45

RAPTORMAPS_CLASSES = (
    "No-Anomaly",
    "Cell",
    "Cell-Multi",
    "Cracking",
    "Hot-Spot",
    "Hot-Spot-Multi",
    "Shadowing",
    "Diode",
    "Diode-Multi",
    "Vegetation",
    "Soiling",
    "Offline-Module",
)

LABEL_TO_DEFECT = {
    "Cell": DefectType.BROKEN_CELL,
    "Cell-Multi": DefectType.BROKEN_CELL,
    "Cracking": DefectType.CRACK,
    "Hot-Spot": DefectType.HOTSPOT,
    "Hot-Spot-Multi": DefectType.HOTSPOT,
    "Shadowing": DefectType.SHADOWING,
    "Diode": DefectType.DIODE,
    "Diode-Multi": DefectType.DIODE,
    "Vegetation": DefectType.VEGETATION,
    "Soiling": DefectType.SOILING,
    "Offline-Module": DefectType.OFFLINE_MODULE,
}

LABEL_TO_PRIORITY = {
    "No-Anomaly": Priority.LOW,
    "Cell": Priority.MEDIUM,
    "Cell-Multi": Priority.HIGH,
    "Cracking": Priority.HIGH,
    "Hot-Spot": Priority.HIGH,
    "Hot-Spot-Multi": Priority.CRITICAL,
    "Shadowing": Priority.MEDIUM,
    "Diode": Priority.HIGH,
    "Diode-Multi": Priority.CRITICAL,
    "Vegetation": Priority.MEDIUM,
    "Soiling": Priority.MEDIUM,
    "Offline-Module": Priority.CRITICAL,
}

LABEL_TO_RISK = {
    "No-Anomaly": 0.08,
    "Cell": 0.52,
    "Cell-Multi": 0.7,
    "Cracking": 0.72,
    "Hot-Spot": 0.76,
    "Hot-Spot-Multi": 0.88,
    "Shadowing": 0.42,
    "Diode": 0.78,
    "Diode-Multi": 0.9,
    "Vegetation": 0.44,
    "Soiling": 0.38,
    "Offline-Module": 0.94,
}


@dataclass(frozen=True)
class RaptorMapsRecord:
    image_id: str
    image_path: Path
    label: str


@dataclass(frozen=True)
class ClassifierPrediction:
    label: str
    confidence: float
    probabilities: dict[str, float]
    inference_ms: int
    artifact_path: str
    model_name: str


class RaptorMapsClassifierError(RuntimeError):
    """Raised when the supervised RaptorMaps classifier cannot run."""


def require_torch() -> Any:
    try:
        import torch
        from torch import nn
    except ModuleNotFoundError as exc:
        raise RaptorMapsClassifierError(
            "PyTorch is required for RaptorMaps classifier training/inference. "
            "Use the ROCm-enabled VPS environment."
        ) from exc
    return torch, nn


def normalize_label(label: str) -> str:
    normalized = label.strip()
    known = {item.lower(): item for item in RAPTORMAPS_CLASSES}
    try:
        return known[normalized.lower()]
    except KeyError as exc:
        raise ValueError(f"Unknown RaptorMaps label: {label}") from exc


def resolve_raptormaps_root(root: Path | str | None = None) -> Path:
    base = Path(root).expanduser() if root else DEFAULT_RAPTORMAPS_ROOT
    if (base / "module_metadata.json").exists():
        return base
    nested = base / "InfraredSolarModules"
    if (nested / "module_metadata.json").exists():
        return nested
    raise FileNotFoundError(f"RaptorMaps module_metadata.json not found under {base}")


def load_raptormaps_records(root: Path | str | None = None) -> list[RaptorMapsRecord]:
    dataset_root = resolve_raptormaps_root(root)
    metadata_path = dataset_root / "module_metadata.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))

    records: list[RaptorMapsRecord] = []
    for image_id, payload in metadata.items():
        label = normalize_label(payload["anomaly_class"])
        image_path = dataset_root / payload["image_filepath"]
        records.append(RaptorMapsRecord(image_id=str(image_id), image_path=image_path, label=label))

    return sorted(records, key=lambda record: int(record.image_id))


def class_distribution(records: list[RaptorMapsRecord]) -> dict[str, int]:
    counts = Counter(record.label for record in records)
    return {label: counts.get(label, 0) for label in RAPTORMAPS_CLASSES}


def stratified_split(
    records: list[RaptorMapsRecord],
    val_ratio: float,
    seed: int,
    max_per_class: int | None = None,
) -> tuple[list[RaptorMapsRecord], list[RaptorMapsRecord]]:
    if not 0 < val_ratio < 1:
        raise ValueError("val_ratio must be between 0 and 1")

    rng = random.Random(seed)
    grouped: dict[str, list[RaptorMapsRecord]] = defaultdict(list)
    for record in records:
        grouped[record.label].append(record)

    train: list[RaptorMapsRecord] = []
    val: list[RaptorMapsRecord] = []
    for label in RAPTORMAPS_CLASSES:
        group = list(grouped[label])
        rng.shuffle(group)
        if max_per_class is not None:
            group = group[:max_per_class]
        val_count = max(1, int(round(len(group) * val_ratio))) if len(group) > 1 else len(group)
        val.extend(group[:val_count])
        train.extend(group[val_count:])

    rng.shuffle(train)
    rng.shuffle(val)
    return train, val


def build_model(num_classes: int) -> Any:
    _torch, nn = require_torch()

    class TinyThermalCNN(nn.Module):
        def __init__(self) -> None:
            super().__init__()
            self.features = nn.Sequential(
                nn.Conv2d(1, 16, kernel_size=3, padding=1),
                nn.BatchNorm2d(16),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
                nn.Conv2d(16, 32, kernel_size=3, padding=1),
                nn.BatchNorm2d(32),
                nn.ReLU(inplace=True),
                nn.MaxPool2d(2),
                nn.Conv2d(32, 64, kernel_size=3, padding=1),
                nn.BatchNorm2d(64),
                nn.ReLU(inplace=True),
                nn.AdaptiveAvgPool2d((1, 1)),
            )
            self.classifier = nn.Linear(64, num_classes)

        def forward(self, inputs: Any) -> Any:
            features = self.features(inputs)
            return self.classifier(features.flatten(1))

    return TinyThermalCNN()


def image_to_tensor(image_path: Path, image_size: tuple[int, int] = DEFAULT_IMAGE_SIZE) -> Any:
    torch, _nn = require_torch()
    import numpy as np

    with Image.open(image_path) as image:
        grayscale = image.convert("L").resize(image_size)
        array = np.asarray(grayscale, dtype=np.float32) / 255.0
    return torch.from_numpy(array).unsqueeze(0)


def prediction_to_result(
    prediction: ClassifierPrediction,
    sample_name: str | None = None,
    raw_output: str | None = None,
    confidence_floor: float | None = None,
) -> InspectionResult:
    label = normalize_label(prediction.label)
    confidence = max(0.0, min(float(prediction.confidence), 1.0))
    confidence_floor = DEFAULT_CONFIDENCE_FLOOR if confidence_floor is None else confidence_floor
    is_inconclusive = confidence < confidence_floor
    priority = LABEL_TO_PRIORITY[label]
    risk = LABEL_TO_RISK[label]
    contains_panel = True

    findings: list[Finding] = []
    if is_inconclusive:
        priority = Priority.INCONCLUSIVE
        risk = 0.0
    elif label != "No-Anomaly":
        defect_type = LABEL_TO_DEFECT.get(label, DefectType.UNKNOWN)
        findings.append(
            Finding(
                defect_type=defect_type,
                severity=priority,
                confidence=confidence,
                location_hint="module-level thermal crop; no bounding box available in RaptorMaps metadata",
                visual_evidence=f"Supervised RaptorMaps classifier predicted {label} from the infrared module crop.",
                recommended_action=_recommended_action(label),
            )
        )

    payload = {
        "inspection_id": sample_name or f"orvex-classifier-{int(time.time())}",
        "image_modality": ImageModality.INFRARED,
        "contains_solar_panel": contains_panel,
        "inspection_confidence": confidence,
        "overall_risk_score": risk,
        "priority": priority,
        "findings": findings,
        "human_review_required": True,
        "summary": _summary_for_label(label, confidence, is_inconclusive=is_inconclusive),
        "raw_model_output": raw_output or json.dumps(asdict(prediction), sort_keys=True),
        "model_name": prediction.model_name,
        "model_mode": "classifier:raptormaps",
        "latency_ms": prediction.inference_ms,
    }
    return InspectionResult.model_validate(payload)


def _summary_for_label(label: str, confidence: float, is_inconclusive: bool) -> str:
    if is_inconclusive:
        return (
            f"Supervised classifier score was too low for a reliable RaptorMaps label "
            f"({label}, {confidence:.2f}). Route this image to human review."
        )
    if label == "No-Anomaly":
        return (
            "Supervised classifier found no RaptorMaps anomaly pattern "
            f"with uncalibrated score {confidence:.2f}. Human review remains required."
        )
    return (
        f"Supervised classifier flagged a possible {label} pattern with uncalibrated score {confidence:.2f}. "
        "Treat this as triage evidence and route to human review."
    )


def _recommended_action(label: str) -> str:
    if label in {"Hot-Spot", "Hot-Spot-Multi", "Diode", "Diode-Multi", "Cell", "Cell-Multi"}:
        return "Prioritize electrical review and compare against string or inverter telemetry."
    if label == "Offline-Module":
        return "Escalate for field verification of module connectivity and production loss."
    if label == "Cracking":
        return "Request higher-resolution RGB confirmation before assigning structural repair work."
    if label in {"Soiling", "Vegetation", "Shadowing"}:
        return "Schedule maintenance review and verify whether obstruction is persistent."
    return "Route to technician review with supporting site context."


class RaptorMapsClassifierClient:
    def __init__(
        self,
        artifact_path: Path | str | None = None,
        device: str | None = None,
    ) -> None:
        self.artifact_path = Path(
            artifact_path or os.getenv("ORVEX_CLASSIFIER_ARTIFACT", str(DEFAULT_CLASSIFIER_ARTIFACT))
        )
        self.device_name = device
        self._loaded: tuple[Any, dict[str, Any]] | None = None

    @property
    def model_name(self) -> str:
        if self._loaded is None:
            return "raptormaps-tiny-thermal-cnn"
        _model, artifact = self._loaded
        return str(artifact.get("metadata", {}).get("model_name", "raptormaps-tiny-thermal-cnn"))

    def predict(self, image_path: Path) -> ClassifierPrediction:
        started = time.perf_counter()
        torch, _nn = require_torch()
        model, artifact = self._load()
        classes = tuple(artifact["classes"])

        tensor = image_to_tensor(image_path, tuple(artifact.get("image_size", DEFAULT_IMAGE_SIZE)))
        tensor = tensor.unsqueeze(0).to(next(model.parameters()).device)
        with torch.no_grad():
            logits = model(tensor)
            probabilities_tensor = torch.softmax(logits, dim=1)[0].detach().cpu()

        probabilities = {
            label: round(float(probabilities_tensor[index].item()), 6)
            for index, label in enumerate(classes)
        }
        best_index = int(probabilities_tensor.argmax().item())
        return ClassifierPrediction(
            label=str(classes[best_index]),
            confidence=float(probabilities_tensor[best_index].item()),
            probabilities=probabilities,
            inference_ms=int((time.perf_counter() - started) * 1000),
            artifact_path=str(self.artifact_path),
            model_name=self.model_name,
        )

    def _load(self) -> tuple[Any, dict[str, Any]]:
        if self._loaded is not None:
            return self._loaded

        if not self.artifact_path.exists():
            raise RaptorMapsClassifierError(f"Classifier artifact not found: {self.artifact_path}")

        torch, _nn = require_torch()
        # The artifact is produced by our own training script and stores metadata
        # alongside tensors, so PyTorch's weights-only loader cannot read it.
        artifact = torch.load(self.artifact_path, map_location="cpu", weights_only=False)
        classes = tuple(artifact["classes"])
        model = build_model(num_classes=len(classes))
        model.load_state_dict(artifact["model_state_dict"])
        device = self._resolve_device(torch)
        model.to(device)
        model.eval()
        self._loaded = (model, artifact)
        return self._loaded

    def _resolve_device(self, torch: Any) -> Any:
        if self.device_name:
            return torch.device(self.device_name)
        if torch.cuda.is_available():
            return torch.device("cuda")
        return torch.device("cpu")
