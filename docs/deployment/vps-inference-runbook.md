# VPS Inference Runbook

Updated: 2026-05-08

This runbook connects the local Orvex product flow to real GPU inference on the AMD MI300X VPS.

## Current Target

- Runtime mode: `AI_MODE=local`
- Default model: `Qwen/Qwen2.5-VL-7B-Instruct`
- Inference stack: PyTorch ROCm + Hugging Face Transformers
- Product contract: `InspectionResult`
- Model reference: https://huggingface.co/Qwen/Qwen2.5-VL-7B-Instruct

## Next Baseline Runbook

The supervised RaptorMaps baseline is documented separately because it is a training-and-artifact workflow, not a VLM inference smoke test:

```txt
docs/ml/raptormaps-supervised-baseline-rocm.md
```

Use that runbook when the next VPS step is to capture a reproducible ROCm/MI300X supervised training baseline, artifact bundle, and cautious FastAPI/Streamlit integration path.

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

Run the curated RaptorMaps smoke batch. This writes ignored JSON result files under `data/external/smoke_results/`:

```bash
HF_HOME=/workspace/orvex-git/data/external/hf-cache \
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/python scripts/smoke_local_vlm_batch.py
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

## Offline Video Evidence Run

The offline path is still the recommended VPS evidence run because it captures ROCm/MI300X runtime proof. API video upload is disabled by default and should only be enabled for explicit experimental bounded-frame tests.

Verify `ffmpeg` resolution. The app checks this order:

```txt
1. ORVEX_FFMPEG_BIN when set
2. ffmpeg from PATH
3. imageio-ffmpeg from the Python venv
```

```bash
cd /workspace/orvex
.venv/bin/python -c "from app.ml.video_pipeline import resolve_ffmpeg_bin; print(resolve_ffmpeg_bin())"
```

If the VPS has ffmpeg installed outside PATH:

```bash
export ORVEX_FFMPEG_BIN=/opt/ffmpeg/bin/ffmpeg
```

If using system `ffmpeg`, this should also work:

```bash
ffmpeg -version
```

Run a bounded video/frame evaluation:

```bash
cd /workspace/orvex
RUN_ID="video-eval-$(date -u +%Y%m%dT%H%M%SZ)"
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/python scripts/evaluate_video_offline.py \
  --video /workspace/private-videos/inspection.mp4 \
  --output-dir "logs/evidence/${RUN_ID}" \
  --sample-fps 1 \
  --max-frames 120 \
  --capture-rocm-evidence \
  --torch-smoke
```

Expected ignored outputs:

```txt
logs/evidence/${RUN_ID}/frames/
logs/evidence/${RUN_ID}/frames_manifest.json
logs/evidence/${RUN_ID}/video_evaluation.json
logs/evidence/${RUN_ID}/runtime_evidence.json
```

Quick evidence checks:

```bash
jq '.summary' "logs/evidence/${RUN_ID}/video_evaluation.json"
jq '.torch, .commands.amd_smi_list.status, .commands.rocminfo.status' \
  "logs/evidence/${RUN_ID}/runtime_evidence.json"
rg -n "MI300X|AMD Instinct|HIP|ROCm|gfx" "logs/evidence/${RUN_ID}/runtime_evidence.json"
```

Claim boundary:

```txt
Offline video evidence and experimental bounded video jobs use timestamped frames and the Orvex inspection contract.
Not arbitrary unbounded public video ingestion, not production diagnostic accuracy,
and not autonomous maintenance.
```

Experimental API video smoke test:

```bash
ORVEX_ENABLE_VIDEO_UPLOAD=true \
ORVEX_VIDEO_PROCESSING_MODE=background \
AI_MODE=classifier \
ORVEX_CLASSIFIER_ARTIFACT=data/models/raptormaps_classifier.pt \
  .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8010
```
