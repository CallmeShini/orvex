# Orvex

Orvex is an AI-assisted inspection copilot for photovoltaic operations and maintenance teams.

The product turns solar inspection imagery into prioritized, human-reviewable maintenance findings. The initial hackathon scope focuses on thermal and RGB solar panel images, structured VLM analysis, risk prioritization, and exportable inspection reports.

## Product Position

Orvex is not a definitive diagnostic system and does not replace field technicians. It is a human-in-the-loop triage workflow for accelerating review, surfacing visual evidence, and standardizing preliminary maintenance reports.

## Current Phase

This repository is the execution source of truth for product, architecture, AI contracts, datasets, and demo planning.

The GPU VPS is reserved for serious model validation and inference work only. Product planning, contracts, local mock flows, documentation, and reviewable implementation should happen outside the VPS first.

## Repository Map

```txt
docs/
  product/
    product-brief.md
    mvp-scope.md
  architecture/
    architecture-principles.md
  ai-contracts/
    vlm-contract-v1.md
  datasets/
    dataset-registry.md
  demo/
    submission-checklist.md
```

## Near-Term Goal

Build a production-compatible hackathon MVP:

```txt
upload images
-> multimodal analysis or transparent mock fallback
-> validated JSON
-> risk prioritization
-> human review
-> exportable report
```

## Operating Rules

- Keep product decisions documented before implementation.
- Do not use the VPS as a scratch environment.
- Keep VLM behavior constrained by versioned prompts and schemas.
- Treat all model outputs as suggestions that require validation and human review.
- Avoid claims about accuracy, autonomy, certification, or commercial readiness without evidence.
