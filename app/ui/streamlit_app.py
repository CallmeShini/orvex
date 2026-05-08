from __future__ import annotations

import base64
import os
from typing import Any

import requests
import streamlit as st


API_URL = os.getenv("ORVEX_API_URL", "http://127.0.0.1:8000")


def fetch_samples() -> list[dict[str, Any]]:
    response = requests.get(f"{API_URL}/samples", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_health() -> dict[str, Any]:
    response = requests.get(f"{API_URL}/health", timeout=10)
    response.raise_for_status()
    return response.json()


def fetch_sample_image(sample_name: str) -> bytes | None:
    response = requests.get(f"{API_URL}/samples/{sample_name}/image", timeout=10)
    if response.status_code == 404:
        return None
    response.raise_for_status()
    return response.content


def analyze(sample_name: str, uploaded_file: Any | None) -> dict[str, Any]:
    files = None
    data = {"sample_name": sample_name}

    if uploaded_file is not None:
        files = {"file": (uploaded_file.name, uploaded_file.getvalue(), uploaded_file.type)}

    response = requests.post(f"{API_URL}/analyze", data=data, files=files, timeout=60)
    response.raise_for_status()
    return response.json()


def priority_badge(priority: str) -> str:
    colors = {
        "low": "#256d3f",
        "medium": "#9a6a00",
        "high": "#a34112",
        "critical": "#a51d2d",
        "inconclusive": "#5f6368",
    }
    color = colors.get(priority, "#5f6368")
    return f"<span class='priority-pill' style='background:{color};'>{priority.upper()}</span>"


def sample_display_name(sample: dict[str, Any]) -> str:
    if sample.get("is_demo"):
        return f"{sample['demo_order']}. {sample['demo_title']}"
    if sample.get("kind") == "dataset_expected":
        return f"{sample['source_label']} | {sample['name']}"
    return sample["name"]


def render_thermal_preview(image_bytes: bytes, caption: str) -> None:
    encoded = base64.b64encode(image_bytes).decode("ascii")
    st.markdown(
        f"""
        <figure class="thermal-preview">
          <img src="data:image/jpeg;base64,{encoded}" alt="{caption}" />
          <figcaption>{caption}</figcaption>
        </figure>
        """,
        unsafe_allow_html=True,
    )


def render_demo_path(samples: list[dict[str, Any]], selected_name: str) -> None:
    demo_samples = [sample for sample in samples if sample.get("is_demo")]
    if not demo_samples:
        return

    st.markdown("<div class='demo-path'>", unsafe_allow_html=True)
    for sample in demo_samples:
        selected_class = " selected" if sample["name"] == selected_name else ""
        priority = sample.get("priority", "")
        st.markdown(
            f"""
            <div class="demo-step{selected_class}">
              <div class="demo-step-index">{sample['demo_order']}</div>
              <div>
                <div class="demo-step-title">{sample['demo_title']}</div>
                <div class="demo-step-meta">{sample['demo_stage']} | {priority}</div>
              </div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    st.markdown("</div>", unsafe_allow_html=True)


st.set_page_config(page_title="Orvex", page_icon=" ", layout="wide")

st.markdown(
    """
    <style>
    .stApp { background: #f7f8f6; color: #17201b; }
    .main .block-container { padding-top: 2rem; max-width: 1240px; }
    h1 { letter-spacing: 0 !important; font-weight: 760 !important; }
    h3 { letter-spacing: 0 !important; }
    .orvex-subtitle { color: #5f6b60; font-size: 1.02rem; margin-top: -0.5rem; max-width: 72ch; }
    .metric-row { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
    .metric-box { border: 1px solid #dfe5dd; border-radius: 8px; padding: 0.9rem 1rem; min-width: 150px; background: #ffffff; }
    .metric-label { color: #647067; font-size: 0.78rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .metric-value { font-size: 1.45rem; font-weight: 740; color: #15221b; margin-top: 0.25rem; }
    .priority-pill { color: white; border-radius: 999px; display: inline-block; font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.6rem; }
    .finding { border-top: 1px solid #dfe5dd; padding-top: 1rem; margin-top: 1rem; }
    .muted { color: #647067; }
    .demo-path { display: grid; grid-template-columns: 1fr; gap: 0.45rem; margin: 0.75rem 0 1rem; }
    .demo-step { display: grid; grid-template-columns: 2rem 1fr; gap: 0.65rem; align-items: center; border: 1px solid #dfe5dd; background: rgba(255,255,255,0.74); border-radius: 8px; padding: 0.55rem 0.65rem; }
    .demo-step.selected { border-color: #426b55; background: #f0f5ef; box-shadow: inset 3px 0 0 #426b55; }
    .demo-step-index { width: 1.45rem; height: 1.45rem; border-radius: 50%; background: #17201b; color: #fff; display: grid; place-items: center; font-size: 0.72rem; font-weight: 720; }
    .demo-step-title { color: #17201b; font-weight: 720; line-height: 1.15; }
    .demo-step-meta { color: #647067; font-size: 0.77rem; margin-top: 0.15rem; text-transform: uppercase; letter-spacing: 0.03em; }
    .provenance-row { display: flex; flex-wrap: wrap; gap: 0.4rem; margin: 0.55rem 0 0.85rem; }
    .provenance-chip { border: 1px solid #dfe5dd; background: #fff; border-radius: 999px; color: #354139; padding: 0.22rem 0.55rem; font-size: 0.78rem; }
    .thermal-preview { margin: 0.55rem 0 1rem; border: 1px solid #dfe5dd; background: #111a15; border-radius: 8px; padding: 0.85rem; }
    .thermal-preview img { width: 100%; max-height: 260px; object-fit: contain; image-rendering: pixelated; filter: contrast(1.35) saturate(1.05); }
    .thermal-preview figcaption { color: #cbd8cf; font-size: 0.75rem; margin-top: 0.55rem; overflow-wrap: anywhere; }
    .analysis-boundary { border-left: 3px solid #426b55; padding: 0.65rem 0.85rem; background: #eef4ee; color: #354139; border-radius: 6px; margin: 0.75rem 0; font-size: 0.9rem; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Orvex")
st.markdown(
    "<p class='orvex-subtitle'>AI-assisted visual triage for photovoltaic inspection workflows. This demo uses curated RaptorMaps samples and transparent expected outputs before live GPU inference.</p>",
    unsafe_allow_html=True,
)

left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.subheader("Inspection Input")
    st.caption("Run the official local demo path without using the GPU VPS.")

    try:
        health = fetch_health()
        samples = fetch_samples()
    except requests.RequestException as exc:
        st.error(f"Could not reach Orvex API at {API_URL}. Start FastAPI before running the UI.")
        st.code(str(exc))
        st.stop()

    sample_mode = st.radio(
        "Sample set",
        ["Demo path", "All RaptorMaps", "Mock only"],
        horizontal=True,
    )

    if sample_mode == "Demo path":
        visible_samples = [sample for sample in samples if sample.get("is_demo")]
    elif sample_mode == "All RaptorMaps":
        visible_samples = [sample for sample in samples if sample.get("kind") == "dataset_expected"]
    else:
        visible_samples = [sample for sample in samples if sample.get("kind") == "mock"]

    if not visible_samples:
        st.error("No samples are available for the selected set.")
        st.stop()

    sample_by_name = {sample["name"]: sample for sample in visible_samples}
    sample_names = list(sample_by_name)
    sample_name = st.selectbox(
        "Inspection sample",
        sample_names,
        index=sample_names.index("hotspot") if "hotspot" in sample_names else 0,
        format_func=lambda name: sample_display_name(sample_by_name[name]),
    )
    selected_sample = sample_by_name[sample_name]

    if sample_mode == "Demo path":
        render_demo_path(samples, sample_name)

    if selected_sample.get("kind") == "dataset_expected":
        st.markdown(
            f"""
            <div class="provenance-row">
              <span class="provenance-chip">{selected_sample['dataset']}</span>
              <span class="provenance-chip">Label: {selected_sample['source_label']}</span>
              <span class="provenance-chip">Bucket: {selected_sample['orvex_bucket']}</span>
              <span class="provenance-chip">License: {selected_sample.get('license') or 'tracked'}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )
        if selected_sample.get("demo_reason"):
            st.markdown(
                f"<div class='analysis-boundary'>{selected_sample['demo_reason']}</div>",
                unsafe_allow_html=True,
            )
        if selected_sample.get("image_available"):
            try:
                sample_image = fetch_sample_image(sample_name)
            except requests.RequestException:
                sample_image = None
            if sample_image is not None:
                render_thermal_preview(sample_image, sample_name)
                if selected_sample.get("visual_limitations"):
                    st.caption(selected_sample["visual_limitations"])
        else:
            st.warning("Dataset image is not available locally. The expected JSON can still be analyzed.")
    elif selected_sample.get("demo_reason"):
        st.markdown(
            f"<div class='analysis-boundary'>{selected_sample['demo_reason']}</div>",
            unsafe_allow_html=True,
        )

    with st.expander("Trace", expanded=False):
        trace_rows = {
            "Sample": sample_name,
            "Dataset": selected_sample.get("dataset") or "mock",
            "Source label": selected_sample.get("source_label") or "not applicable",
            "Bucket": selected_sample.get("orvex_bucket") or "not applicable",
            "License": selected_sample.get("license") or "not applicable",
            "Output source": selected_sample.get("expected_output_source") or "mock",
            "Claim boundary": selected_sample.get("claim_boundary") or "AI-assisted triage only",
            "Human review": selected_sample.get("needs_human_review_reason") or "Required for all current demo outputs.",
        }
        for label, value in trace_rows.items():
            st.write(f"**{label}:** {value}")

    uploaded_file = st.file_uploader("Optional inspection image", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption=uploaded_file.name, width="stretch")

    run_analysis = st.button("Analyze inspection", type="primary", width="stretch")

    st.divider()
    st.caption("Current mode")
    st.code(
        "\n".join(
            [
                f"API: {API_URL}",
                f"AI_MODE: {health['ai_mode']}",
                f"Schema: {health['schema_version']}",
                f"Prompt: {health['prompt_version']}",
                f"Selected: {sample_name}",
            ]
        )
    )

with right:
    st.subheader("Triage Result")

    if not run_analysis:
        st.info("Select a demo scenario or upload an image, then run analysis.")
        st.stop()

    with st.spinner("Analyzing inspection asset..."):
        try:
            payload = analyze(sample_name, uploaded_file)
        except requests.RequestException as exc:
            st.error("Analysis request failed.")
            st.code(str(exc))
            st.stop()

    result = payload["result"]
    priority = result["priority"]

    st.markdown(priority_badge(priority), unsafe_allow_html=True)
    st.write(result["summary"])

    st.markdown(
        f"""
        <div class='metric-row'>
          <div class='metric-box'><div class='metric-label'>Risk Score</div><div class='metric-value'>{result["overall_risk_score"]:.2f}</div></div>
          <div class='metric-box'><div class='metric-label'>Confidence</div><div class='metric-value'>{result["inspection_confidence"]:.2f}</div></div>
          <div class='metric-box'><div class='metric-label'>Human Review</div><div class='metric-value'>{str(result["human_review_required"])}</div></div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        f"""
        <div class="provenance-row">
          <span class="provenance-chip">Model mode: {result["model_mode"]}</span>
          <span class="provenance-chip">Prompt: {result["prompt_version"]}</span>
          <span class="provenance-chip">Schema: {result["schema_version"]}</span>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("### Findings")
    findings = result.get("findings", [])
    if not findings:
        st.write("No clear anomaly was identified. Human review may still be required depending on inspection context.")
    else:
        for finding in findings:
            st.markdown("<div class='finding'>", unsafe_allow_html=True)
            st.markdown(f"**{finding['defect_type'].replace('_', ' ').title()}**")
            st.write(f"Severity: `{finding['severity']}` | Confidence: `{finding['confidence']:.2f}`")
            st.write(f"Location: {finding['location_hint']}")
            st.write(f"Evidence: {finding['visual_evidence']}")
            st.write(f"Recommended action: {finding['recommended_action']}")
            st.markdown("</div>", unsafe_allow_html=True)

    report_markdown = payload.get("report_markdown") or ""
    with st.expander("Report preview", expanded=True):
        st.markdown(report_markdown)

    st.download_button(
        "Download report",
        data=report_markdown,
        file_name=f"{result['inspection_id']}.md",
        mime="text/markdown",
        width="stretch",
    )

    with st.expander("Raw JSON"):
        st.json(result)
