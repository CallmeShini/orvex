from __future__ import annotations

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, PlainTextResponse

from app.api.ai_service import AiServiceError, OrvexAIService
from app.api.report_service import read_report, write_report
from app.api.schemas import (
    HealthResponse,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    AnalyzeResponse,
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
MAX_UPLOAD_BYTES = int(os.getenv("ORVEX_MAX_UPLOAD_BYTES", str(15 * 1024 * 1024)))


def cors_origins() -> list[str]:
    configured = os.getenv("ORVEX_CORS_ORIGINS", "")
    extra_origins = [origin.strip() for origin in configured.split(",") if origin.strip()]
    return [*DEFAULT_CORS_ORIGINS, *extra_origins]


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


def validate_upload(file: UploadFile) -> None:
    if file.content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
        raise HTTPException(
            status_code=415,
            detail=(
                "Unsupported upload type. This API build accepts image inputs only: "
                "JPEG, PNG, WebP, or TIFF. Video requires the planned inspection-job pipeline."
            ),
        )

    current_position = file.file.tell()
    file.file.seek(0, os.SEEK_END)
    size = file.file.tell()
    file.file.seek(current_position)
    if size > MAX_UPLOAD_BYTES:
        raise HTTPException(
            status_code=413,
            detail=f"Upload exceeds the {MAX_UPLOAD_BYTES} byte limit.",
        )


@app.get("/reports/{inspection_id}", response_class=PlainTextResponse)
def report(inspection_id: str) -> str:
    try:
        return read_report(inspection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
