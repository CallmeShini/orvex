export type Priority = "low" | "medium" | "high" | "critical" | "inconclusive";

export type Finding = {
  defect_type: string;
  severity: Priority;
  confidence: number;
  location_hint: string;
  visual_evidence: string;
  recommended_action: string;
};

export type InspectionResult = {
  inspection_id: string;
  image_modality: "rgb" | "thermal" | "infrared" | "unknown";
  contains_solar_panel: boolean;
  inspection_confidence: number;
  overall_risk_score: number;
  priority: Priority;
  findings: Finding[];
  human_review_required: boolean;
  summary: string;
  raw_model_output: string | null;
  schema_version: string;
  prompt_version: string;
  model_name: string;
  model_mode: string;
  latency_ms: number | null;
};

export type AnalyzeResponse = {
  result: InspectionResult;
  report_path: string | null;
  report_markdown: string | null;
};

export type HealthResponse = {
  status: string;
  ai_mode: string;
  schema_version: string;
  prompt_version: string;
};

export type SampleInfo = {
  name: string;
  dataset: string;
  kind: "mock" | "dataset_expected" | string;
  priority: Priority;
  summary: string;
  source_label: string;
  orvex_bucket: string;
  image_available: boolean;
  is_demo: boolean;
  demo_order: number | null;
  demo_stage: string;
  demo_title: string;
  demo_role: string;
  demo_reason: string;
  expected_output_source: string;
  claim_boundary: string;
  needs_human_review_reason: string;
  visual_limitations: string;
  commercial_use_status: string;
  license: string;
};

export const priorityTone: Record<
  Priority,
  {
    label: string;
    text: string;
    bg: string;
    border: string;
  }
> = {
  low: {
    label: "Low",
    text: "text-[#256d3f]",
    bg: "bg-[#e9f4ed]",
    border: "border-[#b7d7c2]"
  },
  medium: {
    label: "Medium",
    text: "text-[#8a6417]",
    bg: "bg-[#f7f0de]",
    border: "border-[#dbc58d]"
  },
  high: {
    label: "High",
    text: "text-[#a44421]",
    bg: "bg-[#f7e8df]",
    border: "border-[#ddb29f]"
  },
  critical: {
    label: "Critical",
    text: "text-[#9f2a25]",
    bg: "bg-[#f5e2df]",
    border: "border-[#dba7a2]"
  },
  inconclusive: {
    label: "Inconclusive",
    text: "text-[#5f665d]",
    bg: "bg-[#edece7]",
    border: "border-[#cdcbc2]"
  }
};

export function formatScore(value: number | null | undefined) {
  if (value === null || value === undefined || Number.isNaN(value)) {
    return "not reported";
  }
  return value.toFixed(2);
}

export function displaySampleName(sample: SampleInfo) {
  if (sample.is_demo && sample.demo_title) {
    return `${sample.demo_order}. ${sample.demo_title}`;
  }
  if (sample.source_label) {
    return `${sample.source_label} | ${sample.name}`;
  }
  return sample.name;
}
