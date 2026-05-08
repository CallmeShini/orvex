from __future__ import annotations

import json
import hashlib
import subprocess
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from statistics import mean
from typing import Any

from app.api.schemas import InspectionResult, Priority


VIDEO_EVALUATION_SCHEMA_VERSION = "orvex-video-evaluation-v1"
DEFAULT_FRAME_PATTERN = "frame-%06d.jpg"
DEFAULT_FRAME_GLOB = "frame-*.jpg"
DEFAULT_VIDEO_FPS = 1.0
DEFAULT_MAX_FRAMES = 48

PRIORITY_RANK = {
    Priority.INCONCLUSIVE: 0,
    Priority.LOW: 1,
    Priority.MEDIUM: 2,
    Priority.HIGH: 3,
    Priority.CRITICAL: 4,
}


class VideoPipelineError(RuntimeError):
    """Raised when the offline video evaluation pipeline cannot continue."""


@dataclass(frozen=True)
class ExtractedFrame:
    frame_index: int
    timestamp_ms: int
    path: Path
    sha256: str | None = None

    def to_json(self) -> dict[str, Any]:
        return {
            "frame_index": self.frame_index,
            "timestamp_ms": self.timestamp_ms,
            "path": str(self.path),
            "sha256": self.sha256,
        }


@dataclass(frozen=True)
class FrameInspection:
    frame: ExtractedFrame
    result: InspectionResult
    error: str | None = None

    def to_json(self) -> dict[str, Any]:
        payload = {
            "frame": self.frame.to_json(),
            "result": self.result.model_dump(mode="json"),
        }
        if self.error:
            payload["error"] = self.error
        return payload


def validate_frame_sampling(fps: float, max_frames: int) -> None:
    if fps <= 0:
        raise ValueError("fps must be greater than 0")
    if max_frames <= 0:
        raise ValueError("max_frames must be greater than 0")


def build_ffmpeg_extract_command(
    *,
    video_path: Path,
    output_dir: Path,
    fps: float = DEFAULT_VIDEO_FPS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    ffmpeg_bin: str = "ffmpeg",
) -> list[str]:
    validate_frame_sampling(fps=fps, max_frames=max_frames)
    return [
        ffmpeg_bin,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-i",
        str(video_path),
        "-vf",
        f"fps={fps}",
        "-frames:v",
        str(max_frames),
        str(output_dir / DEFAULT_FRAME_PATTERN),
    ]


def extract_video_frames(
    *,
    video_path: Path,
    output_dir: Path,
    fps: float = DEFAULT_VIDEO_FPS,
    max_frames: int = DEFAULT_MAX_FRAMES,
    overwrite: bool = False,
    ffmpeg_bin: str = "ffmpeg",
) -> list[ExtractedFrame]:
    video_path = video_path.expanduser().resolve()
    output_dir = output_dir.expanduser().resolve()
    if not video_path.exists():
        raise FileNotFoundError(f"Video file not found: {video_path}")

    output_dir.mkdir(parents=True, exist_ok=True)
    existing_frames = sorted(output_dir.glob(DEFAULT_FRAME_GLOB))
    if existing_frames and not overwrite:
        raise VideoPipelineError(
            f"Frame output directory already contains {len(existing_frames)} frames. "
            "Use --force to replace them."
        )
    if overwrite:
        for frame_path in existing_frames:
            frame_path.unlink()

    command = build_ffmpeg_extract_command(
        video_path=video_path,
        output_dir=output_dir,
        fps=fps,
        max_frames=max_frames,
        ffmpeg_bin=ffmpeg_bin,
    )
    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True)
    except FileNotFoundError as exc:
        raise VideoPipelineError(
            "ffmpeg was not found. Install ffmpeg on the VPS before running video extraction."
        ) from exc

    if completed.returncode != 0:
        raise VideoPipelineError(
            "ffmpeg failed while extracting frames: "
            f"{completed.stderr.strip() or completed.stdout.strip() or 'no output'}"
        )

    frames = discover_extracted_frames(output_dir=output_dir, fps=fps)
    if not frames:
        raise VideoPipelineError(f"ffmpeg completed but no frames were written to {output_dir}")
    return frames


def discover_extracted_frames(*, output_dir: Path, fps: float = DEFAULT_VIDEO_FPS) -> list[ExtractedFrame]:
    validate_frame_sampling(fps=fps, max_frames=1)
    frame_paths = sorted(output_dir.expanduser().resolve().glob(DEFAULT_FRAME_GLOB))
    frame_interval_ms = 1000 / fps
    return [
        ExtractedFrame(
            frame_index=index,
            timestamp_ms=int(round(index * frame_interval_ms)),
            path=frame_path,
            sha256=sha256_file(frame_path),
        )
        for index, frame_path in enumerate(frame_paths)
    ]


