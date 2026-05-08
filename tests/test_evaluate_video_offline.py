from __future__ import annotations

import pytest

from scripts.evaluate_video_offline import reject_url


def test_reject_url_disallows_remote_video_inputs() -> None:
    with pytest.raises(ValueError, match="local file path"):
        reject_url("https://example.com/inspection.mp4")


def test_reject_url_allows_local_video_paths() -> None:
    reject_url("/tmp/inspection.mp4")
