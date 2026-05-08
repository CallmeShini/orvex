# Evaluation Data

This directory stores small, versionable dataset-intake artifacts for Orvex.

Raw datasets are not committed to Git. The RaptorMaps raw files are expected locally under `data/external/raptormaps/`, which is ignored by Git.

## Files

- `raptormaps_manifest.jsonl`: selected RaptorMaps samples with source labels, local raw paths, license, and Orvex operational buckets.
- `expected_outputs/`: expected Orvex `InspectionResult` JSON payloads for the selected samples.

These expected outputs are not model predictions. They are curated reference outputs used to validate the product contract and demo flow before connecting live inference.

Video/frame evidence manifests belong under ignored `logs/evidence/` by default because they can expose raw media paths and operational run context. If a tiny manifest is later promoted into `data/evaluation/`, keep it media-free and document it as an evaluation artifact, not a raw dataset.
