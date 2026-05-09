from __future__ import annotations

import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.ai_service import OrvexAIService
from app.api.job_service import InspectionJobService
from app.api.main import app, enqueue_pending_video_jobs
from app.api.schemas import InspectionJobStatus
from app.api.structured_events import load_structured_events
from app.api.video_queue import VideoJobQueueFull
from app.ml.video_pipeline import ExtractedFrame


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
    assert "sample_name or an image/video file" in response.json()["detail"]


def test_create_inspection_job_rejects_video_when_upload_flag_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.delenv("ORVEX_ENABLE_VIDEO_UPLOAD", raising=False)
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 415
    assert "Video upload is disabled" in response.json()["detail"]


def test_create_inspection_job_rejects_video_when_processing_mode_disabled(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORVEX_ENABLE_VIDEO_UPLOAD", "true")
    monkeypatch.delenv("ORVEX_VIDEO_PROCESSING_MODE", raising=False)
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 503
    assert "no video processing mode is active" in response.json()["detail"]


def test_create_inspection_job_rejects_oversized_video(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORVEX_ENABLE_VIDEO_UPLOAD", "true")
    monkeypatch.setenv("ORVEX_VIDEO_PROCESSING_MODE", "background")
    monkeypatch.setenv("ORVEX_MAX_VIDEO_UPLOAD_BYTES", "3")
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 413
    assert "3 byte limit" in response.json()["detail"]


def test_create_inspection_job_accepts_video_and_queues_processing(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORVEX_ENABLE_VIDEO_UPLOAD", "true")
    monkeypatch.setenv("ORVEX_VIDEO_PROCESSING_MODE", "queue")
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    enqueued_tasks = []

    class FakeVideoQueue:
        def enqueue(self, task) -> None:
            enqueued_tasks.append(task)

    monkeypatch.setattr("app.api.main.get_video_job_queue", lambda: FakeVideoQueue())
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        data={"sample_fps": "0.5", "max_frames": "3"},
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "queued"
    assert payload["source_type"] == "video"
    assert payload["asset"]["filename"] == "inspection.mp4"
    assert payload["asset"]["storage_path"].startswith("assets/asset-")
    assert payload["video_processing"] == {"sample_fps": 0.5, "max_frames": 3}
    assert len(enqueued_tasks) == 1
    assert enqueued_tasks[0].job_id == payload["job_id"]
    assert enqueued_tasks[0].jobs_dir == tmp_path
    assert enqueued_tasks[0].sample_fps == 0.5
    assert enqueued_tasks[0].max_frames == 3


def test_create_inspection_job_marks_video_failed_when_queue_is_full(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setenv("ORVEX_ENABLE_VIDEO_UPLOAD", "true")
    monkeypatch.setenv("ORVEX_VIDEO_PROCESSING_MODE", "queue")
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))

    class FullVideoQueue:
        def enqueue(self, task) -> None:
            raise VideoJobQueueFull("Video job queue is full. Try again later.")

    monkeypatch.setattr("app.api.main.get_video_job_queue", lambda: FullVideoQueue())
    client = TestClient(app)

    response = client.post(
        "/inspection-jobs",
        files={"file": ("inspection.mp4", b"fake video bytes", "video/mp4")},
    )

    assert response.status_code == 503
    assert "queue is full" in response.json()["detail"]
    job_paths = list(tmp_path.glob("job-*/job.json"))
    assert len(job_paths) == 1
    job_payload = json.loads(job_paths[0].read_text(encoding="utf-8"))
    assert job_payload["status"] == "failed"
    assert "queue is full" in job_payload["error"]


def test_process_video_job_writes_aggregate_result(tmp_path: Path, monkeypatch) -> None:
    frame_path = tmp_path / "frame-000001.jpg"
    frame_path.write_bytes(b"frame")

    def fake_extract_video_frames(**kwargs) -> list[ExtractedFrame]:
        return [ExtractedFrame(frame_index=0, timestamp_ms=0, path=frame_path, sha256="abc")]

    monkeypatch.setattr("app.api.job_service.extract_video_frames", fake_extract_video_frames)
    service = InspectionJobService(jobs_dir=tmp_path)
    job = service.create_video_job(
        filename="inspection.mp4",
        media_type="video/mp4",
        file_obj=BytesReader(b"fake video bytes"),
        max_bytes=1024,
    )

    completed = service.process_video_job(job.job_id, ai_service=OrvexAIService())

    assert completed.status == "completed"
    assert completed.result is not None
    assert completed.video_result is not None
    assert completed.video_result.summary.frames_analyzed == 1
    assert (tmp_path / job.job_id / "results" / "video_evaluation.json").exists()


def test_enqueue_pending_video_jobs_uses_persisted_sampling_params(tmp_path: Path) -> None:
    service = InspectionJobService(jobs_dir=tmp_path)
    job = service.create_video_job(
        filename="inspection.mp4",
        media_type="video/mp4",
        file_obj=BytesReader(b"fake video bytes"),
        max_bytes=1024,
        sample_fps=0.25,
        max_frames=7,
    )
    enqueued_tasks = []

    class FakeVideoQueue:
        def enqueue(self, task) -> None:
            enqueued_tasks.append(task)

    enqueue_pending_video_jobs(queue=FakeVideoQueue(), job_service=service)

    assert len(enqueued_tasks) == 1
    assert enqueued_tasks[0].job_id == job.job_id
    assert enqueued_tasks[0].sample_fps == 0.25
    assert enqueued_tasks[0].max_frames == 7


def test_enqueue_pending_video_jobs_recovers_interrupted_processing_jobs(tmp_path: Path) -> None:
    service = InspectionJobService(jobs_dir=tmp_path)
    queued_job = service.create_video_job(
        filename="queued.mp4",
        media_type="video/mp4",
        file_obj=BytesReader(b"queued video bytes"),
        max_bytes=1024,
    )
    processing_job = service.create_video_job(
        filename="processing.mp4",
        media_type="video/mp4",
        file_obj=BytesReader(b"processing video bytes"),
        max_bytes=1024,
    )
    service._write(processing_job.model_copy(update={"status": InspectionJobStatus.PROCESSING}))
    enqueued_tasks = []

    class FakeVideoQueue:
        def enqueue(self, task) -> None:
            enqueued_tasks.append(task)

    enqueue_pending_video_jobs(queue=FakeVideoQueue(), job_service=service)

    assert {task.job_id for task in enqueued_tasks} == {queued_job.job_id, processing_job.job_id}


def test_fetch_missing_inspection_job_returns_404(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.setattr("app.api.main.get_job_service", lambda: InspectionJobService(jobs_dir=tmp_path))
    client = TestClient(app)

    response = client.get("/inspection-jobs/job-missing")

    assert response.status_code == 404


class BytesReader:
    def __init__(self, payload: bytes) -> None:
        self.payload = payload
        self.position = 0

    def read(self, size: int = -1) -> bytes:
        if self.position >= len(self.payload):
            return b""
        if size < 0:
            size = len(self.payload) - self.position
        end_position = min(self.position + size, len(self.payload))
        chunk = self.payload[self.position : end_position]
        self.position = end_position
        return chunk
