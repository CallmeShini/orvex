# Official Demo Path

Updated: 2026-05-08

This is the recommended local walkthrough for the hackathon demo.

The path uses five curated RaptorMaps expected outputs plus one mock fallback. These are not live model predictions. They are reference outputs for validating the Orvex product flow before `AI_MODE=local` is connected to GPU inference.

| Order | Sample ID | Demo Role | Priority | Purpose |
|---:|---|---|---|---|
| 1 | `raptormaps-no_anomaly-10000` | baseline | low | Establishes a normal thermal module reference and shows the app does not force defects. |
| 2 | `raptormaps-soiling-08157` | maintenance | medium | Shows an actionable surface obstruction/cleaning case. |
| 3 | `raptormaps-cracking-06971` | human_review_limit | medium | Shows a structural suspicion that requires RGB or field confirmation. |
| 4 | `raptormaps-hot_spot-06722` | high_priority_fault | high | Shows a localized electrical hotspot with clear maintenance priority. |
| 5 | `raptormaps-offline_module-00000` | critical_escalation | critical | Shows a critical electrical escalation case. |
| 6 | `inconclusive` | fallback | inconclusive | Shows that weak evidence routes to human review instead of a forced diagnosis. |

## Demo Script

1. Start with `Normal module reference` and explain the human-in-the-loop boundary.
2. Move to `Soiling review` and show the system can produce a lower-severity maintenance action.
3. Move to `Cracking confirmation` and call out that thermal-only evidence should not be overclaimed.
4. Move to `Localized hotspot` and show high-priority triage.
5. Move to `Offline module escalation` and show critical prioritization.
6. Finish with `Inconclusive review` to prove the fallback is explicit and safe.

## Claim Boundary

- Do not describe these expected outputs as model accuracy.
- Do not claim technician replacement.
- Do not claim commercial readiness.
- Do describe them as a traceable evaluation/demo path using real RaptorMaps samples and curated reference outputs.

## Offline ROCm Evidence Add-On

If the final presentation includes video, frame it as an offline evidence run, not as public product upload:

```txt
short local video
-> timestamped frame extraction
-> per-frame Orvex inspection contract
-> aggregated triage summary
-> ROCm/MI300X runtime evidence
```

Required details to show:

- run directory under `logs/evidence/video-eval-<timestamp>/`;
- repository commit;
- source video origin and license/permission status;
- `sample_fps` and `max_frames`;
- number of frames extracted and analyzed;
- aggregate priority, human-review state, and representative timestamp;
- `runtime_evidence.json` proving the AMD/ROCm runtime context.
