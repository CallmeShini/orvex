from __future__ import annotations

from io import BytesIO
import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from app.api.main import app
from app.api.ai_service import AiServiceError, OrvexAIService
from app.api.json_utils import JsonExtractionError, extract_json_object
from app.api.schemas import InspectionResult


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SAMPLES_DIR = PROJECT_ROOT / "data" / "samples"
EVALUATION_DIR = PROJECT_ROOT / "data" / "evaluation"
EXPECTED_OUTPUTS_DIR = EVALUATION_DIR / "expected_outputs"


class FakeLocalVLMClient:
    model_name = "fake-qwen-vl"

    def __init__(self, raw_output: str) -> None:
        self.raw_output = raw_output
        self.received_image_path: Path | None = None
        self.received_prompt = ""

    def analyze(self, image_path: Path, prompt: str) -> str:
        self.received_image_path = image_path
        self.received_prompt = prompt
        return self.raw_output


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


def test_local_vlm_mode_validates_model_json() -> None:
    fake_client = FakeLocalVLMClient(
        json.dumps(
            {
                "image_modality": "infrared",
                "contains_solar_panel": True,
                "inspection_confidence": 0.72,
                "overall_risk_score": 0.68,
                "priority": "high",
                "findings": [
                    {
                        "defect_type": "hotspot",
                        "severity": "high",
                        "confidence": 0.7,
                        "location_hint": "center module area",
                        "visual_evidence": "possible localized thermal anomaly",
                        "recommended_action": "review against string telemetry",
                    }
                ],
                "human_review_required": True,
                "summary": "Possible hotspot requires technician review.",
            }
        )
    )

    result = OrvexAIService(mode="local", local_vlm_client=fake_client).analyze_image(
        filename="uploaded-panel.jpg",
        file_obj=BytesIO(b"fake image bytes"),
    )

    assert result.priority == "high"
    assert result.model_mode == "local"
    assert result.model_name == "fake-qwen-vl"
    assert result.raw_model_output is not None
    assert fake_client.received_image_path is not None
    assert fake_client.received_image_path.name.endswith("-uploaded-panel.jpg")
    assert fake_client.received_image_path.name != "uploaded-panel.jpg"
    assert "return only one valid JSON object" in fake_client.received_prompt


def test_local_vlm_mode_reuses_default_client(monkeypatch: pytest.MonkeyPatch) -> None:
    raw_output = json.dumps(
        {
            "image_modality": "infrared",
            "contains_solar_panel": True,
            "inspection_confidence": 0.72,
            "overall_risk_score": 0.68,
            "priority": "high",
            "findings": [],
            "human_review_required": True,
            "summary": "Possible issue requires technician review.",
        }
    )
    instances: list[FakeLocalVLMClient] = []

    class CountingLocalVLMClient(FakeLocalVLMClient):
        def __init__(self) -> None:
            super().__init__(raw_output)
            self.calls = 0
            instances.append(self)

        def analyze(self, image_path: Path, prompt: str) -> str:
            self.calls += 1
            return super().analyze(image_path=image_path, prompt=prompt)

    monkeypatch.setattr("app.api.ai_service.LocalVLMClient", CountingLocalVLMClient)

    service = OrvexAIService(mode="local")
    service.analyze_image(filename="first-panel.jpg", file_obj=BytesIO(b"fake image bytes"))
    service.analyze_image(filename="second-panel.jpg", file_obj=BytesIO(b"fake image bytes"))

    assert len(instances) == 1
    assert instances[0].calls == 2


def test_local_vlm_mode_rejects_invalid_json() -> None:
    fake_client = FakeLocalVLMClient("not-json")

    with pytest.raises(AiServiceError, match="Local VLM output could not be validated"):
        OrvexAIService(mode="local", local_vlm_client=fake_client).analyze_image(
            filename="uploaded-panel.jpg",
            file_obj=BytesIO(b"fake image bytes"),
        )


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


def test_official_demo_path_is_ordered_and_traceable() -> None:
    service = OrvexAIService(mode="mock")
    demo_samples = [sample for sample in service.list_samples() if sample["is_demo"]]

    assert [sample["name"] for sample in demo_samples] == [
        "raptormaps-no_anomaly-10000",
        "raptormaps-soiling-08157",
        "raptormaps-cracking-06971",
        "raptormaps-hot_spot-06722",
        "raptormaps-offline_module-00000",
        "inconclusive",
    ]
    assert [sample["demo_order"] for sample in demo_samples] == [1, 2, 3, 4, 5, 6]
    assert all(sample["claim_boundary"] for sample in demo_samples)
    assert all(sample["expected_output_source"] for sample in demo_samples)


def test_analyze_rejects_non_image_upload() -> None:
    client = TestClient(app)
    response = client.post(
        "/analyze",
        files={"file": ("inspection.txt", b"not an image", "text/plain")},
    )

    assert response.status_code == 415
    assert "accepts image inputs only" in response.json()["detail"]


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
