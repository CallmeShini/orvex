# VPS Inference Runbook

Updated: 2026-05-08

This runbook connects the local Orvex product flow to real GPU inference on the AMD MI300X VPS.

## Current Target

- Runtime mode: `AI_MODE=local`
- Default model: `Qwen/Qwen2.5-VL-7B-Instruct`
- Inference stack: PyTorch ROCm + Hugging Face Transformers
- Product contract: `InspectionResult`
- Model reference: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct

## Why This Path

The app already has a stable mock and dataset expected-output mode. The VPS step should only replace the model execution layer, not the API contract or UI flow.

The local VLM adapter:

- loads Qwen2.5-VL lazily;
- sends one image plus the Orvex structured JSON prompt;
- parses the raw text response as JSON;
- validates the result with Pydantic;
- returns an explicit failure when the model output cannot be trusted.

## VPS Commands

Run inside `/workspace/orvex` on the GPU host.

```bash
git pull
.venv/bin/python -m pip install -r requirements-vps.txt
```

For the public Git clone used during the hackathon, run from `/workspace/orvex-git` if that is the active clean repo checkout. Keep `/workspace/orvex` and team workspaces untouched unless the team explicitly agrees to migrate them.

## Dataset Install

Install the project-relevant solar datasets under the ignored `data/external/` tree:

```bash
.venv/bin/python scripts/install_datasets.py
```

The installer:

- downloads direct public datasets from GitHub/Zenodo;
- verifies available MD5 checksums for Zenodo archives;
- extracts archives with zip-slip protection;
- attempts Kaggle datasets only when Kaggle CLI credentials are present;
- writes `data/external/_manifests/dataset_install_manifest.json`.

Kaggle credential files such as `~/.kaggle/kaggle.json` must never be copied into this repository or committed.

Verify GPU/PyTorch first:

```bash
.venv/bin/python - <<'PY'
import torch
print("torch", torch.__version__)
print("cuda available", torch.cuda.is_available())
print("hip", getattr(torch.version, "hip", None))
print("device count", torch.cuda.device_count())
if torch.cuda.is_available():
    print("device0", torch.cuda.get_device_name(0))
PY
```

Run one smoke test with a local image:

```bash
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/python scripts/smoke_local_vlm.py --image /path/to/panel-image.jpg
```

Run one smoke test with a RaptorMaps sample only if the raw dataset exists on the VPS:

```bash
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/python scripts/smoke_local_vlm.py --sample raptormaps-hot_spot-06722
```

Start the API in local model mode:

```bash
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8010
```

## Operational Constraints

- Do not claim measured accuracy from a smoke test.
- Keep `mock` as the default mode for stable demos.
- Use `local` only when GPU dependencies and model weights are available.
- Treat invalid model JSON as a product failure, not as a partial success.
- Keep raw datasets and downloaded model weights out of Git.

## First Success Criteria

- `torch.cuda.is_available()` returns `True`.
- Qwen2.5-VL loads without `qwen2_5_vl` registry errors.
- `scripts/smoke_local_vlm.py` returns one valid `InspectionResult` JSON.
- The API can run with `AI_MODE=local`.
- The UI shows `Model mode: local` for an analyzed image.
