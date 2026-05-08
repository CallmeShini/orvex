# Submission Checklist

## Product

- [ ] Upload image works.
- [ ] Batch upload works or is explicitly out of scope.
- [ ] Analysis returns validated JSON.
- [ ] Findings show risk score, priority, evidence, and recommended action.
- [ ] Human review state is visible.
- [ ] Report export works.
- [ ] Mock fallback works transparently.

## AI

- [ ] Model selected and documented.
- [ ] Runtime documented.
- [ ] Prompt versioned.
- [ ] Schema versioned.
- [ ] Output validation implemented.
- [ ] Invalid JSON fallback implemented.
- [ ] Latency and failure logs captured.
- [ ] Small manual evaluation set prepared.

## AMD Narrative

- [ ] Explain why multimodal inspection matters.
- [ ] Explain why MI300X/ROCm matters.
- [ ] Show open-source model/runtime path.
- [ ] Avoid unverified performance or accuracy claims.
- [ ] Mention human-in-the-loop safety boundary.

## ROCm Evidence

- [ ] Evidence run directory captured under ignored `logs/evidence/`.
- [ ] Repository commit and dirty state captured.
- [ ] Runtime evidence includes `torch`, HIP/ROCm, `amd-smi` or `rocm-smi`, and device name.
- [ ] Video/frame run records source permission, `sample_fps`, `max_frames`, frame count, and failures.
- [ ] Aggregated result shows human-review requirement and representative timestamped frame.
- [ ] Claims distinguish offline evidence from public video upload support.

## Demo Assets

- [ ] Two-minute demo script.
- [ ] Demo image set with normal, suspected, and inconclusive cases.
- [ ] README tested from clean clone.
- [ ] Public demo URL tested.
- [ ] Video recorded.
- [ ] Slides exported.
- [ ] Cover image prepared.
- [ ] Repository cleaned of secrets and heavy data.

## Claims Allowed

- [ ] AI-assisted visual triage.
- [ ] Human-in-the-loop solar inspection workflow.
- [ ] Structured preliminary maintenance report.
- [ ] Open VLM workflow targeting AMD ROCm/MI300X.
- [ ] Offline frame-evaluation evidence run on AMD ROCm/MI300X when runtime artifacts are shown.

## Claims Prohibited

- [ ] 99% accurate without benchmark.
- [ ] Replaces technicians.
- [ ] Guarantees fault detection.
- [ ] Fully automates maintenance decisions.
- [ ] Commercially ready without validation, licensing, and owned/cleared data.
