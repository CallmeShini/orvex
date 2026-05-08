from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.api.ai_service import AiServiceError, OrvexAIService  # noqa: E402
from app.ml.runtime_evidence import collect_runtime_evidence, write_runtime_evidence  # noqa: E402
from app.ml.video_pipeline import (  # noqa: E402
    DEFAULT_MAX_FRAMES,
    DEFAULT_VIDEO_FPS,
    ExtractedFrame,
    FrameInspection,
    extract_video_frames,
    video_evaluation_payload,
    write_frame_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Offline video evaluation for Orvex: local video path -> extracted frames -> "
            "frame InspectionResult records -> aggregated triage JSON."
        )
    )
    parser.add_argument("--video", required=True, help="Local source video path. URLs are intentionally unsupported.")
    parser.add_argument("--output-dir", required=True, help="Run output directory under ignored logs/evidence/.")
    parser.add_argument("--sample-fps", type=float, default=DEFAULT_VIDEO_FPS)
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    parser.add_argument("--ai-mode", default=None, help="Override AI_MODE for frame evaluation.")
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--force", action="store_true", help="Replace existing frames and JSON outputs.")
    parser.add_argument("--continue-on-error", action="store_true", help="Record inconclusive frames instead of failing.")
    parser.add_argument("--capture-rocm-evidence", action="store_true", help="Capture AMD/ROCm runtime evidence JSON.")
    parser.add_argument("--torch-smoke", action="store_true", help="Run a small torch GPU matmul during evidence capture.")
    return parser.parse_args()


def reject_url(video: str) -> None:
    lowered = video.lower()
    if lowered.startswith(("http://", "https://", "s3://", "gs://")):
        raise ValueError("Video input must be a local file path. Remote URLs are intentionally unsupported.")


def inspect_frames(
    *,
    frames: list[ExtractedFrame],
    service: OrvexAIService,
    continue_on_error: bool,
) -> list[FrameInspection]:
    inspections: list[FrameInspection] = []
    for frame in frames:
        try:
            result = service.analyze_image(filename=frame.path.name, image_path=frame.path)
            inspections.append(FrameInspection(frame=frame, result=result))
        except AiServiceError as exc:
            if not continue_on_error:
                raise
            result = service.inconclusive_result(raw_output=str(exc))
            inspections.append(FrameInspection(frame=frame, result=result, error=str(exc)))
    return inspections


def run_metadata(args: argparse.Namespace, frames: list[ExtractedFrame]) -> dict[str, Any]:
    return {
        "ai_mode": args.ai_mode or os.getenv("AI_MODE", "mock"),
        "sample_fps": args.sample_fps,
        "max_frames": args.max_frames,
        "frames_analyzed": len(frames),
        "claim_boundary": (
            "Offline frame evaluation only. API/UI video upload remains disabled until "
            "asynchronous job processing, codec limits, and quality evaluation are complete."
        ),
    }


def main() -> None:
    args = parse_args()
    reject_url(args.video)
    video_path = Path(args.video).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    frames_dir = output_dir / "frames"
    manifest_path = output_dir / "frames_manifest.json"
    evaluation_path = output_dir / "video_evaluation.json"
    evidence_path = output_dir / "runtime_evidence.json"

    if evaluation_path.exists() and not args.force:
        raise FileExistsError(f"Output already exists: {evaluation_path}. Use --force to replace it.")

    frames = extract_video_frames(
        video_path=video_path,
        output_dir=frames_dir,
        fps=args.sample_fps,
        max_frames=args.max_frames,
        overwrite=args.force,
        ffmpeg_bin=args.ffmpeg_bin,
    )
    write_frame_manifest(
        manifest_path=manifest_path,
        video_path=video_path,
        frames=frames,
        fps=args.sample_fps,
        max_frames=args.max_frames,
    )

    service = OrvexAIService(mode=args.ai_mode)
    inspections = inspect_frames(
        frames=frames,
        service=service,
        continue_on_error=args.continue_on_error,
    )
    payload = video_evaluation_payload(
        source_video=video_path,
        frames=frames,
        frame_inspections=inspections,
        run_metadata=run_metadata(args, frames),
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    evaluation_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")

    if args.capture_rocm_evidence:
        evidence = collect_runtime_evidence(run_torch_smoke=args.torch_smoke)
        write_runtime_evidence(evidence_path, evidence)

    print(json.dumps(payload["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
