from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.ai_service import OrvexAIService
from app.api.json_utils import JsonExtractionError, extract_json_object
from app.api.schemas import InspectionResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"


@pytest.mark.parametrize("sample_path", sorted(SAMPLES_DIR.glob("*.json")))
def test_samples_match_contract(sample_path: Path) -> None:
    payload = json.loads(sample_path.read_text(encoding="utf-8"))
    result = InspectionResult.model_validate(payload)
    assert result.summary
    assert 0 <= result.overall_risk_score <= 1
    assert 0 <= result.inspection_confidence <= 1


def test_mock_service_returns_valid_result() -> None:
    result = OrvexAIService(mode="mock").analyze_image(sample_name="hotspot")
    assert result.priority == "high"
    assert result.human_review_required is True
    assert result.model_mode == "mock"


def test_extract_json_from_markdown_block() -> None:
    raw = """Here is the result:
```json
{"priority": "low", "risk": 0.1}
```
"""
    assert extract_json_object(raw) == {"priority": "low", "risk": 0.1}


def test_extract_json_rejects_invalid_output() -> None:
    with pytest.raises(JsonExtractionError):
        extract_json_object("no structured object here")
