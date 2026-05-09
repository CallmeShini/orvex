from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from app.api.job_service import InspectionJobService
from app.api.main import app
from app.api.structured_events import load_structured_events


def test_create_and_fetch_sample_inspection_job(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    create_response = client.post("/inspection-jobs", data={"sample_name": "raptormaps-hot_spot-06722"})

    assert create_response.status_code == 200
    payload = create_response.json()
    assert payload["job_id"].startswith("job-")
    assert payload["status"] == "completed"
    assert payload["source_type"] == "sample"
    assert payload["asset"]["sample_name"] == "raptormaps-hot_spot-06722"
    assert payload["result"]["priority"] == "high"
    assert payload["result"]["human_review_required"] is True
    assert payload["report_id"] == payload["result"]["inspection_id"]
    assert "Orvex Inspection Report" in payload["report_markdown"]
    assert (tmp_path / payload["job_id"] / "job.json").exists()
    assert (tmp_path / payload["job_id"] / "results" / f"{payload['result']['inspection_id']}.json").exists()
    events = load_structured_events(tmp_path / payload["job_id"] / "events.jsonl")
    assert [event["event"] for event in events] == ["job_created", "job_completed"]
    assert events[-1]["model_mode"] == payload["result"]["model_mode"]
    assert events[-1]["latency_ms"] == payload["result"]["latency_ms"]

    fetch_response = client.get(f"/inspection-jobs/{payload['job_id']}")

    assert fetch_response.status_code == 200
    assert fetch_response.json()["job_id"] == payload["job_id"]


def test_create_image_job_stores_asset_inside_job_directory(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("../panel hotspot.jpg", b"fake image bytes", "image/jpeg")},
    )

    assert response.status_code == 200
    payload = response.json()
    asset = payload["asset"]
    assert payload["source_type"] == "image"
    assert asset["filename"] == "panel hotspot.jpg"
    assert asset["storage_path"].startswith("assets/asset-")
    assert ".." not in asset["storage_path"]
    assert asset["size_bytes"] == len(b"fake image bytes")
    assert len(asset["sha256"]) == 64
    assert (tmp_path / payload["job_id"] / asset["storage_path"]).exists()
    events = load_structured_events(tmp_path / payload["job_id"] / "events.jsonl")
    assert [event["event"] for event in events] == ["job_created", "asset_saved", "job_completed"]
    asset_event = events[1]
    assert asset_event["asset_id"] == asset["asset_id"]
    assert asset_event["size_bytes"] == len(b"fake image bytes")
    assert asset_event["sha256"] == asset["sha256"]
    assert "filename" not in asset_event


def test_create_inspection_job_requires_input(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post("/inspection-jobs")

    assert response.status_code == 422
    assert "sample_name or an image file" in response.json()["detail"]


def test_create_inspection_job_rejects_video_until_pipeline_exists(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 415
    assert "Video requires the planned inspection-job pipeline" in response.json()["detail"]


def test_fetch_missing_inspection_job_returns_404(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/inspection-jobs/job-missing")

    assert response.status_code == 404
