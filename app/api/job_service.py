from __future__ import annotations

import json
import hashlib
import re
from datetime import UTC, datetime
from pathlib import Path
from typing import BinaryIO
from uuid import uuid4

from app.api.ai_service import AiServiceError, OrvexAIService
from app.api.report_service import write_report
from app.api.schemas import (
    InspectionAsset,
    InspectionResult,
    InspectionJobResponse,
    InspectionJobStatus,
    InspectionSourceType,
    VideoEvaluationResult,
)
from app.ml.video_pipeline import (
    DEFAULT_MAX_FRAMES,
    DEFAULT_VIDEO_FPS,
    FrameInspection,
    VideoPipelineError,
    extract_video_frames,
    video_evaluation_payload,
    write_frame_manifest,
)
from app.api.structured_events import append_structured_event


PROJECT_ROOT = Path(__file__).resolve().parents[2]
JOBS_DIR = PROJECT_ROOT / "data" / "jobs"
ASSET_SUFFIX_BY_MEDIA_TYPE = {
    "image/jpeg": ".jpg",
    "image/png": ".png",
    "image/webp": ".webp",
    "image/tiff": ".tiff",
    "video/mp4": ".mp4",
    "video/quicktime": ".mov",
    "video/webm": ".webm",
}


class InspectionJobNotFound(FileNotFoundError):
    """Raised when an inspection job record does not exist."""


