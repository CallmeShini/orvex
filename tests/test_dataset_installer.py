from __future__ import annotations

import json
import zipfile
from pathlib import Path

import pytest

from scripts.install_datasets import DATASETS, count_tree, safe_extract_zip, write_manifest


def test_dataset_keys_are_unique() -> None:
    keys = [dataset.key for dataset in DATASETS]
    assert len(keys) == len(set(keys))


def test_core_sources_do_not_include_medical_datasets() -> None:
    titles = " ".join(dataset.title.lower() for dataset in DATASETS)
    assert "brain" not in titles
    assert "skin" not in titles


def test_count_tree_counts_images_and_annotations(tmp_path: Path) -> None:
    (tmp_path / "images").mkdir()
    (tmp_path / "labels").mkdir()
    (tmp_path / "images" / "sample.jpg").write_bytes(b"fake-image")
    (tmp_path / "labels" / "sample.json").write_text("{}", encoding="utf-8")

    summary = count_tree(tmp_path, limit=4)

    assert summary["exists"] is True
    assert summary["total_files"] == 2
    assert summary["image_files"] == 1
    assert summary["annotation_files"] == 1


def test_safe_extract_blocks_zip_slip(tmp_path: Path) -> None:
    archive_path = tmp_path / "unsafe.zip"
    with zipfile.ZipFile(archive_path, "w") as archive:
        archive.writestr("../escape.txt", "bad")

    with pytest.raises(RuntimeError, match="unsafe zip member"):
        safe_extract_zip(archive_path, tmp_path / "raw", force=True)


def test_write_manifest_uses_ignored_external_root(tmp_path: Path) -> None:
    manifest_path = write_manifest(tmp_path / "data" / "external", [{"status": "blocked"}])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))

    assert payload["summary"]["blocked"] == 1
    assert manifest_path.name == "dataset_install_manifest.json"
