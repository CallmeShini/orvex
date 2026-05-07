# Architecture Principles

## Core Principle

Keep the system simple enough for a four-day hackathon, but compatible with a real product path.

The VLM must not own all product logic. Orvex should separate ingestion, preprocessing, inference, validation, prioritization, human review, reporting, and observability.

## Target Flow

```txt
frontend
-> upload image, batch, or short video
-> backend creates inspection job
-> pipeline normalizes input
-> AI layer analyzes image/frame
-> backend validates schema
-> backend calculates priority and review state
-> UI shows review queue and evidence
-> user reviews result
-> report is exported
```

## Initial Stack Direction

For the hackathon implementation:

- Python backend.
- FastAPI API boundary.
- Pydantic schemas.
- Streamlit or similarly fast UI only if speed is required.
- Local filesystem storage for hackathon.
- SQLite only if persistence becomes necessary.
- AI mode switch: `mock` first, `local` when model integration is stable.

For production evolution:

- Dedicated frontend.
- Durable database.
- Object storage.
- Async job queue.
- Structured observability.
- Auth and tenant boundaries.
- Dataset and prompt versioning.

## Minimal Domain Entities

```txt
InspectionJob
  id
  created_at
  status
  source_type
  asset_group

InspectionAsset
  id
  job_id
  filename
  frame_index
  storage_path

InspectionResult
  id
  asset_id
  model_name
  prompt_version
  schema_version
  risk_score
  priority
  findings_json
  human_review_required
  review_status
```

## Observability Minimum

Track from the beginning:

- model mode: mock or local;
- model name;
- prompt version;
- schema version;
- latency per image;
- JSON parse failures;
- validation failures;
- fallback usage;
- human review requirement rate.

## VPS Boundary

The VPS should be used only for serious model validation, GPU inference, and reproducible performance checks.

Do not use the VPS for:

- product discovery;
- unreviewed architecture churn;
- broad dependency experimentation;
- undocumented file changes;
- secrets stored in source files.
