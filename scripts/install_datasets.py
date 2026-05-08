from __future__ import annotations

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time
import urllib.request
import zipfile
from dataclasses import asdict, dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable


IMAGE_SUFFIXES = {".jpg", ".jpeg", ".png", ".bmp", ".tif", ".tiff", ".webp"}
ANNOTATION_SUFFIXES = {".json", ".xml", ".txt", ".csv", ".yaml", ".yml"}


@dataclass(frozen=True)
class DatasetSpec:
    key: str
    title: str
    priority: str
    access: str
    path_name: str
    source_url: str
    license_status: str
    modality: str
    intended_use: str
    download_url: str | None = None
    archive_name: str | None = None
    expected_md5: str | None = None
    expected_bytes: int | None = None
    kaggle_slug: str | None = None
    notes: str = ""


DATASETS: tuple[DatasetSpec, ...] = (
    DatasetSpec(
        key="raptormaps",
        title="RaptorMaps InfraredSolarModules",
        priority="P0",
        access="direct",
        path_name="raptormaps",
        source_url="https://github.com/RaptorMaps/InfraredSolarModules",
        download_url="https://github.com/RaptorMaps/InfraredSolarModules/raw/master/2020-02-14_InfraredSolarModules.zip",
        archive_name="2020-02-14_InfraredSolarModules.zip",
        license_status="MIT",
        modality="infrared thermal classification",
        intended_use="Core classification baseline and curated thermal anomaly samples.",
        expected_bytes=15471926,
    ),
    DatasetSpec(
        key="thermal-pv-uav",
        title="Thermal PV Panel Detection and Fault Detection Dataset for UAV-Based Inspection",
        priority="P1",
        access="direct",
        path_name="thermal-pv-uav",
        source_url="https://zenodo.org/records/16420123",
        download_url="https://zenodo.org/api/records/16420123/files/Thermal%20PV%20Panel%20Detection%20Dataset%20for%20UAV%20Inspection.zip/content",
        archive_name="Thermal_PV_Panel_Detection_Dataset_for_UAV_Inspection.zip",
        expected_md5="c7c8b85ed4dbe6d7422e45b1776d3fa7",
        expected_bytes=15172606,
        license_status="CC BY 4.0",
        modality="thermal UAV object detection",
        intended_use="Optional site overview and panel localization narrative.",
    ),
    DatasetSpec(
        key="pv-multi-defect",
        title="PV-Multi-Defect",
        priority="P1",
        access="direct",
        path_name="pv-multi-defect",
        source_url="https://zenodo.org/records/15017563",
        download_url="https://zenodo.org/api/records/15017563/files/PV-Multi-Defect-main.zip/content",
        archive_name="PV-Multi-Defect-main.zip",
        expected_md5="cffbd957e8f502305191c745f0f50157",
        expected_bytes=43269389,
        license_status="CC BY 4.0 on Zenodo; upstream GitHub repository has no explicit license file.",
        modality="RGB surface defect detection",
        intended_use="Optional detection experiment after annotation format review.",
    ),
    DatasetSpec(
        key="pv-panel-defect",
        title="PV Panel Defect Dataset",
        priority="P1",
        access="kaggle",
        path_name="pv-panel-defect",
        source_url="https://www.kaggle.com/datasets/alicjalena/pv-panel-defect-dataset",
        kaggle_slug="alicjalena/pv-panel-defect-dataset",
        expected_bytes=500359961,
        license_status="CC BY-NC-SA 4.0; non-commercial research/demo only.",
        modality="RGB visual defect classification",
        intended_use="Demo-friendly visual classification supplement, not commercial evidence.",
    ),
    DatasetSpec(
        key="multimodal-ir-solar-pv-fault",
        title="Multimodal Infrared Solar PV Fault Dataset",
        priority="P2",
        access="kaggle",
        path_name="multimodal-ir-solar-pv-fault",
        source_url="https://www.kaggle.com/datasets/khawlamnsr/multimodal-infrared-solar-pv-fault-dataset",
        kaggle_slug="khawlamnsr/multimodal-infrared-solar-pv-fault-dataset",
        expected_bytes=2224885576,
        license_status="MIT according to Kaggle metadata.",
        modality="module/string/delta-temperature infrared representations",
        intended_use="Technical plus for hierarchical thermal explanation views.",
    ),
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Install Orvex solar datasets into an ignored local data directory.")
    parser.add_argument("--root", default="data/external", help="Ignored dataset root directory.")
    parser.add_argument(
        "--datasets",
        nargs="*",
        default=None,
        help="Specific dataset keys to install. Defaults to all core/P2 Orvex solar datasets.",
    )
    parser.add_argument("--direct-only", action="store_true", help="Skip Kaggle datasets even if credentials exist.")
    parser.add_argument("--kaggle-only", action="store_true", help="Skip direct public datasets.")
    parser.add_argument("--force", action="store_true", help="Redownload archives and re-extract datasets.")
    parser.add_argument("--no-extract", action="store_true", help="Download archives without extracting zip files.")
    parser.add_argument("--validate-only", action="store_true", help="Only inspect existing local dataset directories.")
    parser.add_argument("--limit-summary-files", type=int, default=8, help="Number of example files to include per dataset.")
    return parser.parse_args()


def selected_specs(args: argparse.Namespace) -> list[DatasetSpec]:
    requested = set(args.datasets or [spec.key for spec in DATASETS])
    unknown = requested.difference({spec.key for spec in DATASETS})
    if unknown:
        raise SystemExit(f"Unknown dataset key(s): {', '.join(sorted(unknown))}")

    specs = [spec for spec in DATASETS if spec.key in requested]
    if args.direct_only:
        specs = [spec for spec in specs if spec.access == "direct"]
    if args.kaggle_only:
        specs = [spec for spec in specs if spec.access == "kaggle"]
    return specs


def md5sum(path: Path) -> str:
    digest = hashlib.md5()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def download_file(url: str, destination: Path, force: bool) -> tuple[str, int]:
    if destination.exists() and not force:
        return "existing", destination.stat().st_size

    destination.parent.mkdir(parents=True, exist_ok=True)
    tmp_path = destination.with_suffix(destination.suffix + ".part")
    if tmp_path.exists():
        tmp_path.unlink()

    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": "orvex-dataset-installer/1.0",
            "Accept": "application/octet-stream,*/*",
        },
    )
    print(f"Downloading {url}", flush=True)
    started_at = time.time()
    downloaded = 0
    next_report = 25 * 1024 * 1024

    with urllib.request.urlopen(request, timeout=120) as response, tmp_path.open("wb") as handle:
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            handle.write(chunk)
            downloaded += len(chunk)
            if downloaded >= next_report:
                elapsed = max(time.time() - started_at, 0.001)
                print(f"  downloaded {downloaded / (1024 * 1024):.1f} MiB at {downloaded / elapsed / (1024 * 1024):.1f} MiB/s", flush=True)
                next_report += 25 * 1024 * 1024

    tmp_path.replace(destination)
    return "downloaded", destination.stat().st_size


