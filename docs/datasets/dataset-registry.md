# Dataset Registry

Updated: 2026-05-08

This registry tracks candidate datasets for the Orvex hackathon scope and separates demo/research use from future commercial assumptions.

Every dataset must be reviewed before being used for any commercial claim. Do not commit large datasets to this repository.

## Scope Decision

Orvex is currently a solar inspection product. Medical datasets shared earlier in the team channel, such as skin disease and brain tumor MRI datasets, are out of scope for this product line and should not be mixed into the Orvex repo, demo, or evaluation story.

## Priority Registry

| Priority | Dataset | Source | Modality | Primary Use | Labels / Structure | License Status | Hackathon Use | Commercial Use | Decision |
|---|---|---|---|---|---|---|---|---|---|
| P0 | RaptorMaps InfraredSolarModules | https://github.com/RaptorMaps/InfraredSolarModules | Infrared / thermal | Main classification baseline and thermal anomaly examples | 20,000 images, 24x40 px, 12 classes | MIT on GitHub | Use first | Likely acceptable after attribution/source review | Core dataset |
| P1 | PV Panel Defect Dataset | https://www.kaggle.com/datasets/alicjalena/pv-panel-defect-dataset | RGB / visible | Demo-friendly visual defect examples | 1,574 images, 6 classes | CC BY-NC-SA 4.0 / non-commercial | Research/demo only | Not acceptable without new data or license clearance | Demo supplement |
| P1 | Thermal PV Panel Detection and Fault Detection Dataset | https://zenodo.org/records/16420123 | Thermal / UAV | Optional site overview and panel localization | 353 images, 26,678 annotated panels | CC BY 4.0 on Zenodo | Useful if localization is needed | Possible with attribution/source review | Optional UAV narrative |
| P1 | PV-Multi-Defect | https://github.com/CCNUZFW/PV-Multi-Defect / https://zenodo.org/records/15017563 | RGB / surface defects | Optional detection experiment | Images plus annotations, 5 visible defect types in repo README | Zenodo mirror is CC BY 4.0; original repo license still needs review | Use only after annotation/license check | Needs source review | Optional YOLO/detection plus |
| P2 | Multimodal Infrared Solar PV Fault Dataset | https://www.kaggle.com/datasets/khawlamnsr/multimodal-infrared-solar-pv-fault-dataset | Infrared / derived multimodal | Module/string/Delta T explanation view | Module-level, string-level and Delta T representations | MIT according to Kaggle page | Good plus if opened quickly | Likely acceptable after source review | Technical plus |
| P3 | THED-PV | https://zenodo.org/records/17404247 | High-resolution thermal | Future homography/alignment roadmap | 12,460 raw images and 99,680 homography pairs | CC BY 4.0 on Zenodo | Too large for core hackathon flow | Possible with attribution/source review | Roadmap only |
| P3 | Large PV Thermal Defects Pretraining Dataset | https://zenodo.org/records/14644158 | Thermal / curated aggregate | Future pretraining/fine-tuning | 1.4 GB curated thermal defects dataset | CC BY 4.0 on Zenodo | Avoid unless team finishes early | Possible with attribution/source review | Roadmap only |

## Operational Taxonomy

For the hackathon, do not preserve every source label as a top-level product category. Normalize dataset labels into Orvex operational buckets:

| Orvex Bucket | Meaning | Example Source Labels |
|---|---|---|
| `healthy` | No clear anomaly visible | No-Anomaly, Clean |
| `surface_obstruction` | Visual or thermal obstruction affecting inspection or generation | Soiling, Shadowing, Vegetation, Dusty, Bird-drop, Snow-covered |
| `structural_fault` | Physical damage or surface degradation | Cracking, Physical-damage, broken areas, scratches, black/gray border areas |
| `electrical_fault` | Thermal/electrical fault signature | Cell, Cell-Multi, Hot-Spot, Hot-Spot-Multi, Diode, Diode-Multi, Offline-Module, Electrical-damage |
| `inconclusive` | Image cannot support a reliable triage result | Ambiguous, low-quality, non-solar, unsupported modality |

Keep the original dataset labels as `source_label` metadata so we can trace results back to the source.

## Intake Rules

- Do not version raw datasets in Git.
- Keep raw data outside the repository, preferably under a local ignored path such as `data/external/`.
- Use `scripts/install_datasets.py` for repeatable VPS/local dataset intake instead of manual one-off downloads.
- Keep only small demo samples in Git if license and attribution allow it.
- Store a manifest before model work: source URL, local path, license, modality, original label, Orvex bucket, split, and notes.
- Mark non-commercial datasets clearly as demo/research only.
- Do not make accuracy, safety, production, or commercial claims from public datasets without controlled validation.

## VPS Dataset Install

Run from the repository root on the VPS:

```bash
.venv/bin/python scripts/install_datasets.py
```

This installs the project-relevant solar datasets under the ignored `data/external/` tree and writes a local manifest to:

```txt
data/external/_manifests/dataset_install_manifest.json
```

Expected behavior:

- Direct public datasets download and extract automatically:
  - `raptormaps`
  - `thermal-pv-uav`
  - `pv-multi-defect`
- Kaggle datasets are attempted only when Kaggle CLI and credentials exist:
  - `pv-panel-defect`
  - `multimodal-ir-solar-pv-fault`
- If Kaggle credentials are missing, the manifest records a `blocked` status and the exact next command/setup note. Do not commit `kaggle.json`.

Useful focused runs:

```bash
.venv/bin/python scripts/install_datasets.py --direct-only
.venv/bin/python scripts/install_datasets.py --kaggle-only
.venv/bin/python scripts/install_datasets.py --validate-only
.venv/bin/python scripts/install_datasets.py --datasets raptormaps pv-panel-defect
```

## Completed Intake Slice

The first intake slice was completed before supervised training:

```txt
download/open RaptorMaps
-> inspect metadata
-> select 20-40 representative images
-> map source labels to Orvex buckets
-> create a manifest
-> generate expected JSON examples
-> connect selected samples to the existing FastAPI + Streamlit flow
```

Tracked outputs:

- `data/evaluation/raptormaps_manifest.jsonl`
- `data/evaluation/expected_outputs/`
- `docs/ml/raptormaps-supervised-baseline-rocm.md`

The next dataset step is not to add unrelated medical or generic vision datasets. It is to use the existing RaptorMaps split and optional PV datasets to compare three paths:

```txt
expected contract outputs
-> Qwen2.5-VL smoke outputs
-> supervised ROCm classifier outputs
```

This keeps evaluation traceable and prevents the demo from mixing incompatible problem domains.

## Video Evidence Inputs

The offline video pipeline may use local video files for evidence runs, but raw media must remain outside Git.

Track each video input in the run directory metadata instead of committing the file:

```txt
logs/evidence/video-eval-<run_id>/video_evaluation.json
```

Required notes for any video used in a presentation:

- source and permission/license status;
- whether the file is team-owned, public, or research/demo only;
- modality, site context, and whether it shows real solar panels;
- sampling config: `sample_fps`, `max_frames`, and extracted frame count;
- claim boundary: offline evidence only, not public video upload support.
