# Offline Video Frame Evaluation on ROCm

Updated: 2026-05-08

This runbook defines Orvex's controlled video path for the AMD hackathon.

The same frame pipeline can be used by `/inspection-jobs` for experimental bounded video uploads, but that path is disabled by default. This document remains the recommended VPS evidence runbook for controlled local video files and ROCm/MI300X proof.

## Objective

Prove that Orvex can evaluate a short solar inspection video as timestamped frames while preserving the existing product contract:

```txt
local video file
-> bounded ffmpeg frame extraction
-> per-frame InspectionResult
-> aggregated video triage summary
-> ROCm/MI300X runtime evidence
```

The output remains human-review triage. Do not use it to claim production diagnostic accuracy.

## Code Paths

```txt
app/ml/video_pipeline.py
app/ml/runtime_evidence.py
scripts/extract_video_frames.py
scripts/evaluate_video_frames.py
scripts/evaluate_video_offline.py
scripts/capture_runtime_evidence.py
```

## ffmpeg on VPS

The pipeline needs `ffmpeg`. It can come from either:

```txt
1. system ffmpeg available on PATH; or
2. imageio-ffmpeg installed in the Python venv; or
3. an explicit ORVEX_FFMPEG_BIN path.
```

The code resolves this automatically through `app.ml.video_pipeline.resolve_ffmpeg_bin`.

Verify it on the VPS:

```bash
cd /workspace/orvex
.venv/bin/python -c "from app.ml.video_pipeline import resolve_ffmpeg_bin; print(resolve_ffmpeg_bin())"
```

If the VPS keeps ffmpeg outside PATH, set:

```bash
export ORVEX_FFMPEG_BIN=/opt/ffmpeg/bin/ffmpeg
```

If system ffmpeg is preferred:

```bash
ffmpeg -version
```

## Output Layout

Use ignored evidence directories:

```txt
logs/evidence/video-eval-<timestamp>/
  frames/
  frames_manifest.json
  video_evaluation.json
  runtime_evidence.json
```

`video_evaluation.json` includes:

- source video path;
- frame count;
- per-frame `InspectionResult` payloads;
- aggregate priority;
- max, p95, mean, and top-k mean risk score;
- frames with findings, errors, and human-review state;
- representative timestamped frame;
- claim boundary metadata.

`runtime_evidence.json` includes:

- Python/platform metadata;
- allowlisted environment values only;
- PyTorch version, HIP version, device count, and device names;
- optional GPU matmul smoke;
- `amd-smi`, `rocm-smi`, and `rocminfo` command captures when present.

## VPS Command

Run from the canonical repo path:

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

Use `AI_MODE=classifier` when the goal is to evaluate the supervised RaptorMaps fallback instead of Qwen2.5-VL:

```bash
AI_MODE=classifier ORVEX_CLASSIFIER_ARTIFACT=data/models/raptormaps_classifier.pt \
  .venv/bin/python scripts/evaluate_video_offline.py \
  --video /workspace/private-videos/inspection.mp4 \
  --output-dir "logs/evidence/${RUN_ID}" \
  --sample-fps 1 \
  --max-frames 120 \
  --capture-rocm-evidence
```

## Validation

Local unit tests:

```bash
.venv/bin/pytest tests/test_video_pipeline.py tests/test_runtime_evidence.py tests/test_evaluate_video_offline.py tests/test_inspection_jobs.py
```

API smoke test after the service is running:

```bash
curl http://127.0.0.1:8000/health
```

Evidence checks on the VPS:

```bash
jq '.summary' "logs/evidence/${RUN_ID}/video_evaluation.json"
jq '.torch' "logs/evidence/${RUN_ID}/runtime_evidence.json"
rg -n "MI300X|AMD Instinct|HIP|ROCm|gfx" "logs/evidence/${RUN_ID}/runtime_evidence.json"
```

## Claim Boundary

Allowed:

```txt
Orvex has an offline video evidence pipeline that extracts timestamped frames,
runs the existing inspection contract per frame, aggregates triage signals,
and records ROCm/MI300X runtime evidence.
Orvex can run experimental bounded video jobs through POST /inspection-jobs when explicit flags are enabled.
```

Not allowed:

```txt
Orvex supports arbitrary unbounded public video uploads.
Orvex provides production diagnostic accuracy.
Orvex replaces field technicians or automates maintenance decisions.
```

## Experimental API Integration

The public job endpoint rejects video by default. To enable experimental bounded video jobs locally:

```bash
ORVEX_ENABLE_VIDEO_UPLOAD=true
ORVEX_VIDEO_PROCESSING_MODE=background
```

With those flags, the job endpoint uses this shape:

```txt
POST /inspection-jobs
-> store video asset with strict limits
-> enqueue background task
-> extract bounded frames
-> write frame assets and frame results
-> aggregate final job.result
-> expose job polling and reviewable evidence
```

For production-grade VPS workloads, replace FastAPI `BackgroundTasks` with a durable worker queue.