def safe_extract_zip(archive_path: Path, target_dir: Path, force: bool) -> str:
    if target_dir.exists() and any(target_dir.iterdir()) and not force:
        return "existing"

    target_dir.mkdir(parents=True, exist_ok=True)
    target_root = target_dir.resolve()
    with zipfile.ZipFile(archive_path) as archive:
        for member in archive.infolist():
            destination = (target_root / member.filename).resolve()
            if target_root != destination and target_root not in destination.parents:
                raise RuntimeError(f"Blocked unsafe zip member path: {member.filename}")
        archive.extractall(target_root)
    return "extracted"


def count_tree(path: Path, limit: int) -> dict[str, object]:
    if not path.exists():
        return {
            "exists": False,
            "total_files": 0,
            "total_bytes": 0,
            "image_files": 0,
            "annotation_files": 0,
            "examples": [],
        }

    total_files = 0
    total_bytes = 0
    image_files = 0
    annotation_files = 0
    examples: list[str] = []

    for item in path.rglob("*"):
        if not item.is_file():
            continue
        total_files += 1
        try:
            total_bytes += item.stat().st_size
        except OSError:
            pass
        suffix = item.suffix.lower()
        if suffix in IMAGE_SUFFIXES:
            image_files += 1
        if suffix in ANNOTATION_SUFFIXES:
            annotation_files += 1
        if len(examples) < limit:
            examples.append(str(item.relative_to(path)))

    return {
        "exists": True,
        "total_files": total_files,
        "total_bytes": total_bytes,
        "image_files": image_files,
        "annotation_files": annotation_files,
        "examples": examples,
    }


def kaggle_command() -> list[str] | None:
    executable = shutil.which("kaggle")
    if executable:
        return [executable]

    venv_executable = Path(sys.executable).with_name("kaggle")
    if venv_executable.exists():
        return [str(venv_executable)]

    return None


def has_kaggle_credentials() -> bool:
    kaggle_json = Path.home() / ".kaggle" / "kaggle.json"
    env_credentials = bool(os.environ.get("KAGGLE_USERNAME") and os.environ.get("KAGGLE_KEY"))
    return kaggle_json.exists() or env_credentials


def install_direct(spec: DatasetSpec, dataset_dir: Path, args: argparse.Namespace) -> dict[str, object]:
    if not spec.download_url or not spec.archive_name:
        raise RuntimeError(f"{spec.key} is missing direct download metadata")

    archive_path = dataset_dir / "archives" / spec.archive_name
    raw_dir = dataset_dir / "raw"
    result: dict[str, object] = {
        "archive_path": str(archive_path),
        "raw_path": str(raw_dir),
    }

    if args.validate_only:
        result["status"] = "validated"
    else:
        action, bytes_written = download_file(spec.download_url, archive_path, args.force)
        result["download_action"] = action
        result["archive_bytes"] = bytes_written

        checksum = md5sum(archive_path)
        result["md5"] = checksum
        if spec.expected_md5 and checksum != spec.expected_md5:
            raise RuntimeError(f"{spec.key} checksum mismatch: expected {spec.expected_md5}, got {checksum}")

        if spec.expected_bytes and bytes_written != spec.expected_bytes:
            result["byte_warning"] = f"expected {spec.expected_bytes}, got {bytes_written}"

        if args.no_extract:
            result["extract_action"] = "skipped"
        else:
            result["extract_action"] = safe_extract_zip(archive_path, raw_dir, args.force)
        result["status"] = "installed"

    result["summary"] = count_tree(raw_dir, args.limit_summary_files)
    return result


