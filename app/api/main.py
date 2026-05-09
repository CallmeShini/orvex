from __future__ import annotations

import os

from fastapi import BackgroundTasks, FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from app.api.ai_service import AiServiceError, OrvexAIService
from app.api.job_service import InspectionJobNotFound, InspectionJobService
from app.api.report_service import read_report, write_report
from app.api.schemas import (
    HealthResponse,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    AnalyzeResponse,
    InspectionJobResponse,
)


DEFAULT_CORS_ORIGINS = (
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
)
ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/tiff",
}
ALLOWED_VIDEO_CONTENT_TYPES = {
    "video/mp4",
    "video/quicktime",
    "video/webm",
}
DEFAULT_MAX_UPLOAD_BYTES = 15 * 1024 * 1024
DEFAULT_MAX_VIDEO_UPLOAD_BYTES = 50 * 1024 * 1024
DEFAULT_VIDEO_FPS = 1.0
DEFAULT_VIDEO_MAX_FRAMES = 48
VIDEO_PROCESSING_MODE_DISABLED = "disabled"
VIDEO_PROCESSING_MODE_BACKGROUND = "background"


def cors_origins() -> list[str]:
    configured = os.getenv("ORVEX_CORS_ORIGINS", "")
    extra_origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [*DEFAULT_CORS_ORIGINS, *extra_origins]


def env_flag(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.lower() in {"1", "true", "yes", "on"}


def video_upload_enabled() -> bool:
    return env_flag("ORVEX_ENABLE_VIDEO_UPLOAD", default=False)


def video_processing_mode() -> str:
    return os.getenv("ORVEX_VIDEO_PROCESSING_MODE", VIDEO_PROCESSING_MODE_DISABLED).lower()


app = FastAPI(
    title="Orvex API",
    description="AI-assisted visual triage API for photovoltaic inspection workflows.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=cors_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_ai_service() -> OrvexAIService:
    return OrvexAIService()


def get_job_service() -> InspectionJobService:
    return InspectionJobService()


@app.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    return HealthResponse(
        status="ok",
        ai_mode=os.getenv("AI_MODE", "mock"),
        schema_version=SCHEMA_VERSION,
        prompt_version=PROMPT_VERSION,
    )


@app.get("/samples")
def samples() -> list[dict[str, object]]:
    return get_ai_service().list_samples()


@app.get("/samples/{sample_name}/image", response_class=FileResponse)
def sample_image(sample_name: str) -> FileResponse:
    try:
        image_path = get_ai_service().get_sample_image_path(sample_name)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    return FileResponse(image_path, media_type="image/jpeg")


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    sample_name: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
    if file is not None:
        validate_upload(file)

    service = get_ai_service()
    try:
        result = service.analyze_image(
            sample_name=sample_name,
            filename=file.filename if file else None,
            file_obj=file.file if file else None,
        )
    except AiServiceError as exc:
        result = service.inconclusive_result(raw_output=str(exc))

    report_path, report_markdown = write_report(result)
    return AnalyzeResponse(
        result=result,
        report_path=str(report_path),
        report_markdown=report_markdown,
    )


@app.post("/inspection-jobs", response_model=InspectionJobResponse)
async def create_inspection_job(
    background_tasks: BackgroundTasks,
    sample_name: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
    sample_fps: float = Form(default=DEFAULT_VIDEO_FPS),
    max_frames: int = Form(default=DEFAULT_VIDEO_MAX_FRAMES),
) -> InspectionJobResponse:
    if file is None and not sample_name:
        raise HTTPException(status_code=422, detail="Provide either sample_name or an image/video file.")
    if file is not None:
        validate_job_upload(file)

    job_service = get_job_service()
    if file is not None and file.content_type in ALLOWED_VIDEO_CONTENT_TYPES:
        if not video_upload_enabled():
            raise HTTPException(
                status_code=415,
                detail="Video upload is disabled in this build. Use the offline video evidence pipeline.",
            )
        if video_processing_mode() != VIDEO_PROCESSING_MODE_BACKGROUND:
            raise HTTPException(
                status_code=503,
                detail="Video upload is enabled, but no video processing mode is active.",
            )
        if sample_fps <= 0 or sample_fps > 2:
            raise HTTPException(status_code=422, detail="sample_fps must be greater than 0 and at most 2.")
        if max_frames <= 0 or max_frames > 120:
            raise HTTPException(status_code=422, detail="max_frames must be greater than 0 and at most 120.")

        job = job_service.create_video_job(
            filename=file.filename or "inspection-video",
            media_type=file.content_type or "application/octet-stream",
            file_obj=file.file,
            max_bytes=int(os.getenv("ORVEX_MAX_VIDEO_UPLOAD_BYTES", str(DEFAULT_MAX_VIDEO_UPLOAD_BYTES))),
        )
        background_tasks.add_task(
            job_service.process_video_job,
            job.job_id,
            get_ai_service(),
            sample_fps,
            max_frames,
        )
        return job

    return job_service.create_image_job(
        ai_service=get_ai_service(),
        sample_name=sample_name,
        filename=file.filename if file else None,
        media_type=file.content_type if file else None,
        file_obj=file.file if file else None,
    )


@app.get("/inspection-jobs/{job_id}", response_model=InspectionJobResponse)
def inspection_job(job_id: str) -> InspectionJobResponse:
    try:
        return get_job_service().get_job(job_id)
    except InspectionJobNotFound as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


def validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported upload type. This API build accepts image inputs only: "
                "JPEG, PNG, WebP, or TIFF. Video requires the planned inspection-job pipeline."
            ),
        )

    validate_upload_size(file, max_bytes=int(os.getenv("ORVEX_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))))


def validate_job_upload(file: UploadFile) -> None:
    if file.content_type in ALLOWED_IMAGE_CONTENT_TYPES:
        validate_upload_size(file, max_bytes=int(os.getenv("ORVEX_MAX_UPLOAD_BYTES", str(DEFAULT_MAX_UPLOAD_BYTES))))
        return

    if file.content_type in ALLOWED_VIDEO_CONTENT_TYPES:
        if not video_upload_enabled():
            raise HTTPException(
                status_code=415,
                detail="Video upload is disabled in this build. Use the offline video evidence pipeline.",
            )
        validate_upload_size(
            file,
            max_bytes=int(os.getenv("ORVEX_MAX_VIDEO_UPLOAD_BYTES", str(DEFAULT_MAX_VIDEO_UPLOAD_BYTES))),
        )
        return

    raise HTTPException(
        status_code=415,
        detail="Unsupported upload type. Use JPEG, PNG, WebP, TIFF, MP4, MOV, or WebM.",
    )


def validate_upload_size(file: UploadFile, max_bytes: int) -> None:
    current_position = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(current_position)
    if size > max_bytes:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {max_bytes} byte limit.",
        )


@app.get("/reports/{inspection_id}", response_class=PlainTextResponse)
def report(inspection_id: str) -> str:
    try:
        return read_report(inspection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
