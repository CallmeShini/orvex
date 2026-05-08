from __future__ import annotations

import json
from pathlib import Path

import pytest
from PIL import Image

from app.api.ai_service import OrvexAIService
from app.api.schemas import Priority
from app.ml.raptormaps_classifier import (
    ClassifierPrediction,
    RaptorMapsRecord,
    class_distribution,
    load_raptormaps_records,
    prediction_to_result,
    stratified_split,
)


def write_fake_raptormaps_root(root: Path) -> None:
    images = root / "images"
    images.mkdir(parents=True)
    metadata = {}
    labels = ["No-Anomaly", "Hot-Spot", "Soiling", "Cracking"]
    for index, label in enumerate(labels):
        image_id = str(index)
        image_path = images / f"{image_id}.jpg"
        Image.new("L", (24, 40), color=index * 40).save(image_path)
        metadata[image_id] = {
            "image_filepath": f"images/{image_id}.jpg",
            "anomaly_class": label,
        }
    (root / "module_metadata.json").write_text(json.dumps(metadata), encoding="utf-8")


def test_load_raptormaps_records_from_global_metadata(tmp_path: Path) -> None:
    write_fake_raptormaps_root(tmp_path)

    records = load_raptormaps_records(tmp_path)

    assert [record.image_id for record in records] == ["0", "1", "2", "3"]
    assert class_distribution(records)["Hot-Spot"] == 1
    assert records[1].image_path.name == "1.jpg"


def test_stratified_split_keeps_each_class_represented() -> None:
    records = []
    for label in ("No-Anomaly", "Hot-Spot"):
        for index in range(10):
            records.append(
                RaptorMapsRecord(image_id=f"{label}-{index}", image_path=Path("x.jpg"), label=label)
            )

    train, validation = stratified_split(records, val_ratio=0.2, seed=7)

    assert len(train) == 16
    assert len(validation) == 4
    assert class_distribution(train)["No-Anomaly"] == 8
    assert class_distribution(validation)["Hot-Spot"] == 2


def test_prediction_to_result_uses_cautious_triage_language() -> None:
    prediction = ClassifierPrediction(
        label="Hot-Spot",
        confidence=0.82,
        probabilities={"Hot-Spot": 0.82, "No-Anomaly": 0.18},
        inference_ms=12,
        artifact_path="data/models/raptormaps_classifier.pt",
        model_name="raptormaps-tiny-thermal-cnn",
    )

    result = prediction_to_result(prediction, sample_name="raptormaps-hot_spot-06722")

    assert result.priority == Priority.HIGH
    assert result.human_review_required is True
    assert result.model_mode == "classifier:raptormaps"
    assert "possible Hot-Spot" in result.summary
    assert result.findings[0].defect_type == "hotspot"


def test_prediction_to_result_routes_low_confidence_to_inconclusive() -> None:
    prediction = ClassifierPrediction(
        label="Hot-Spot",
        confidence=0.2,
        probabilities={"Hot-Spot": 0.2, "No-Anomaly": 0.19},
        inference_ms=12,
        artifact_path="data/models/raptormaps_classifier.pt",
        model_name="raptormaps-tiny-thermal-cnn",
    )

    result = prediction_to_result(prediction, sample_name="weak-sample")

    assert result.priority == Priority.INCONCLUSIVE
    assert result.overall_risk_score == 0.0
    assert result.findings == []
    assert "too low" in result.summary


def test_classifier_mode_uses_injected_client() -> None:
    class FakeClassifierClient:
        def predict(self, image_path: Path) -> ClassifierPrediction:
            assert image_path.name == "panel.jpg"
            return ClassifierPrediction(
                label="No-Anomaly",
                confidence=0.91,
                probabilities={"No-Anomaly": 0.91},
                inference_ms=3,
                artifact_path="fake.pt",
                model_name="fake-classifier",
            )

    service = OrvexAIService(mode="classifier", classifier_client=FakeClassifierClient())
    result = service.analyze_image(filename="panel.jpg", file_obj=FakeUpload(b"image"))

    assert result.priority == Priority.LOW
    assert result.human_review_required is True
    assert result.model_name == "fake-classifier"
    assert result.model_mode == "classifier:raptormaps"


class FakeUpload:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload

    def read(self) -> bytes:
        return self.payload