def write_frame_manifest(
    *,
    manifest_path: Path,
    video_path: Path,
    frames: list[ExtractedFrame],
    fps: float,
    max_frames: int,
) -> dict[str, Any]:
    payload = {
        "schema_version": VIDEO_EVALUATION_SCHEMA_VERSION,
        "video_path": str(video_path),
        "fps": fps,
        "max_frames": max_frames,
        "frame_count": len(frames),
        "frames": [frame.to_json() for frame in frames],
    }
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return payload


def load_frame_manifest(manifest_path: Path) -> list[ExtractedFrame]:
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    frames = []
    for item in payload.get("frames", []):
        frames.append(
            ExtractedFrame(
                frame_index=int(item["frame_index"]),
                timestamp_ms=int(item["timestamp_ms"]),
                path=Path(item["path"]),
                sha256=item.get("sha256"),
            )
        )
    return frames


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def aggregate_frame_inspections(frame_inspections: list[FrameInspection]) -> dict[str, Any]:
    if not frame_inspections:
        raise ValueError("frame_inspections must not be empty")

    priorities = [inspection.result.priority for inspection in frame_inspections]
    max_priority = max(priorities, key=lambda priority: PRIORITY_RANK[priority])
    risk_scores = [inspection.result.overall_risk_score for inspection in frame_inspections]
    confidences = [inspection.result.inspection_confidence for inspection in frame_inspections]
    sorted_risks = sorted(risk_scores)
    top_k_risks = sorted_risks[-min(5, len(sorted_risks)) :]
    latencies = [
        inspection.result.latency_ms
        for inspection in frame_inspections
        if inspection.result.latency_ms is not None
    ]
    defect_counts = Counter(
        finding.defect_type.value
        for inspection in frame_inspections
        for finding in inspection.result.findings
    )
    model_modes = Counter(inspection.result.model_mode for inspection in frame_inspections)
    representative = max(
        frame_inspections,
        key=lambda inspection: (
            PRIORITY_RANK[inspection.result.priority],
            inspection.result.overall_risk_score,
            inspection.result.inspection_confidence,
        ),
    )

    return {
        "schema_version": VIDEO_EVALUATION_SCHEMA_VERSION,
        "frames_analyzed": len(frame_inspections),
        "frames_with_findings": sum(1 for inspection in frame_inspections if inspection.result.findings),
        "frames_with_errors": sum(1 for inspection in frame_inspections if inspection.error),
        "frames_requiring_human_review": sum(
            1 for inspection in frame_inspections if inspection.result.human_review_required
        ),
        "priority": max_priority.value,
        "max_overall_risk_score": round(max(risk_scores), 6),
        "p95_overall_risk_score": round(percentile(sorted_risks, 0.95), 6),
        "top_k_mean_overall_risk_score": round(mean(top_k_risks), 6),
        "mean_overall_risk_score": round(mean(risk_scores), 6),
        "mean_inspection_confidence": round(mean(confidences), 6),
        "defect_type_counts": dict(sorted(defect_counts.items())),
        "model_mode_counts": dict(sorted(model_modes.items())),
        "latency_ms_total": sum(latencies) if latencies else None,
        "latency_ms_mean": round(mean(latencies), 3) if latencies else None,
        "representative_frame": {
            "frame_index": representative.frame.frame_index,
            "timestamp_ms": representative.frame.timestamp_ms,
            "inspection_id": representative.result.inspection_id,
            "priority": representative.result.priority.value,
            "overall_risk_score": representative.result.overall_risk_score,
            "summary": representative.result.summary,
        },
        "human_review_required": any(
            inspection.result.human_review_required for inspection in frame_inspections
        ),
    }


def percentile(sorted_values: list[float], quantile: float) -> float:
    if not sorted_values:
        raise ValueError("sorted_values must not be empty")
    if quantile <= 0:
        return sorted_values[0]
    if quantile >= 1:
        return sorted_values[-1]

    position = (len(sorted_values) - 1) * quantile
    lower_index = int(position)
    upper_index = min(lower_index + 1, len(sorted_values) - 1)
    fraction = position - lower_index
    return sorted_values[lower_index] + ((sorted_values[upper_index] - sorted_values[lower_index]) * fraction)


def video_evaluation_payload(
    *,
    source_video: Path | None,
    frames: list[ExtractedFrame],
    frame_inspections: list[FrameInspection],
    run_metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "schema_version": VIDEO_EVALUATION_SCHEMA_VERSION,
        "source_video": str(source_video) if source_video else None,
        "frame_count": len(frames),
        "summary": aggregate_frame_inspections(frame_inspections),
        "run_metadata": run_metadata or {},
        "frames": [inspection.to_json() for inspection in frame_inspections],
    }
