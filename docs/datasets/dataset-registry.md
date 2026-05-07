# Dataset Registry

This registry tracks candidate datasets for the hackathon and separates demo/research use from future commercial assumptions.

Every dataset must be reviewed before being used for any commercial claim.

| Dataset | Modality | Primary Use | Labels | License | Hackathon Use | Commercial Use | Priority | Notes |
|---|---|---|---|---|---|---|---|---|
| RaptorMaps InfraredSolarModules | Infrared / thermal | Initial evaluation and anomaly examples | Anomaly classes | MIT, to verify before use | Likely acceptable | Needs source review | P0 | Strong candidate for initial thermal workflow. |
| PV Panel Defect Dataset | RGB | Demo-friendly visual defect examples | Multiple visual defect classes | CC BY-NC-SA 4.0, to verify | Research/demo only | Not without license clearance | P1 | Good for visible defects; avoid commercial claim. |
| PV-Multi-Defect | RGB / PV defects | Optional supplemental examples | Surface defect classes | Unknown, verify manually | Only after review | Unknown | P1 | Do not make core until annotations and license are checked. |
| Roboflow Solar Panel Infrared Images | Infrared | Optional detection examples | Hotspot / diode classes | CC BY 4.0, to verify | Likely useful | Needs source review | P1 | Small dataset; useful for demo samples. |
| Thermal PV Panel Detection and Fault Detection Dataset | Thermal / UAV | Optional UAV narrative and panel detection | Detection/fault labels | Verify on source | Only after review | Unknown | P2 | Useful for broader roadmap, not core MVP. |

## Registry Rules

- Do not version large datasets in this repository.
- Keep only small demo samples if licensing allows.
- Store dataset source, license, and download instructions before use.
- Mark non-commercial datasets clearly as demo/research only.
- For a real SaaS, plan for owned data, customer partnerships, or licensed datasets.
