# Next.js Product Interface

Updated: 2026-05-08

The canonical Orvex presentation interface is now the Next.js app under `frontend/`.

Streamlit remains useful as a legacy internal smoke UI, but the product-facing surface is the Next.js workspace because the hackathon presentation needs to communicate a serious vertical SaaS workflow, not a notebook-style demo.

## Architecture

```txt
Browser
-> Next.js App Router workspace
-> Next.js route handler proxy /api/orvex/*
-> FastAPI Orvex API
-> inspection job envelope
-> mock, local VLM, or RaptorMaps classifier mode
-> validated InspectionResult
-> report markdown
```

The proxy route lives at:

```txt
frontend/app/api/orvex/[...path]/route.ts
```

It forwards requests to `ORVEX_API_URL`, defaulting to:

```txt
http://127.0.0.1:8000
```

For local runs where another service already owns port `8000`, set another FastAPI port and pass it to Next:

```bash
AI_MODE=mock .venv/bin/uvicorn app.api.main:app --host 127.0.0.1 --port 8010
cd frontend
ORVEX_API_URL=http://127.0.0.1:8010 npm run dev -- --hostname 127.0.0.1 --port 3001
```

## Interface Scope

Implemented now:

- operational inspection workspace, not a marketing landing page;
- curated RaptorMaps demo path;
- image upload for JPEG, PNG, WebP, and TIFF;
- FastAPI inspection jobs through a Next.js BFF/proxy;
- `job_id` and `status` traceability in the result inspector;
- risk, confidence, findings, model mode, schema, and human-review display;
- loading, empty, error, and analyzed states;
- restrained product UI using Next.js, React, TypeScript, Tailwind, Framer Motion, and Phosphor icons.

Not implemented yet:

- public video ingestion;
- async job lifecycle;
- tenant auth;
- persistent database-backed reports;
- generated OpenAPI TypeScript client.

## Video Boundary

The UI intentionally labels video as planned instead of accepting video files.
The repository now has an offline video frame-evaluation pipeline for MI300X/ROCm evidence runs,
but the product interface should present that as recorded evidence, not live upload support.

The current FastAPI endpoint is synchronous and image-centric:

```txt
POST /inspection-jobs
sample_name: optional form string
file: optional image file
```

Real video support should be a separate job pipeline:

```txt
POST /inspection-jobs
-> store video asset
-> sample frames
-> run per-frame VLM/classifier analysis
-> aggregate findings with timestamps
-> return job status and frame evidence
```

Until that exists, accepting video would create a false product claim.

## Backend Hardening Added

The FastAPI layer now has:

- configurable CORS origins with Next.js local origins included;
- image upload content-type validation;
- upload size limit via `ORVEX_MAX_UPLOAD_BYTES`;
- unique upload filenames to avoid overwrite collisions.

## ML Presentation Boundary

The interface should present classifier and VLM outputs as measured triage signals.

Do not show fake certainty. The current RaptorMaps classifier probabilities are uncalibrated and must be labeled as provisional. Human review remains required for all current outputs.

LoRA can be added as a controlled Qwen2.5-VL adapter experiment, but it should target schema compliance, taxonomy alignment, and cautious reporting unless a held-out evaluation proves diagnostic improvement.

## Validation

Current local validation:

```bash
cd frontend
npm audit --json
npm run typecheck
npm run build

cd ..
.venv/bin/pytest
```

The Playwright smoke check loads the workspace, confirms the API proxy, runs the default hotspot analysis, and captures screenshots under ignored `logs/`.
