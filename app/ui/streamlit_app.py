from __future__ import annotations

import os
from typing import Any

import requests
import streamlit as st


API_URL = os.getenv("ORVEX_API_URL", "http://127.0.0.1:8000")


def fetch_samples() -> list[dict[str, Any]]:
    response = requests.get(f"{API_URL}/samples", timeout=10)
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
    if sample.get("kind") == "dataset_expected":
        return f"{sample['source_label']} · {sample['name']}"
    return sample["name"]


st.set_page_config(page_title="Orvex", page_icon=" ", layout="wide")

st.markdown(
    """
    <style>
    .main .block-container { padding-top: 2rem; max-width: 1180px; }
    h1 { letter-spacing: 0 !important; }
    .orvex-subtitle { color: #5f6368; font-size: 1.02rem; margin-top: -0.5rem; }
    .metric-row { display: flex; gap: 1rem; flex-wrap: wrap; margin: 1rem 0; }
    .metric-box { border: 1px solid #e3e5e8; border-radius: 8px; padding: 0.9rem 1rem; min-width: 150px; background: #fff; }
    .metric-label { color: #687076; font-size: 0.8rem; text-transform: uppercase; letter-spacing: 0.04em; }
    .metric-value { font-size: 1.45rem; font-weight: 700; color: #111827; margin-top: 0.25rem; }
    .priority-pill { color: white; border-radius: 999px; display: inline-block; font-size: 0.75rem; font-weight: 700; padding: 0.25rem 0.6rem; }
    .finding { border-top: 1px solid #e5e7eb; padding-top: 1rem; margin-top: 1rem; }
    .muted { color: #687076; }
    </style>
    """,
    unsafe_allow_html=True,
)

st.title("Orvex")
st.markdown(
    "<p class='orvex-subtitle'>AI-assisted visual triage for photovoltaic inspection workflows.</p>",
    unsafe_allow_html=True,
)

left, right = st.columns([0.34, 0.66], gap="large")

with left:
    st.subheader("Inspection Input")
    st.caption("Run the Day 1 mock workflow without using the GPU VPS.")

    try:
        samples = fetch_samples()
    except requests.RequestException as exc:
        st.error(f"Could not reach Orvex API at {API_URL}. Start FastAPI before running the UI.")
        st.code(str(exc))
        st.stop()

    sample_by_name = {sample["name"]: sample for sample in samples}
    sample_names = list(sample_by_name)
    sample_name = st.selectbox(
        "Inspection sample",
        sample_names,
        index=sample_names.index("hotspot") if "hotspot" in sample_names else 0,
        format_func=lambda name: sample_display_name(sample_by_name[name]),
    )
    selected_sample = sample_by_name[sample_name]

    if selected_sample.get("kind") == "dataset_expected":
        st.caption(
            f"Dataset: {selected_sample['dataset']} | Source label: {selected_sample['source_label']} | Bucket: {selected_sample['orvex_bucket']}"
        )
        if selected_sample.get("image_available"):
            try:
                sample_image = fetch_sample_image(sample_name)
            except requests.RequestException:
                sample_image = None
            if sample_image is not None:
                st.image(sample_image, caption=sample_name, width="stretch")
        else:
            st.warning("Dataset image is not available locally. The expected JSON can still be analyzed.")

    uploaded_file = st.file_uploader("Optional inspection image", type=["png", "jpg", "jpeg", "webp"])
    if uploaded_file is not None:
        st.image(uploaded_file, caption=uploaded_file.name, width="stretch")

    run_analysis = st.button("Analyze inspection", type="primary", width="stretch")

    st.divider()
    st.caption("Current mode")
    st.code(f"API: {API_URL}\nAI_MODE: mock")

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
