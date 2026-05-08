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
  ui/
    streamlit_app.py
data/
  evaluation/
    raptormaps_manifest.jsonl
    expected_outputs/
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
  demo/
    submission-checklist.md
```

## Near-Term Goal

Build a production-compatible hackathon MVP:

```txt
upload images
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

### Run UI

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
