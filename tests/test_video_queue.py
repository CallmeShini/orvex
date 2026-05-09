from __future__ import annotations

import threading
from pathlib import Path

from app.api.video_queue import VideoJobQueue, VideoJobTask


def test_video_job_queue_runs_task_with_worker(tmp_path: Path, monkeypatch) -> None:
    processed = []
    processed_event = threading.Event()

    def fake_process_video_job(self, job_id, ai_service, sample_fps, max_frames, ffmpeg_bin="ffmpeg"):
        processed.append(
            {
                "jobs_dir": self.jobs_dir,
                "job_id": job_id,
                "ai_mode": ai_service.mode,
                "sample_fps": sample_fps,
                "max_frames": max_frames,
                "ffmpeg_bin": ffmpeg_bin,
            }
        )
        processed_event.set()

    monkeypatch.setattr(
        "app.api.video_queue.InspectionJobService.process_video_job",
        fake_process_video_job,
    )
    queue = VideoJobQueue(worker_count=1, max_size=2)

    try:
        queue.enqueue(
            VideoJobTask(
                job_id="job-test",
                jobs_dir=tmp_path,
                sample_fps=0.5,
                max_frames=3,
                ai_mode="mock",
                ffmpeg_bin="ffmpeg-test",
            )
        )

        assert processed_event.wait(timeout=2)
        assert processed == [
            {
                "jobs_dir": tmp_path,
                "job_id": "job-test",
                "ai_mode": "mock",
                "sample_fps": 0.5,
                "max_frames": 3,
                "ffmpeg_bin": "ffmpeg-test",
            }
        ]
    finally:
        queue.stop()