class InspectionJobService:
    def __init__(self, jobs_dir: Path | None = None) -> None:
        self.jobs_dir = jobs_dir or JOBS_DIR

    def create_image_job(
        self,
        ai_service: OrvexAIService,
        sample_name: str | None = None,
        filename: str | None = None,
        media_type: str | None = None,
        file_obj: BinaryIO | None = None,
    ) -> InspectionJobResponse:
        now = utc_now()
        job_id = f"job-{uuid4().hex[:12]}"
        job_dir = self._job_dir(job_id)
        source_type = InspectionSourceType.IMAGE if filename else InspectionSourceType.SAMPLE
        asset_path: Path | None = None
        asset = InspectionAsset(
            asset_id=f"asset-{uuid4().hex[:12]}",
            source_type=source_type,
            filename=Path(filename).name if filename else None,
            sample_name=sample_name,
            media_type=media_type,
        )
        job = InspectionJobResponse(
            job_id=job_id,
            status=InspectionJobStatus.PROCESSING,
            source_type=source_type,
            asset=asset,
            created_at=now,
            updated_at=now,
        )
        self._write(job)
        self._log_event(
            job_id=job_id,
            event="job_created",
            status=job.status.value,
            source_type=source_type.value,
            asset_id=asset.asset_id,
            sample_name=sample_name,
            media_type=asset.media_type,
        )
        if file_obj and filename:
            asset, asset_path = self._save_asset(job_dir=job_dir, asset=asset, filename=filename, file_obj=file_obj)
            self._log_event(
                job_id=job_id,
                event="asset_saved",
                asset_id=asset.asset_id,
                source_type=asset.source_type.value,
                media_type=asset.media_type,
                storage_path=asset.storage_path,
                size_bytes=asset.size_bytes,
                sha256=asset.sha256,
            )

        try:
            result = ai_service.analyze_image(
                sample_name=sample_name,
                filename=filename,
                image_path=asset_path,
            )
        except AiServiceError as exc:
            result = ai_service.inconclusive_result(raw_output=str(exc))
        except Exception:
            failed = job.model_copy(update={"status": InspectionJobStatus.FAILED, "updated_at": utc_now()})
            self._write(failed)
            self._log_event(
                job_id=job_id,
                event="job_failed",
                status=failed.status.value,
                error_type="unexpected_exception",
            )
            raise

        _report_path, report_markdown = write_report(result)
        self._write_result(job_id=job.job_id, result=result)
        completed = job.model_copy(
            update={
                "status": InspectionJobStatus.COMPLETED,
                "asset": asset,
                "result": result,
                "report_id": result.inspection_id,
                "report_markdown": report_markdown,
                "updated_at": utc_now(),
            }
        )
        self._write(completed)
        self._log_event(
            job_id=job_id,
            event="job_completed",
            status=completed.status.value,
            inspection_id=result.inspection_id,
            model_mode=result.model_mode,
            model_name=result.model_name,
            latency_ms=result.latency_ms,
            priority=result.priority.value,
            findings_count=len(result.findings),
            human_review_required=result.human_review_required,
            report_id=completed.report_id,
        )
        return completed

    def create_video_job(
        self,
        filename: str,
        media_type: str,
        file_obj: BinaryIO,
    ) -> InspectionJobResponse:
        now = utc_now()
        job_id = f"job-{uuid4().hex[:12]}"
        job_dir = self._job_dir(job_id)
        asset = InspectionAsset(
            asset_id=f"asset-{uuid4().hex[:12]}",
            source_type=InspectionSourceType.VIDEO,
            filename=Path(filename).name,
            media_type=media_type,
        )
        asset, _asset_path = self._save_asset(job_dir=job_dir, asset=asset, filename=filename, file_obj=file_obj)
        job = InspectionJobResponse(
            job_id=job_id,
            status=InspectionJobStatus.QUEUED,
            source_type=InspectionSourceType.VIDEO,
            asset=asset,
            created_at=now,
            updated_at=now,
        )
        self._write(job)
        return job

    def process_video_job(
        self,
        job_id: str,
        ai_service: OrvexAIService,
        sample_fps: float = DEFAULT_VIDEO_FPS,
        max_frames: int = DEFAULT_MAX_FRAMES,
        ffmpeg_bin: str = "ffmpeg",
    ) -> InspectionJobResponse:
        job = self.get_job(job_id)
        if job.asset is None or job.asset.storage_path is None:
            failed = job.model_copy(
                update={
                    "status": InspectionJobStatus.FAILED,
                    "error": "Video job has no persisted source asset.",
                    "updated_at": utc_now(),
                }
            )
            self._write(failed)
            return failed

        processing = job.model_copy(update={"status": InspectionJobStatus.PROCESSING, "updated_at": utc_now()})
        self._write(processing)

        job_dir = self._job_dir(job.job_id)
        video_path = job_dir / job.asset.storage_path
        results_dir = job_dir / "results"
        frames_dir = job_dir / "assets" / "frames"
        manifest_path = results_dir / "frames_manifest.json"

        try:
            frames = extract_video_frames(
                video_path=video_path,
                output_dir=frames_dir,
                fps=sample_fps,
                max_frames=max_frames,
                overwrite=True,
                ffmpeg_bin=ffmpeg_bin,
            )
            write_frame_manifest(
                manifest_path=manifest_path,
                video_path=video_path,
                frames=frames,
                fps=sample_fps,
                max_frames=max_frames,
            )
            frame_inspections = []
            for frame in frames:
                try:
                    result = ai_service.analyze_image(filename=frame.path.name, image_path=frame.path)
                    frame_inspections.append(FrameInspection(frame=frame, result=result))
                except AiServiceError as exc:
                    result = ai_service.inconclusive_result(raw_output=str(exc))
                    frame_inspections.append(FrameInspection(frame=frame, result=result, error=str(exc)))

            payload = video_evaluation_payload(
                source_video=video_path,
                frames=frames,
                frame_inspections=frame_inspections,
                run_metadata={
                    "ai_mode": ai_service.mode,
                    "sample_fps": sample_fps,
                    "max_frames": max_frames,
                    "claim_boundary": (
                        "Video support is bounded frame-based triage. Results require human review "
                        "and do not replace field inspection."
                    ),
                },
            )
            video_result = VideoEvaluationResult.model_validate(payload)
            self._write_video_result(job_id=job.job_id, video_result=video_result)
            representative_result = self._representative_result(video_result)
            _report_path, report_markdown = write_report(representative_result)
            completed = processing.model_copy(
                update={
                    "status": InspectionJobStatus.COMPLETED,
                    "result": representative_result,
                    "video_result": video_result,
                    "report_id": representative_result.inspection_id,
                    "report_markdown": report_markdown,
                    "updated_at": utc_now(),
                }
            )
            self._write(completed)
            return completed
        except (OSError, ValueError, VideoPipelineError) as exc:
            failed = processing.model_copy(
                update={
                    "status": InspectionJobStatus.FAILED,
                    "error": str(exc),
                    "updated_at": utc_now(),
                }
            )
            self._write(failed)
            return failed

    def get_job(self, job_id: str) -> InspectionJobResponse:
        path = self._job_path(job_id)
        if not path.exists():
            raise InspectionJobNotFound(f"Inspection job not found: {job_id}")
        payload = json.loads(path.read_text(encoding="utf-8"))
        return InspectionJobResponse.model_validate(payload)

    def _write(self, job: InspectionJobResponse) -> None:
        job_dir = self._job_dir(job.job_id)
        job_dir.mkdir(parents=True, exist_ok=True)
        path = self._job_path(job.job_id)
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(job.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _job_path(self, job_id: str) -> Path:
        safe_job_id = Path(job_id).name
        return self._job_dir(safe_job_id) / "job.json"

    def _job_dir(self, job_id: str) -> Path:
        safe_job_id = Path(job_id).name
        return self.jobs_dir / safe_job_id

    def _events_path(self, job_id: str) -> Path:
        return self._job_dir(job_id) / "events.jsonl"

    def _log_event(self, job_id: str, event: str, **fields: object) -> None:
        append_structured_event(self._events_path(job_id), event=event, job_id=job_id, **fields)

    def _save_asset(
        self,
        job_dir: Path,
        asset: InspectionAsset,
        filename: str,
        file_obj: BinaryIO,
    ) -> tuple[InspectionAsset, Path]:
        original_name = Path(filename).name
        safe_stem = re.sub(r"[^a-zA-Z0-9._-]+", "-", Path(original_name).stem).strip(".-")
        safe_stem = safe_stem[:80] or "inspection-upload"
        suffix = ASSET_SUFFIX_BY_MEDIA_TYPE.get(asset.media_type or "", Path(original_name).suffix.lower()[:12])
        asset_filename = f"{asset.asset_id}-{safe_stem}{suffix}"
        relative_path = Path("assets") / asset_filename
        destination = job_dir / relative_path
        assert_within_directory(destination=destination, directory=job_dir)

        payload = file_obj.read()
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_bytes(payload)
        updated_asset = asset.model_copy(
            update={
                "storage_path": relative_path.as_posix(),
                "size_bytes": len(payload),
                "sha256": hashlib.sha256(payload).hexdigest(),
            }
        )
        return updated_asset, destination

    def _write_result(self, job_id: str, result: InspectionResult) -> None:
        result_dir = self._job_dir(job_id) / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        path = result_dir / f"{result.inspection_id}.json"
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(result.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    def _write_video_result(self, job_id: str, video_result: VideoEvaluationResult) -> None:
        result_dir = self._job_dir(job_id) / "results"
        result_dir.mkdir(parents=True, exist_ok=True)
        path = result_dir / "video_evaluation.json"
        tmp_path = path.with_suffix(".json.tmp")
        tmp_path.write_text(json.dumps(video_result.model_dump(mode="json"), indent=2, sort_keys=True), encoding="utf-8")
        tmp_path.replace(path)

    @staticmethod
    def _representative_result(video_result: VideoEvaluationResult) -> InspectionResult:
        representative_id = video_result.summary.representative_frame.inspection_id
        for frame in video_result.frames:
            if frame.result.inspection_id == representative_id:
                return frame.result
        return video_result.frames[0].result


def assert_within_directory(destination: Path, directory: Path) -> None:
    destination.resolve().relative_to(directory.resolve())


def utc_now() -> str:
    return datetime.now(UTC).isoformat(timespec="seconds")
