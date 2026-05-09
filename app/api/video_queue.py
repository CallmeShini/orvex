from __future__ import annotations

import queue
import threading
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from app.api.ai_service import OrvexAIService
from app.api.job_service import InspectionJobNotFound, InspectionJobService
from app.ml.video_pipeline import DEFAULT_MAX_FRAMES, DEFAULT_VIDEO_FPS


_STOP = object()


class VideoJobQueueError(RuntimeError):
    """Raised when a video job cannot be queued for worker execution."""


class VideoJobQueueClosed(VideoJobQueueError):
    """Raised when queueing is attempted after the worker queue was closed."""


class VideoJobQueueFull(VideoJobQueueError):
    """Raised when the worker queue has reached its configured capacity."""


@dataclass(frozen=True)
class VideoJobTask:
    job_id: str
    jobs_dir: Path
    sample_fps: float = DEFAULT_VIDEO_FPS
    max_frames: int = DEFAULT_MAX_FRAMES
    ai_mode: str | None = None
    ffmpeg_bin: str = "ffmpeg"


class VideoJobQueue:
    def __init__(
        self,
        *,
        worker_count: int = 1,
        max_size: int = 32,
        ai_service_factory: Callable[[str | None], OrvexAIService] | None = None,
    ) -> None:
        if worker_count <= 0:
            raise ValueError("worker_count must be greater than 0")
        if max_size < 0:
            raise ValueError("max_size must be zero or greater")

        self.worker_count = worker_count
        self.max_size = max_size
        self._ai_service_factory = ai_service_factory or (lambda mode: OrvexAIService(mode=mode))
        self._queue: queue.Queue[VideoJobTask | object] = queue.Queue(maxsize=max_size)
        self._threads: list[threading.Thread] = []
        self._lock = threading.Lock()
        self._started = False
        self._closed = False

    @property
    def started(self) -> bool:
        return self._started

    @property
    def closed(self) -> bool:
        return self._closed

    @property
    def pending_count(self) -> int:
        return self._queue.qsize()

    def start(self) -> None:
        with self._lock:
            if self._closed:
                raise VideoJobQueueClosed("Video job queue is closed.")
            if self._started:
                return

            self._threads = [
                threading.Thread(
                    target=self._worker_loop,
                    name=f"orvex-video-worker-{index + 1}",
                    daemon=True,
                )
                for index in range(self.worker_count)
            ]
            for thread in self._threads:
                thread.start()
            self._started = True

    def stop(self, timeout_seconds: float = 5.0) -> None:
        with self._lock:
            if self._closed:
                return
            self._closed = True
            threads = list(self._threads)

        deadline = time.monotonic() + timeout_seconds
        for _thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            try:
                self._queue.put(_STOP, timeout=remaining)
            except queue.Full:
                break

        for thread in threads:
            remaining = max(0.0, deadline - time.monotonic())
            thread.join(timeout=remaining)

        with self._lock:
            self._threads = [thread for thread in self._threads if thread.is_alive()]
            self._started = bool(self._threads)

    def enqueue(self, task: VideoJobTask) -> None:
        if self._closed:
            raise VideoJobQueueClosed("Video job queue is closed.")

        self.start()
        try:
            self._queue.put_nowait(task)
        except queue.Full as exc:
            raise VideoJobQueueFull("Video job queue is full. Try again later.") from exc

    def _worker_loop(self) -> None:
        while True:
            item = self._queue.get()
            try:
                if item is _STOP:
                    return
                self._run_task(item)
            finally:
                self._queue.task_done()

    def _run_task(self, task: VideoJobTask | object) -> None:
        if not isinstance(task, VideoJobTask):
            return

        job_service = InspectionJobService(jobs_dir=task.jobs_dir)
        try:
            job_service.process_video_job(
                task.job_id,
                ai_service=self._ai_service_factory(task.ai_mode),
                sample_fps=task.sample_fps,
                max_frames=task.max_frames,
                ffmpeg_bin=task.ffmpeg_bin,
            )
        except InspectionJobNotFound:
            return
        except Exception as exc:
            try:
                job_service.mark_job_failed(task.job_id, f"Video worker failed: {exc}")
            except InspectionJobNotFound:
                return
