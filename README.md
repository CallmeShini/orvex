# Orvex

Orvex is an AI-assisted inspection copilot for photovoltaic operations and maintenance teams.

The product turns solar inspection imagery into prioritized, human-reviewable maintenance findings. The initial hackathon scope focuses on thermal and RGB solar panel images, structured VLM analysis, risk prioritization, and exportable inspection reports.

## Product Position

Orvex is not a definitive diagnostic system and does not replace field technicians. It is a human-in-the-loop triage workflow for accelerating review, surfacing visual evidence, and standardizing preliminary maintenance reports.

## Current Phase

This repository is the execution source of truth for product, architecture, AI contracts, datasets, and demo planning.

The GPU VPS is reserved for serious model validation and inference work only. Product planning, contracts, local mock flows, documentation, and reviewable implementation should happen outside the VPS first.

## Repository Map

```txt
app/
  api/
    main.py
    schemas.py
    ai_service.py
    json_utils.py
    report_service.py
  ml/
    raptormaps_classifier.py
    runtime_evidence.py
    video_pipeline.py
  ui/
    streamlit_app.py
frontend/
  app/
    api/orvex/[...path]/route.ts
    page.tsx
  components/
    orvex-workspace.tsx
data/
  evaluation/
    raptormaps_manifest.jsonl
    expected_outputs/
  jobs/
  samples/
  reports/
docs/
  product/
    product-brief.md
    mvp-scope.md
  architecture/
    architecture-principles.md
  ai-contracts/
    vlm-contract-v1.md
  datasets/
    dataset-registry.md
  ml/
    raptormaps-supervised-baseline-rocm.md
    video-frame-evaluation-rocm.md
  frontend/
    nextjs-product-interface.md
  demo/
    submission-checklist.md
scripts/
  capture_runtime_evidence.py
  evaluate_video_offline.py
  evaluate_video_frames.py
  extract_video_frames.py
  install_datasets.py
  train_raptormaps_classifier.py
  smoke_local_vlm.py
```

## Near-Term Goal

Build a production-compatible hackathon MVP:

```txt
upload images
-> inspection job
-> multimodal analysis or transparent mock fallback
-> validated JSON
-> risk prioritization
-> human review
-> exportable report
```

## Operating Rules

- Keep product decisions documented before implementation.
- Do not use the VPS as a scratch environment.
- Keep VLM behavior constrained by versioned prompts and schemas.
- Treat all model outputs as suggestions that require validation and human review.
- Avoid claims about accuracy, autonomy, certification, or commercial readiness without evidence.

## Local Day 1 Demo

The current build runs in `AI_MODE=mock`. It does not require the GPU VPS.

### Setup

