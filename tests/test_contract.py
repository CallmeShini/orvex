from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.api.ai_service import OrvexAIService
from app.api.json_utils import JsonExtractionError, extract_json_object
from app.api.schemas import InspectionResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
EVALUATION_DIR = PROJECT_ROOT / "data" / "evaluation"
EXPECTED_OUTPUTS_DIR = EVALUATION_DIR / "expected_outputs"


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


def test_raptormaps_manifest_has_expected_outputs() -> None:
    manifest_path = EVALUATION_DIR / "raptormaps_manifest.jsonl"
    entries = [
        json.loads(line)
        for line in manifest_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert len(entries) == 24
    assert {entry["dataset"] for entry in entries} == {"RaptorMaps InfraredSolarModules"}
    assert {"healthy", "surface_obstruction", "structural_fault", "electrical_fault"} <= {
        entry["orvex_bucket"] for entry in entries
    }

    for entry in entries:
        expected_path = EXPECTED_OUTPUTS_DIR / f"{entry['sample_id']}.json"
        assert expected_path.exists()
        payload = json.loads(expected_path.read_text(encoding="utf-8"))
        InspectionResult.model_validate(payload)


def test_service_lists_and_loads_dataset_expected_sample() -> None:
    service = OrvexAIService(mode="mock")
    samples = service.list_samples()
    dataset_samples = [sample for sample in samples if sample["kind"] == "dataset_expected"]
    assert dataset_samples

    result = service.analyze_image(sample_name=dataset_samples[0]["name"])
    assert result.inspection_id == dataset_samples[0]["name"]
    assert result.model_mode == "mock:dataset_expected"


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
