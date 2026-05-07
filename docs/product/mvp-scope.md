# MVP Scope

## Objective

Deliver a navigable end-to-end workflow for the AMD hackathon:

```txt
upload
-> analysis
-> validated structured output
-> prioritization
-> human review
-> report
```

## Must-Have

- Upload one or more solar inspection images.
- Run analysis through a VLM or transparent mock fallback.
- Return validated JSON.
- Display priority, risk score, findings, evidence, and recommended action.
- Mark whether human review is required.
- Export a Markdown or JSON report.
- Include a fallback mode with precomputed sample outputs.

## Should-Have

- Batch upload.
- Inspection queue.
- Result detail screen.
- Review status: approve, correct, or mark inconclusive.
- Basic logging for model mode, prompt version, schema version, latency, and failures.

## Could-Have

- Video frame sampling.
- Lightweight classifier or detector baseline.
- Simple dashboard metrics.
- Hugging Face Space deployment.
- Small benchmark table.

## Out of Scope for the Hackathon Core

- Heavy VLM fine-tuning.
- Multi-tenant SaaS.
- Authentication and billing.
- Complex maps or GIS integrations.
- Kubernetes or distributed serving.
- Pixel-perfect segmentation.
- Legal, warranty, or safety certification.

## Demo Acceptance Criteria

The MVP is demo-ready when an external reviewer can:

1. Open the app.
2. Upload a solar inspection image or sample batch.
3. Trigger analysis.
4. See validated structured findings.
5. Understand priority and recommended next action.
6. Mark or understand human review state.
7. Export or view a report.
8. See the same flow work in fallback mode if live inference is unavailable.