def install_kaggle(spec: DatasetSpec, dataset_dir: Path, args: argparse.Namespace) -> dict[str, object]:
    raw_dir = dataset_dir / "raw"
    result: dict[str, object] = {
        "raw_path": str(raw_dir),
        "kaggle_slug": spec.kaggle_slug,
    }

    command = kaggle_command()
    if not command:
        result["status"] = "blocked"
        result["reason"] = "Kaggle CLI is not installed in this environment."
        result["next_command"] = f"{sys.executable} -m pip install kaggle"
        result["summary"] = count_tree(raw_dir, args.limit_summary_files)
        return result

    if not has_kaggle_credentials():
        result["status"] = "blocked"
        result["reason"] = "Kaggle credentials were not found. Expected ~/.kaggle/kaggle.json or KAGGLE_USERNAME/KAGGLE_KEY."
        result["next_command"] = "mkdir -p ~/.kaggle && chmod 700 ~/.kaggle && place kaggle.json there with chmod 600 ~/.kaggle/kaggle.json"
        result["summary"] = count_tree(raw_dir, args.limit_summary_files)
        return result

    if args.validate_only:
        result["status"] = "validated"
        result["summary"] = count_tree(raw_dir, args.limit_summary_files)
        return result

    raw_dir.mkdir(parents=True, exist_ok=True)
    kaggle_args = [
        *command,
        "datasets",
        "download",
        "-d",
        str(spec.kaggle_slug),
        "-p",
        str(raw_dir),
        "--unzip",
        "--force",
    ]
    print(f"Downloading Kaggle dataset {spec.kaggle_slug}", flush=True)
    subprocess.run(kaggle_args, check=True)
    result["status"] = "installed"
    result["summary"] = count_tree(raw_dir, args.limit_summary_files)
    return result


def install_dataset(spec: DatasetSpec, root: Path, args: argparse.Namespace) -> dict[str, object]:
    dataset_dir = root / spec.path_name
    dataset_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n== {spec.key}: {spec.title} ==", flush=True)

    base = {
        "dataset": asdict(spec),
        "local_path": str(dataset_dir),
        "started_at": datetime.now(timezone.utc).isoformat(),
    }
    try:
        if spec.access == "direct":
            operation = install_direct(spec, dataset_dir, args)
        elif spec.access == "kaggle":
            operation = install_kaggle(spec, dataset_dir, args)
        else:
            raise RuntimeError(f"Unsupported access mode: {spec.access}")
        base.update(operation)
    except Exception as exc:  # noqa: BLE001 - capture per-dataset failures in the manifest.
        base["status"] = "error"
        base["error"] = str(exc)
    finally:
        base["finished_at"] = datetime.now(timezone.utc).isoformat()

    print(f"  status: {base.get('status')}", flush=True)
    if base.get("reason"):
        print(f"  reason: {base['reason']}", flush=True)
    if base.get("error"):
        print(f"  error: {base['error']}", flush=True)
    return base


def write_manifest(root: Path, results: Iterable[dict[str, object]]) -> Path:
    manifest_dir = root / "_manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    manifest_path = manifest_dir / "dataset_install_manifest.json"
    result_list = list(results)
    payload = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "root": str(root),
        "summary": {
            "installed": sum(1 for item in result_list if item.get("status") == "installed"),
            "validated": sum(1 for item in result_list if item.get("status") == "validated"),
            "blocked": sum(1 for item in result_list if item.get("status") == "blocked"),
            "error": sum(1 for item in result_list if item.get("status") == "error"),
        },
        "results": result_list,
    }
    manifest_path.write_text(json.dumps(payload, indent=2, sort_keys=True) + "\n", encoding="utf-8")
    return manifest_path


def main() -> None:
    args = parse_args()
    if args.direct_only and args.kaggle_only:
        raise SystemExit("--direct-only and --kaggle-only cannot be used together")

    root = Path(args.root).expanduser().resolve()
    root.mkdir(parents=True, exist_ok=True)
    specs = selected_specs(args)

    print(f"Dataset root: {root}")
    print("Selected datasets: " + ", ".join(spec.key for spec in specs))
    results = [install_dataset(spec, root, args) for spec in specs]
    manifest_path = write_manifest(root, results)
    print(f"\nManifest written to {manifest_path}")

    failures = [item for item in results if item.get("status") == "error"]
    if failures:
        raise SystemExit(1)


if __name__ == "__main__":
    main()
