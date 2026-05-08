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

export type VideoFrameAsset = {
  frame_index: number;
  timestamp_ms: number;
  path: string;
  sha256: string | null;
};

export type VideoFrameInspection = {
  frame: VideoFrameAsset;
  result: InspectionResult;
  error: string | null;
};

export type VideoRepresentativeFrame = {
  frame_index: number;
  timestamp_ms: number;
  inspection_id: string;
  priority: Priority;
  overall_risk_score: number;
  summary: string;
};

export type VideoInspectionSummary = {
  schema_version: string;
  frames_analyzed: number;
  frames_with_findings: number;
  frames_with_errors: number;
  frames_requiring_human_review: number;
  priority: Priority;
  max_overall_risk_score: number;
  p95_overall_risk_score: number;
  top_k_mean_overall_risk_score: number;
  mean_overall_risk_score: number;
  mean_inspection_confidence: number;
  defect_type_counts: Record<string, number>;
  model_mode_counts: Record<string, number>;
  latency_ms_total: number | null;
  latency_ms_mean: number | null;
  representative_frame: VideoRepresentativeFrame;
  human_review_required: boolean;
};

export type VideoEvaluationResult = {
  schema_version: string;
  source_video: string | null;
  frame_count: number;
  summary: VideoInspectionSummary;
  run_metadata: Record<string, unknown>;
  frames: VideoFrameInspection[];
};

export type AnalyzeResponse = {
  result: InspectionResult;
  report_path: string | null;
  report_markdown: string | null;
};

export type InspectionJobStatus = "queued" | "processing" | "completed" | "failed" | "unsupported";

export type InspectionAsset = {
  asset_id: string;
  source_type: "sample" | "image" | "video";
  filename: string | null;
  sample_name: string | null;
  media_type: string | null;
  storage_path: string | null;
  size_bytes: number | null;
  sha256: string | null;
  frame_index: number | null;
  timestamp_ms: number | null;
};

export type InspectionJobResponse = {
  job_id: string;
  status: InspectionJobStatus;
  source_type: "sample" | "image" | "video";
  asset: InspectionAsset | null;
  result: InspectionResult | null;
  video_result: VideoEvaluationResult | null;
  report_id: string | null;
  report_markdown: string | null;
  error: string | null;
  created_at: string;
  updated_at: string;
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
