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
from app.ml.video_pipeline import (  # noqa: E402
    ExtractedFrame,
    FrameInspection,
    discover_extracted_frames,
    load_frame_manifest,
    video_evaluation_payload,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Run offline Orvex inspection over extracted video frames and aggregate the result."
    )
    source_group = parser.add_mutually_exclusive_group(required=True)
    source_group.add_argument("--manifest", help="Frame manifest produced by scripts/extract_video_frames.py.")
    source_group.add_argument("--frames-dir", help="Directory containing frame-*.jpg files.")
    parser.add_argument("--video", default=None, help="Optional source video path for traceability.")
    parser.add_argument("--fps", type=float, default=1.0, help="Sampling FPS used when --frames-dir is provided.")
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--ai-mode", default=None, help="Override AI_MODE for this run.")
    parser.add_argument("--continue-on-error", action="store_true", help="Record inconclusive frames instead of failing.")
    return parser.parse_args()


def load_frames(args: argparse.Namespace) -> list[ExtractedFrame]:
    if args.manifest:
        frames = load_frame_manifest(Path(args.manifest))
    else:
        frames = discover_extracted_frames(output_dir=Path(args.frames_dir), fps=args.fps)
    if not frames:
        raise ValueError("No frames were found for evaluation.")
    return frames


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


def build_run_metadata(args: argparse.Namespace, frames: list[ExtractedFrame]) -> dict[str, Any]:
    return {
        "ai_mode": args.ai_mode or os.getenv("AI_MODE", "mock"),
        "manifest": args.manifest,
        "frames_dir": args.frames_dir,
        "fps": args.fps,
        "frame_count": len(frames),
        "claim_boundary": (
            "Offline frame evaluation only. This is not public video-upload support and "
            "does not imply production accuracy."
        ),
    }


def main() -> None:
    args = parse_args()
    frames = load_frames(args)
    service = OrvexAIService(mode=args.ai_mode)
    inspections = inspect_frames(
        frames=frames,
        service=service,
        continue_on_error=args.continue_on_error,
    )
    output = video_evaluation_payload(
        source_video=Path(args.video) if args.video else None,
        frames=frames,
        frame_inspections=inspections,
        run_metadata=build_run_metadata(args, frames),
    )
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    print(json.dumps(output["summary"], indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
