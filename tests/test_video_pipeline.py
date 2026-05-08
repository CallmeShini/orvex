from __future__ import annotations

from pathlib import Path

import pytest

from app.api.schemas import DefectType, Finding, ImageModality, InspectionResult, Priority
from app.ml.video_pipeline import (
    ExtractedFrame,
    FrameInspection,
    aggregate_frame_inspections,
    build_ffmpeg_extract_command,
    discover_extracted_frames,
    percentile,
)


def make_result(
    *,
    priority: Priority,
    risk: float,
    confidence: float,
    findings: list[Finding] | None = None,
) -> InspectionResult:
    return InspectionResult(
        image_modality=ImageModality.INFRARED,
        contains_solar_panel=True,
        inspection_confidence=confidence,
        overall_risk_score=risk,
        priority=priority,
        findings=findings or [],
        human_review_required=True,
        summary=f"{priority.value} frame",
        model_name="test-model",
        model_mode="test",
        latency_ms=25,
    )


def test_build_ffmpeg_extract_command_is_bounded_and_deterministic(tmp_path: Path) -> None:
    command = build_ffmpeg_extract_command(
        video_path=tmp_path / "inspection.mp4",
        output_dir=tmp_path / "frames",
        fps=2,
        max_frames=12,
        ffmpeg_bin="ffmpeg",
    )

    assert command == [
        "ffmpeg",
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(tmp_path / "inspection.mp4"),
        "-vf",
        "fps=2",
        "-frames:v",
        "12",
        str(tmp_path / "frames" / "frame-%06d.jpg"),
    ]


def test_discover_extracted_frames_assigns_timestamps(tmp_path: Path) -> None:
    frames_dir = tmp_path / "frames"
    frames_dir.mkdir()
    (frames_dir / "frame-000001.jpg").write_bytes(b"one")
    (frames_dir / "frame-000002.jpg").write_bytes(b"two")

    frames = discover_extracted_frames(output_dir=frames_dir, fps=0.5)

    assert [frame.frame_index for frame in frames] == [0, 1]
    assert [frame.timestamp_ms for frame in frames] == [0, 2000]
    assert all(frame.sha256 for frame in frames)


def test_aggregate_frame_inspections_uses_highest_risk_frame_and_counts_findings(tmp_path: Path) -> None:
    hotspot = Finding(
        defect_type=DefectType.HOTSPOT,
        severity=Priority.HIGH,
        confidence=0.71,
        location_hint="frame center",
        visual_evidence="thermal hotspot",
        recommended_action="review string telemetry",
    )
    frame_inspections = [
        FrameInspection(
            frame=ExtractedFrame(frame_index=0, timestamp_ms=0, path=tmp_path / "frame-000001.jpg"),
            result=make_result(priority=Priority.LOW, risk=0.1, confidence=0.8),
        ),
        FrameInspection(
            frame=ExtractedFrame(frame_index=1, timestamp_ms=1000, path=tmp_path / "frame-000002.jpg"),
            result=make_result(priority=Priority.HIGH, risk=0.82, confidence=0.71, findings=[hotspot]),
        ),
        FrameInspection(
            frame=ExtractedFrame(frame_index=2, timestamp_ms=2000, path=tmp_path / "frame-000003.jpg"),
            result=make_result(priority=Priority.INCONCLUSIVE, risk=0.0, confidence=0.2),
            error="model output invalid",
        ),
    ]

    summary = aggregate_frame_inspections(frame_inspections)

    assert summary["frames_analyzed"] == 3
    assert summary["frames_with_findings"] == 1
    assert summary["frames_with_errors"] == 1
    assert summary["priority"] == "high"
    assert summary["max_overall_risk_score"] == 0.82
    assert summary["defect_type_counts"] == {"hotspot": 1}
    assert summary["representative_frame"]["frame_index"] == 1
    assert summary["human_review_required"] is True


def test_percentile_interpolates_values() -> None:
    assert percentile([0.0, 0.5, 1.0], 0.95) == pytest.approx(0.95)
