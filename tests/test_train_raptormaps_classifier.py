from __future__ import annotations

from pathlib import Path

import pytest

from app.ml.raptormaps_classifier import RaptorMapsRecord
from scripts.train_raptormaps_classifier import metric_is_better, validate_split_support


def test_metric_is_better_prefers_higher_quality_metrics() -> None:
    assert metric_is_better("macro_recall", 0.4, None) is True
    assert metric_is_better("macro_recall", 0.41, 0.4) is True
    assert metric_is_better("accuracy", 0.39, 0.4) is False


def test_metric_is_better_prefers_lower_loss() -> None:
    assert metric_is_better("loss", 1.9, None) is True
    assert metric_is_better("loss", 1.8, 1.9) is True
    assert metric_is_better("loss", 2.0, 1.9) is False


def test_validate_split_support_rejects_missing_classes() -> None:
    records = [RaptorMapsRecord(image_id="1", image_path=Path("x.jpg"), label="No-Anomaly")]

    with pytest.raises(ValueError, match="missing_train"):
        validate_split_support(records, records)
