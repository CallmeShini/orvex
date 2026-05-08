# RaptorMaps Supervised Baseline on ROCm

Updated: 2026-05-08

This runbook defines the next controlled ML step for Orvex: a supervised RaptorMaps baseline trained and evaluated on the AMD MI300X VPS with ROCm. It is a measurable comparator and possible low-latency fallback, not a replacement for Qwen2.5-VL or human review.

## Objective

Train a small supervised image classifier on RaptorMaps InfraredSolarModules and expose its result through the existing Orvex `InspectionResult` contract.

First success means:

- deterministic train/eval split and reproducible run config;
- saved artifact bundle with labels, preprocessing, metrics, and environment metadata;
- ROCm/MI300X evidence proving the run used the target AMD stack;
- one FastAPI smoke path proving the artifact can feed Streamlit through the existing product flow.

## Architecture

```txt
RaptorMaps raw data
-> deterministic split and manifest
-> supervised training on ROCm / MI300X
-> ignored artifact bundle
-> FastAPI baseline adapter
-> Streamlit result view
```

Training starts deliberately small: a purpose-built PyTorch CNN over the native 24x40 thermal crop. Avoid heavy fine-tuning, ensembles, or new product schemas until this baseline has a clean evaluation story.

Default artifact targets, ignored by Git:

```txt
data/models/raptormaps_classifier.pt
data/metrics/raptormaps_classifier_metrics.json
```

The `.pt` bundle must include:

- model state dict;
- class labels;
- preprocessing image size;
- training history;
- final held-out metrics;
- run metadata with ROCm/PyTorch/device details.

The metrics JSON must include class distribution, train/validation distribution, per-class precision/recall/F1, confusion matrix, throughput, hardware metadata, seed, batch size, image size, epochs, and train/eval wall-clock time.

## FastAPI and Streamlit Contract

The FastAPI adapter loads the artifact lazily with `AI_MODE=classifier` or `AI_MODE=raptormaps_classifier` and returns the existing `InspectionResult` schema.

Mapping rules:

- high-confidence known class maps to a suspected defect, priority, and human-review state;
- low confidence maps to `priority=inconclusive`;
- preprocessing or model-load failure must be explicit, not a silent success;
- model-specific probabilities can be logged, but the public API contract remains Orvex's existing schema.

Streamlit should display model mode, suspected class or Orvex bucket, confidence/probability, human-review requirement, and a short caveat that this is a supervised baseline. Do not show benchmark numbers until they come from a recorded held-out run.

## AMD / ROCm Evidence

Capture evidence under:

```txt
logs/evidence/raptormaps-baseline-<run_id>/
```

Required evidence files:

- `git.txt`: commit and dirty-state snapshot.
- `rocminfo.txt`: HSA agents and MI300X/gfx target evidence.
- `amd-smi-version.txt`, `amd-smi-list.json`, `amd-smi-static.json`: GPU inventory.
- `amd-smi-monitor-train.txt`: utilization, power, temperature, and VRAM during training.
- `torch-env.txt`: `python -m torch.utils.collect_env`.
- `torch-device.txt`: `torch.cuda.is_available()`, `torch.version.hip`, device count, and device name.
- `pip-freeze.txt`: Python package inventory.
- `train.log`: epoch loss, validation metrics, batch size, precision, and wall-clock time.
- `metrics.json`: held-out accuracy, macro F1, per-class precision/recall/F1, and confusion matrix.
- `api-smoke.json`: future FastAPI response from the saved artifact.

Prefer `amd-smi` for new evidence. Keep `rocm-smi` only as a fallback if the VPS image does not provide `amd-smi`.

## Expected VPS Commands

Run from the canonical VPS workspace:

```bash
cd /workspace/orvex
git status --short
git rev-parse HEAD
.venv/bin/python -m pip install -r requirements-vps.txt
.venv/bin/python scripts/install_datasets.py --datasets raptormaps
```

Capture run evidence:

