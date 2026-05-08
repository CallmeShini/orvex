# Inspection Jobs API

Updated: 2026-05-08

The inspection job API is the production-compatible path for Orvex ingestion.

It keeps the existing `InspectionResult` contract, but wraps execution in a job envelope so image analysis, future video processing, queueing, and review workflows can share one shape.

## Endpoints

```txt
POST /inspection-jobs
GET /inspection-jobs/{job_id}
```

`POST /inspection-jobs` accepts:

```txt
sample_name: optional form string
file: optional image file
```

Exactly one of these must be useful. If neither is provided, the API returns `422`.

For this build, accepted upload types are:

```txt
image/jpeg
image/png
image/webp
image/tiff
```

Video uploads return `415` with an explicit message that the video pipeline is planned but not enabled.

## Current Execution Model

Image and sample jobs are processed synchronously for hackathon reliability:

```txt
request
-> create job folder
-> persist job metadata
-> persist uploaded image asset when present
-> run OrvexAIService
-> validate InspectionResult
-> write report
-> write result JSON
-> return completed job
```

This intentionally avoids adding a queue, database, or worker process before the product needs it.

## Filesystem Layout

Job data is stored under ignored local filesystem paths:

```txt
data/jobs/{job_id}/job.json
data/jobs/{job_id}/assets/{asset_id}-{safe_filename}
data/jobs/{job_id}/results/{inspection_id}.json
data/reports/{inspection_id}.md
```

`data/jobs/*`, `data/uploads/*`, and `data/reports/*` are ignored by Git. Only `.gitkeep` placeholders are tracked.

## Response Shape

```json
{
  "job_id": "job-...",
  "status": "completed",
  "source_type": "image",
  "asset": {
    "asset_id": "asset-...",
    "source_type": "image",
    "filename": "panel.jpg",
    "sample_name": null,
    "media_type": "image/jpeg",
    "storage_path": "assets/asset-...-panel.jpg",
    "size_bytes": 12345,
    "sha256": "...",
    "frame_index": null,
    "timestamp_ms": null
  },
  "result": {},
  "report_id": "orvex-...",
  "report_markdown": "...",
  "error": null,
  "created_at": "2026-05-08T00:00:00+00:00",
  "updated_at": "2026-05-08T00:00:00+00:00"
}
```

## Backwards Compatibility

`POST /analyze` remains available and still returns:

```txt
AnalyzeResponse
```

The Next.js UI now uses `/inspection-jobs`, but older demo clients can keep using `/analyze`.

## Security Boundaries

- User filenames are reduced to `Path(filename).name`.
- Asset filenames are generated from server-side IDs.
- Uploaded assets are scoped under `data/jobs/{job_id}/assets`.
- Job metadata is loaded by `job_id`, not by arbitrary file paths.
- Non-image uploads are rejected.
- Upload size is controlled by `ORVEX_MAX_UPLOAD_BYTES`.

## Video Boundary

Allowed claim:

```txt
Orvex now has a job-shaped API foundation for image inspections and future video ingestion.
```

Not allowed yet:

```txt
Orvex supports video inspection.
```

Video needs a separate implementation:

```txt
video asset
-> frame extraction
-> per-frame analysis
-> timestamped evidence
-> aggregation policy
-> reviewable report
```
