from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field


SCHEMA_VERSION = "orvex-inspection-result-v1"
PROMPT_VERSION = "orvex-solar-vlm-prompt-v1"
DEFAULT_MODEL_NAME = "mock-orvex-solar-inspection-v1"


class ImageModality(str, Enum):
    RGB = "rgb"
    THERMAL = "thermal"
    INFRARED = "infrared"
    UNKNOWN = "unknown"


class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"
    INCONCLUSIVE = "inconclusive"


class DefectType(str, Enum):
    HOTSPOT = "hotspot"
    CRACK = "crack"
    SOILING = "soiling"
    BROKEN_CELL = "broken_cell"
    SHADOWING = "shadowing"
    DELAMINATION = "delamination"
    BURN_MARK = "burn_mark"
    DISCOLORATION = "discoloration"
    DIODE = "diode"
    VEGETATION = "vegetation"
    OFFLINE_MODULE = "offline_module"
    UNKNOWN = "unknown"


class InspectionSourceType(str, Enum):
    SAMPLE = "sample"
    IMAGE = "image"
    VIDEO = "video"


class InspectionJobStatus(str, Enum):
    QUEUED = "queued"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"
    UNSUPPORTED = "unsupported"


class Finding(BaseModel):
    defect_type: DefectType
    severity: Priority
    confidence: float = Field(ge=0.0, le=1.0)
    location_hint: str = Field(min_length=1)
    visual_evidence: str = Field(min_length=1)
    recommended_action: str = Field(min_length=1)


class InspectionResult(BaseModel):
    inspection_id: str = Field(default_factory=lambda: f"orvex-{uuid4().hex[:12]}")
    image_modality: ImageModality = ImageModality.UNKNOWN
    contains_solar_panel: bool
    inspection_confidence: float = Field(ge=0.0, le=1.0)
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    priority: Priority
    findings: list[Finding] = Field(default_factory=list)
    human_review_required: bool
    summary: str = Field(min_length=1)
    raw_model_output: str | None = None
    schema_version: str = SCHEMA_VERSION
    prompt_version: str = PROMPT_VERSION
    model_name: str = DEFAULT_MODEL_NAME
    model_mode: str = "mock"
    latency_ms: int | None = None


class AnalyzeResponse(BaseModel):
    result: InspectionResult
    report_path: str | None = None
    report_markdown: str | None = None


class InspectionAsset(BaseModel):
    asset_id: str
    source_type: InspectionSourceType
    filename: str | None = None
    sample_name: str | None = None
    media_type: str | None = None
    storage_path: str | None = None
    size_bytes: int | None = Field(default=None, ge=0)
    sha256: str | None = None
    frame_index: int | None = None
    timestamp_ms: int | None = Field(default=None, ge=0)


class VideoFrameAsset(BaseModel):
    frame_index: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    path: str
    sha256: str | None = None


class VideoFrameInspection(BaseModel):
    frame: VideoFrameAsset
    result: InspectionResult
    error: str | None = None


class VideoRepresentativeFrame(BaseModel):
    frame_index: int = Field(ge=0)
    timestamp_ms: int = Field(ge=0)
    inspection_id: str
    priority: Priority
    overall_risk_score: float = Field(ge=0.0, le=1.0)
    summary: str


class VideoInspectionSummary(BaseModel):
    schema_version: str
    frames_analyzed: int = Field(ge=0)
    frames_with_findings: int = Field(ge=0)
    frames_with_errors: int = Field(ge=0)
    frames_requiring_human_review: int = Field(ge=0)
    priority: Priority
    max_overall_risk_score: float = Field(ge=0.0, le=1.0)
    p95_overall_risk_score: float = Field(ge=0.0, le=1.0)
    top_k_mean_overall_risk_score: float = Field(ge=0.0, le=1.0)
    mean_overall_risk_score: float = Field(ge=0.0, le=1.0)
    mean_inspection_confidence: float = Field(ge=0.0, le=1.0)
    defect_type_counts: dict[str, int] = Field(default_factory=dict)
    model_mode_counts: dict[str, int] = Field(default_factory=dict)
    latency_ms_total: int | None = Field(default=None, ge=0)
    latency_ms_mean: float | None = Field(default=None, ge=0.0)
    representative_frame: VideoRepresentativeFrame
    human_review_required: bool


class VideoEvaluationResult(BaseModel):
    schema_version: str
    source_video: str | None = None
    frame_count: int = Field(ge=0)
    summary: VideoInspectionSummary
    run_metadata: dict[str, Any] = Field(default_factory=dict)
    frames: list[VideoFrameInspection] = Field(default_factory=list)


class InspectionJobResponse(BaseModel):
    job_id: str
    status: InspectionJobStatus
    source_type: InspectionSourceType
    asset: InspectionAsset | None = None
    result: InspectionResult | None = None
    video_result: VideoEvaluationResult | None = None
    report_id: str | None = None
    report_markdown: str | None = None
    error: str | None = None
    created_at: str
    updated_at: str


class SampleInfo(BaseModel):
    name: str
    priority: Priority
    summary: str


class HealthResponse(BaseModel):
    status: str
    ai_mode: str
    schema_version: str
    prompt_version: str

def result_from_mapping(payload: dict[str, Any]) -> InspectionResult:
    return InspectionResult.model_validate(payload)