```bash
RUN_ID="raptormaps-baseline-$(date -u +%Y%m%dT%H%M%SZ)"
EVIDENCE_DIR="logs/evidence/${RUN_ID}"
mkdir -p "${EVIDENCE_DIR}"

git rev-parse HEAD > "${EVIDENCE_DIR}/git.txt"
git status --short >> "${EVIDENCE_DIR}/git.txt"
rocminfo > "${EVIDENCE_DIR}/rocminfo.txt"
amd-smi version > "${EVIDENCE_DIR}/amd-smi-version.txt" || true
amd-smi list --json > "${EVIDENCE_DIR}/amd-smi-list.json" || true
amd-smi static --json > "${EVIDENCE_DIR}/amd-smi-static.json" || true
.venv/bin/python -m torch.utils.collect_env > "${EVIDENCE_DIR}/torch-env.txt"
.venv/bin/python - <<'PY' > "${EVIDENCE_DIR}/torch-device.txt"
import torch
print("torch", torch.__version__)
print("cuda_available", torch.cuda.is_available())
print("hip", getattr(torch.version, "hip", None))
print("device_count", torch.cuda.device_count())
if torch.cuda.is_available():
    print("device0", torch.cuda.get_device_name(0))
PY
.venv/bin/python -m pip freeze > "${EVIDENCE_DIR}/pip-freeze.txt"
```

Training command:

```bash
amd-smi monitor --watch 1 --watch_time 120 > "${EVIDENCE_DIR}/amd-smi-monitor-train.txt" &
MONITOR_PID=$!

.venv/bin/python scripts/train_raptormaps_classifier.py \
  --data-root data/external/raptormaps/raw/InfraredSolarModules \
  --output data/models/raptormaps_classifier.pt \
  --metrics-output data/metrics/raptormaps_classifier_metrics.json \
  --seed 42 \
  --epochs 10 \
  --batch-size 512 \
  2>&1 | tee "${EVIDENCE_DIR}/train.log"

kill "${MONITOR_PID}" || true
```

Prediction smoke:

```bash
.venv/bin/python scripts/predict_raptormaps_classifier.py \
  --artifact data/models/raptormaps_classifier.pt \
  --sample-id 6722 \
  > "${EVIDENCE_DIR}/classifier-smoke.json"
```

Contract smoke:

```bash
.venv/bin/python scripts/smoke_raptormaps_classifier.py \
  --artifact data/models/raptormaps_classifier.pt \
  --sample raptormaps-hot_spot-06722 \
  --output "${EVIDENCE_DIR}/api-smoke.json"
```

Optional live API smoke:

```bash
AI_MODE=classifier \
ORVEX_CLASSIFIER_ARTIFACT=data/models/raptormaps_classifier.pt \
  .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8010
```

Save one FastAPI response as `logs/evidence/<run_id>/fastapi-response.json` if the live API is started.

## Claim Boundaries

Allowed after one clean run:

- "We trained a supervised RaptorMaps baseline on AMD MI300X/ROCm."
- "The run produced a versioned artifact and held-out evaluation report."
- "The artifact plugs into the existing FastAPI/Streamlit contract through `AI_MODE=classifier`."

Not allowed without stronger validation:

- production accuracy claims;
- transfer claims from public RaptorMaps data to customer drone imagery;
- safety, warranty, insurance, or autonomous maintenance claims;
- comparison against human inspectors;
- claims that the baseline replaces the VLM or human review.

## References

- ROCm `rocminfo`: https://rocm.docs.amd.com/projects/rocminfo/en/docs-7.2.0/how-to/use-rocminfo.html
- AMD SMI CLI: https://rocm.docs.amd.com/projects/amdsmi/en/develop/how-to/amdsmi-cli-tool.html
- PyTorch on ROCm installation: https://rocm.docs.amd.com/projects/install-on-linux/en/latest/install/3rd-party/pytorch-install.html
- PyTorch HIP semantics: https://docs.pytorch.org/docs/2.11/notes/hip.html
