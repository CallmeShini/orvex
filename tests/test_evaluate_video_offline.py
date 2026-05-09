from __future__ import annotations

from pathlib import Path

import pytest

from app.api.schemas import ImageModality, InspectionResult, Priority
from app.api.structured_events import load_structured_events
from app.ml.video_pipeline import ExtractedFrame
from scripts.evaluate_video_offline import inspect_frames, reject_url


def test_reject_url_disallows_remote_video_inputs() -> None:
    with pytest.raises(ValueError, match="local file path"):
        reject_url("https://example.com/inspection.mp4")


def test_reject_url_allows_local_video_paths() -> None:
    reject_url("/tmp/inspection.mp4")


def test_inspect_frames_writes_structured_frame_events(tmp_path: Path) -> None:
    frame = ExtractedFrame(frame_index=2, timestamp_ms=2000, path=tmp_path / "frame-000003.jpg", sha256="abc123")
    events_path = tmp_path / "events.jsonl"

    class FakeService:
        def analyze_image(self, filename: str, image_path: Path) -> InspectionResult:
            return InspectionResult(
                image_modality=ImageModality.RGB,
                contains_solar_panel=True,
                inspection_confidence=0.7,
                overall_risk_score=0.4,
                priority=Priority.MEDIUM,
                findings=[],
                human_review_required=True,
                summary="Frame requires review.",
                model_name="fake-model",
                model_mode="classifier:raptormaps",
                latency_ms=17,
            )

    inspections = inspect_frames(
        frames=[frame],
        service=FakeService(),
        continue_on_error=False,
        events_path=events_path,
    )

    assert len(inspections) == 1
    events = load_structured_events(events_path)
    assert events[0]["event"] == "frame_analyzed"
    assert events[0]["frame_index"] == 2
    assert events[0]["model_mode"] == "classifier:raptormaps"
    assert events[0]["latency_ms"] == 17
