# VLM Contract v1

## Objective

Define a stable contract between Orvex and the multimodal inference layer.

The VLM can provide useful visual reasoning, but every output must be parsed, validated, normalized, and treated as preliminary until reviewed by a human.

## Prompt Base

```txt
You are Orvex, a photovoltaic inspection assistant.

Analyze the provided image as a solar panel inspection asset.

Return ONLY valid JSON. Do not include markdown.

Use cautious language. Do not claim certainty. Do not make legal, warranty, safety, or insurance conclusions. If evidence is unclear, mark the result as inconclusive and require human review.

Focus on:
- visible defects or anomalies;
- suspected defect type;
- severity;
- confidence;
- visual evidence;
- recommended maintenance action;
- whether human review is required.
```

## Schema

```json
{
  "inspection_id": "string",
  "image_modality": "rgb|thermal|infrared|unknown",
  "contains_solar_panel": true,
  "inspection_confidence": 0.0,
  "overall_risk_score": 0.0,
  "priority": "low|medium|high|critical|inconclusive",
  "findings": [
    {
      "defect_type": "hotspot|crack|soiling|broken_cell|shadowing|delamination|burn_mark|discoloration|diode|vegetation|offline_module|unknown",
      "severity": "low|medium|high|critical|inconclusive",
      "confidence": 0.0,
      "location_hint": "short visual location",
      "visual_evidence": "what is visible in the image",
      "recommended_action": "what the maintenance team should review next"
    }
  ],
  "human_review_required": true,
  "summary": "short inspection summary",
  "raw_model_output": "optional raw text"
}
```

## Validation Rules

The backend must reject, correct, or fallback when:

- JSON is invalid;
- required fields are missing;
- confidence is outside `0..1`;
- risk score is outside `0..1`;
- priority is unknown;
- severity is unknown;
- the output uses absolute certainty language;
- the output claims to replace human review;
- a conclusion has no visual evidence.

## Fallback Behavior

If output parsing or validation fails:

1. Attempt one corrective retry when live inference is available.
2. If retry fails, create an `inconclusive` result.
3. Set `human_review_required=true`.
4. Save the raw model output for debugging.
5. Do not block the entire job because one image failed.

## Version Tags

```txt
schema_version: orvex-inspection-result-v1
prompt_version: orvex-solar-vlm-prompt-v1
default_model: Qwen2.5-VL-7B-Instruct
runtime_target: ROCm / MI300X
```

## Allowed Language

Prefer:

- possible;
- suspected;
- appears consistent with;
- visual evidence suggests;
- requires human review.

Avoid:

- guaranteed;
- confirmed;
- definitive;
- certified;
- no review needed.
