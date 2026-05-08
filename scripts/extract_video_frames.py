from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ml.video_pipeline import (  # noqa: E402
    DEFAULT_MAX_FRAMES,
    DEFAULT_VIDEO_FPS,
    extract_video_frames,
    write_frame_manifest,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract a bounded frame set from a solar inspection video for offline Orvex evaluation."
    )
    parser.add_argument("--video", required=True, help="Path to the source video.")
    parser.add_argument("--output-dir", required=True, help="Directory where extracted frames will be written.")
    parser.add_argument("--manifest", default=None, help="Optional manifest path. Defaults to <output-dir>/manifest.json.")
    parser.add_argument("--fps", type=float, default=DEFAULT_VIDEO_FPS)
    parser.add_argument("--max-frames", type=int, default=DEFAULT_MAX_FRAMES)
    parser.add_argument("--ffmpeg-bin", default="ffmpeg")
    parser.add_argument("--force", action="store_true", help="Replace existing frame files in output-dir.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    output_dir = Path(args.output_dir)
    manifest_path = Path(args.manifest) if args.manifest else output_dir / "manifest.json"
    frames = extract_video_frames(
        video_path=Path(args.video),
        output_dir=output_dir,
        fps=args.fps,
        max_frames=args.max_frames,
        overwrite=args.force,
        ffmpeg_bin=args.ffmpeg_bin,
    )
    payload = write_frame_manifest(
        manifest_path=manifest_path,
        video_path=Path(args.video),
        frames=frames,
        fps=args.fps,
        max_frames=args.max_frames,
    )
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
