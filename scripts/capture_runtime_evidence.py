from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from app.ml.runtime_evidence import collect_runtime_evidence, write_runtime_evidence  # noqa: E402


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Capture safe runtime evidence for AMD ROCm / MI300X Orvex runs."
    )
    parser.add_argument("--output", required=True, help="Output JSON path.")
    parser.add_argument("--torch-smoke", action="store_true", help="Run a small torch matmul on GPU if available.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    payload = collect_runtime_evidence(run_torch_smoke=args.torch_smoke)
    write_runtime_evidence(Path(args.output), payload)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
