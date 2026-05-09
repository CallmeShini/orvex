from __future__ import annotations

import sys
from pathlib import Path

from app.ml.raptormaps_classifier import ClassifierPrediction, prediction_to_result
from scripts import smoke_raptormaps_classifier


def test_smoke_classifier_accepts_explicit_image(monkeypatch, tmp_path: Path, capsys) -> None:
    image_path = tmp_path / "panel.jpg"
    image_path.write_bytes(b"fake image payload")
    artifact_path = tmp_path / "classifier.pt"

    calls = {}

    class FakeService:
        def __init__(self, mode: str) -> None:
            calls["mode"] = mode

        def analyze_image(self, sample_name: str | None = None, image_path: Path | None = None):
            calls["sample_name"] = sample_name
            calls["image_path"] = image_path
            return prediction_to_result(
                prediction=ClassifierPrediction(
                    label="No-Anomaly",
                    confidence=0.93,
                    probabilities={"No-Anomaly": 0.93},
                    inference_ms=2,
                    artifact_path=str(artifact_path),
                    model_name="fake-classifier",
                ),
                sample_name=sample_name,
            )

    monkeypatch.setattr(smoke_raptormaps_classifier, "OrvexAIService", FakeService)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            "smoke_raptormaps_classifier.py",
            "--artifact",
            str(artifact_path),
            "--image",
            str(image_path),
        ],
    )

    smoke_raptormaps_classifier.main()

    output = capsys.readouterr().out
    assert '"model_name": "fake-classifier"' in output
    assert calls == {
        "mode": "classifier",
        "sample_name": None,
        "image_path": image_path,
    }
