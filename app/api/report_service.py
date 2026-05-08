from __future__ import annotations

from pathlib import Path

from app.api.schemas import InspectionResult


PROJECT_ROOT = Path(__file__).resolve().parents[2]
REPORTS_DIR = PROJECT_ROOT / "data" / "reports"


def render_markdown_report(result: InspectionResult) -> str:
    lines = [
        f"# Orvex Inspection Report - {result.inspection_id}",
        "",
        "## Summary",
        "",
        result.summary,
        "",
        "## Risk",
        "",
        f"- Priority: `{result.priority.value}`",
        f"- Overall risk score: `{result.overall_risk_score:.2f}`",
        f"- Inspection confidence: `{result.inspection_confidence:.2f}`",
        f"- Human review required: `{result.human_review_required}`",
        "",
        "## Findings",
        "",
    ]

    if result.findings:
        for index, finding in enumerate(result.findings, start=1):
            lines.extend(
                [
                    f"### Finding {index}: {finding.defect_type.value}",
                    "",
                    f"- Severity: `{finding.severity.value}`",
                    f"- Confidence: `{finding.confidence:.2f}`",
                    f"- Location hint: {finding.location_hint}",
                    f"- Visual evidence: {finding.visual_evidence}",
                    f"- Recommended action: {finding.recommended_action}",
                    "",
                ]
            )
    else:
        lines.extend(["No clear findings were produced by the inspection workflow.", ""])

    lines.extend(
        [
            "## Model Metadata",
            "",
            f"- Model mode: `{result.model_mode}`",
            f"- Model name: `{result.model_name}`",
            f"- Prompt version: `{result.prompt_version}`",
            f"- Schema version: `{result.schema_version}`",
            "",
            "## Review Boundary",
            "",
            "This report is a preliminary AI-assisted triage output. It does not replace technical inspection, warranty review, safety analysis, or legal certification.",
        ]
    )
    return "\n".join(lines).strip() + "\n"


def write_report(result: InspectionResult) -> tuple[Path, str]:
    REPORTS_DIR.mkdir(parents=True, exist_ok=True)
    markdown = render_markdown_report(result)
    path = REPORTS_DIR / f"{result.inspection_id}.md"
    path.write_text(markdown, encoding="utf-8")
    return path, markdown


def read_report(inspection_id: str) -> str:
    path = REPORTS_DIR / f"{inspection_id}.md"
    if not path.exists():
        raise FileNotFoundError(f"Report not found: {inspection_id}")
    return path.read_text(encoding="utf-8")

