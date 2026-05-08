from __future__ import annotations

import json
import os
import platform
import shutil
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


RUNTIME_EVIDENCE_SCHEMA_VERSION = "orvex-runtime-evidence-v1"
SAFE_ENV_KEYS = (
    "AI_MODE",
    "ORVEX_CLASSIFIER_ARTIFACT",
    "ORVEX_MAX_NEW_TOKENS",
    "HIP_VISIBLE_DEVICES",
    "ROCR_VISIBLE_DEVICES",
    "CUDA_VISIBLE_DEVICES",
    "PYTORCH_HIP_ALLOC_CONF",
    "HF_HOME",
    "TRANSFORMERS_CACHE",
)


def collect_command(command: list[str], timeout_seconds: int = 20) -> dict[str, Any]:
    binary = command[0]
    resolved = shutil.which(binary)
    if resolved is None:
        return {
            "status": "missing",
            "command": command,
            "returncode": None,
            "stdout": "",
            "stderr": f"{binary} not found in PATH",
        }

    try:
        completed = subprocess.run(command, check=False, capture_output=True, text=True, timeout=timeout_seconds)
    except subprocess.TimeoutExpired as exc:
        return {
            "status": "timeout",
            "command": command,
            "returncode": None,
            "stdout": (exc.stdout or "").strip() if isinstance(exc.stdout, str) else "",
            "stderr": f"Command timed out after {timeout_seconds}s",
        }
    return {
        "status": "ok" if completed.returncode == 0 else "failed",
        "command": command,
        "returncode": completed.returncode,
        "stdout": completed.stdout.strip(),
        "stderr": completed.stderr.strip(),
    }


def collect_safe_environment() -> dict[str, str]:
    return {key: os.environ[key] for key in SAFE_ENV_KEYS if key in os.environ}


def collect_torch_runtime(run_smoke: bool = False) -> dict[str, Any]:
    try:
        import torch
    except ModuleNotFoundError as exc:
        return {
            "status": "missing",
            "error": str(exc),
        }

    payload: dict[str, Any] = {
        "status": "ok",
        "torch_version": torch.__version__,
        "cuda_available": bool(torch.cuda.is_available()),
        "hip_version": getattr(torch.version, "hip", None),
        "cuda_version": getattr(torch.version, "cuda", None),
        "device_count": int(torch.cuda.device_count()),
        "devices": [],
    }
    for index in range(torch.cuda.device_count()):
        payload["devices"].append(
            {
                "index": index,
                "name": torch.cuda.get_device_name(index),
            }
        )

    if run_smoke and torch.cuda.is_available():
        started = datetime.now(UTC)
        device = torch.device("cuda")
        a = torch.ones((512, 512), device=device)
        b = torch.eye(512, device=device)
        c = a @ b
        torch.cuda.synchronize()
        elapsed_ms = (datetime.now(UTC) - started).total_seconds() * 1000
        payload["matmul_smoke"] = {
            "status": "ok",
            "device": str(device),
            "shape": [512, 512],
            "elapsed_ms": round(elapsed_ms, 3),
            "checksum": round(float(c.sum().detach().cpu().item()), 6),
        }
    elif run_smoke:
        payload["matmul_smoke"] = {
            "status": "skipped",
            "reason": "torch.cuda.is_available() returned False",
        }

    return payload


def collect_runtime_evidence(run_torch_smoke: bool = False) -> dict[str, Any]:
    return {
        "schema_version": RUNTIME_EVIDENCE_SCHEMA_VERSION,
        "captured_at": datetime.now(UTC).isoformat(timespec="seconds"),
        "platform": {
            "python": sys.version,
            "executable": sys.executable,
            "system": platform.system(),
            "release": platform.release(),
            "machine": platform.machine(),
        },
        "environment": collect_safe_environment(),
        "torch": collect_torch_runtime(run_smoke=run_torch_smoke),
        "commands": {
            "amd_smi_version": collect_command(["amd-smi", "version"]),
            "amd_smi_list": collect_command(["amd-smi", "list", "--json"]),
            "amd_smi_static": collect_command(["amd-smi", "static", "--json"], timeout_seconds=30),
            "rocm_smi": collect_command(["rocm-smi"], timeout_seconds=30),
            "rocminfo": collect_command(["rocminfo"], timeout_seconds=30),
        },
    }


def write_runtime_evidence(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
