# Inspection Jobs API

Updated: 2026-05-08

The inspection job API is the production-compatible path for Orvex ingestion.

It keeps the existing `InspectionResult` contract, but wraps execution in a job envelope so image analysis, bounded video frame processing, queueing, and review workflows can share one shape.

## Endpoints

```txt
POST /inspection-jobs
GET /inspection-jobs/{job_id}
```

`POST /inspection-jobs` accepts:

```txt
sample_name: optional form string
file: optional image file, or experimental video file when explicitly enabled
sample_fps: optional video frame sampling rate
max_frames: optional video frame cap
```

Exactly one of these must be useful. If neither is provided, the API returns `422`.

For this build, image upload types are always accepted:

```txt
image/jpeg
image/png
image/webp
image/tiff
```

Video upload types are disabled by default and only accepted when both flags are set:

```bash
ORVEX_ENABLE_VIDEO_UPLOAD=true
ORVEX_VIDEO_PROCESSING_MODE=background
```

Experimental video content types:

```txt
video/mp4
video/quicktime
video/webm
```

Video uploads are accepted by `/inspection-jobs` only in this explicit experimental mode. The legacy `/analyze` endpoint remains image-only.

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

Experimental video jobs are created quickly and processed with FastAPI `BackgroundTasks`:

```txt
request
-> create queued job
-> persist uploaded video asset
-> return job_id
-> extract bounded frames with ffmpeg
-> run OrvexAIService on each frame
-> aggregate frame results into video_result
-> persist video_evaluation.json
-> update job to completed or failed
```

This intentionally avoids adding a database or external queue before the product needs it. `BackgroundTasks` runs in the API process and is not durable; for heavier VPS workloads, replace it with a real worker queue.

## Filesystem Layout

Job data is stored under ignored local filesystem paths:

```txt
data/jobs/{job_id}/job.json
data/jobs/{job_id}/assets/{asset_id}-{safe_filename}
data/jobs/{job_id}/assets/frames/frame-000001.jpg
data/jobs/{job_id}/results/frames_manifest.json
data/jobs/{job_id}/results/video_evaluation.json
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
  "video_result": null,
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
- Unsupported uploads are rejected.
- Image upload size is controlled by `ORVEX_MAX_UPLOAD_BYTES`.
- Video upload is disabled unless `ORVEX_ENABLE_VIDEO_UPLOAD=true`.
- Experimental video processing requires `ORVEX_VIDEO_PROCESSING_MODE=background`.
- Video upload size is controlled by `ORVEX_MAX_VIDEO_UPLOAD_BYTES`; the default is intentionally conservative.
- Video sampling is bounded by `sample_fps <= 2` and `max_frames <= 120`.

## Video Boundary

Allowed claim:

```txt
Orvex has an offline video evidence pipeline, and can run experimental bounded video jobs when
explicitly enabled. Both paths extract frames, apply the existing inspection contract per frame,
and aggregate triage signals for human review.
```

Still not allowed:

```txt
Orvex performs production-grade temporal video understanding.
Orvex supports arbitrary unbounded public video uploads.
Orvex replaces field technicians or automates maintenance decisions.
```

The current video path is frame-based:

```txt
video asset
-> frame extraction
-> per-frame analysis
-> timestamped evidence
-> aggregation policy
-> experimental background task/job status
-> reviewable report
```

The offline evidence pipeline remains available for controlled VPS runs:

```txt
scripts/evaluate_video_offline.py
docs/ml/video-frame-evaluation-rocm.md
```
