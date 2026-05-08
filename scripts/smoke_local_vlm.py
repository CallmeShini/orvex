from __future__ import annotations

import argparse
from pathlib import Path

from app.api.ai_service import OrvexAIService


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run one local VLM smoke test through the Orvex contract.")
    parser.add_argument("--sample", default=None, help="Dataset sample id available through /samples.")
    parser.add_argument("--image", default=None, help="Path to an image file to upload/analyze.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    service = OrvexAIService(mode="local")

    if args.image:
        image_path = Path(args.image).expanduser().resolve()
        with image_path.open("rb") as handle:
            result = service.analyze_image(filename=image_path.name, file_obj=handle)
    else:
        result = service.analyze_image(sample_name=args.sample)

    print(result.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