```bash
python3.11 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

### Run API

```bash
AI_MODE=mock uvicorn app.api.main:app --host 127.0.0.1 --port 8000
```

### Run Next.js UI

Open a second terminal:

```bash
cd frontend
ORVEX_API_URL=http://127.0.0.1:8000 npm run dev -- --hostname 127.0.0.1 --port 3000
```

Then open:

```txt
http://127.0.0.1:3000
```

The Next.js app is the canonical presentation/product interface. It calls FastAPI through its own `/api/orvex/*` proxy route so browser clients do not need direct CORS access to the Python service.

## Inspection Job API

The product-compatible API path is:

```txt
POST /inspection-jobs
GET /inspection-jobs/{job_id}
```

`POST /inspection-jobs` currently processes image or curated-sample jobs synchronously and returns a completed job envelope with the same validated `InspectionResult` used by `/analyze`.

The legacy `/analyze` endpoint remains available for compatibility with older demo clients. Video files are still intentionally rejected by the public API/UI. The repository now has an offline frame-evaluation pipeline for controlled VPS evidence runs, but that is not public video-upload support.

### Legacy Streamlit UI

Open a second terminal:

```bash
source .venv/bin/activate
ORVEX_API_URL=http://127.0.0.1:8000 streamlit run app/ui/streamlit_app.py --server.port 8501
```

Then open:

```txt
http://localhost:8501
```

### Validate

```bash
source .venv/bin/activate
pytest
curl http://127.0.0.1:8000/health
curl http://127.0.0.1:8000/samples
```

## Demo Boundary

Mock mode is intentionally transparent. It exists so the user flow, report generation, JSON contract, and presentation can be validated before using MI300X inference.

## Dataset Intake

The first real dataset intake uses RaptorMaps InfraredSolarModules.

Raw data is stored locally under `data/external/raptormaps/` and is ignored by Git. The repository only tracks the small evaluation artifacts:

```txt
data/evaluation/raptormaps_manifest.jsonl
data/evaluation/expected_outputs/
```

The manifest contains 24 selected RaptorMaps samples, two per source class, with source label, Orvex bucket, license, and local image path. The expected outputs are curated contract examples, not model predictions.

To download the raw RaptorMaps dataset locally:

```bash
mkdir -p data/external/raptormaps
curl -L https://github.com/RaptorMaps/InfraredSolarModules/raw/master/2020-02-14_InfraredSolarModules.zip \
  -o data/external/raptormaps/2020-02-14_InfraredSolarModules.zip
unzip -q -o data/external/raptormaps/2020-02-14_InfraredSolarModules.zip \
  -d data/external/raptormaps/raw
```

When the raw data exists locally, the Streamlit UI can preview the selected RaptorMaps samples. If the raw data is absent, the API can still use the expected JSON outputs.

## Official Demo Path

The local UI includes an official demo path with five curated RaptorMaps reference outputs and one mock fallback:

```txt
1. raptormaps-no_anomaly-10000
2. raptormaps-soiling-08157
3. raptormaps-cracking-06971
4. raptormaps-hot_spot-06722
5. raptormaps-offline_module-00000
6. inconclusive
```

See `docs/demo/demo-path.md` for the walkthrough script and claim boundaries.

## GPU Inference Mode

The default mode remains `AI_MODE=mock` for stable local demos. The GPU path is implemented behind `AI_MODE=local` and validates Qwen2.5-VL output against the same Orvex `InspectionResult` contract.

VPS runbook:

```txt
docs/deployment/vps-inference-runbook.md
```

Smoke test command on the GPU host:

```bash
AI_MODE=local ORVEX_MAX_NEW_TOKENS=700 \
  .venv/bin/python scripts/smoke_local_vlm.py --sample raptormaps-hot_spot-06722
```

## Supervised RaptorMaps Baseline

The RaptorMaps supervised baseline is a PyTorch/ROCm training path for the MI300X VPS. It is a measurable classifier stage for the 24x40 infrared dataset, not a replacement for Qwen2.5-VL or human review.

Artifacts and metrics are ignored by Git:

```txt
data/models/raptormaps_classifier.pt
data/metrics/raptormaps_classifier_metrics.json
```

Runbook:

```txt
docs/ml/raptormaps-supervised-baseline-rocm.md
```

After training on the VPS, the artifact can feed the existing API contract with:

```bash
AI_MODE=classifier \
ORVEX_CLASSIFIER_ARTIFACT=data/models/raptormaps_classifier.pt \
  .venv/bin/python scripts/smoke_raptormaps_classifier.py --sample raptormaps-hot_spot-06722
```

Evaluate a trained artifact against the curated 24-sample Orvex manifest:

```bash
.venv/bin/python scripts/evaluate_raptormaps_classifier_samples.py \
  --artifact data/models/raptormaps_classifier.pt
```

Validated MI300X/ROCm baseline run:

- Commit: `b2d5378`
- GPU: AMD Instinct MI300X VF
- Runtime: PyTorch `2.9.1+rocm6.4`, HIP `6.4.43484`
- Dataset: 20,000 RaptorMaps records, 16,000 train / 4,000 validation
- Canonical 10-epoch run: validation accuracy `0.4775`, macro recall `0.346012`, macro F1 `0.31931`
- Follow-up 15-epoch sweep: class-weight power `0.5` gave the best balanced result, with accuracy `0.67225`, macro recall `0.380194`, macro F1 `0.411179`; class-weight power `1.0` gave the best macro recall, `0.461672`, at lower accuracy `0.52725`

Claim boundary: this proves a reproducible supervised training and inference path on AMD ROCm/MI300X. It does not prove production diagnostic accuracy.

## Offline Video Evidence Pipeline

The video path is deliberately offline first:

```txt
local video file
-> bounded ffmpeg frame extraction
-> per-frame Orvex InspectionResult
-> aggregate video triage summary
-> optional ROCm/MI300X runtime evidence JSON
```

This keeps the public product honest while still proving the architecture can evaluate timestamped video frames on the AMD stack.

Runbook:

```txt
docs/ml/video-frame-evaluation-rocm.md
```

Example VPS command:

```bash
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

Claim boundary: this is offline frame evaluation with human review required. It does not mean the Next.js UI or FastAPI API accepts arbitrary video uploads yet.
