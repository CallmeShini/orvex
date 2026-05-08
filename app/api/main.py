from __future__ import annotations

import os

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from app.api.ai_service import AiServiceError, OrvexAIService
from app.api.report_service import read_report, write_report
from app.api.schemas import (
    HealthResponse,
    PROMPT_VERSION,
    SCHEMA_VERSION,
    AnalyzeResponse,
)


app = FastAPI(
    title="Orvex API",
    description="AI-assisted visual triage API for photovoltaic inspection workflows.",
    version="0.1.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501", "http://127.0.0.1:8501"],
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
def samples() -> list[dict[str, str]]:
    return get_ai_service().list_samples()


@app.post("/analyze", response_model=AnalyzeResponse)
async def analyze(
    sample_name: str | None = Form(default=None),
    file: UploadFile | None = File(default=None),
) -> AnalyzeResponse:
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


@app.get("/reports/{inspection_id}", response_class=PlainTextResponse)
def report(inspection_id: str) -> str:
    try:
        return read_report(inspection_id)
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

