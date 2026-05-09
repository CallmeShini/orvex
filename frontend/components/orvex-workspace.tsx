"use client";

import {
  ArrowClockwise,
  CheckCircle,
  CircleNotch,
  ClipboardText,
  Cpu,
  FileArrowDown,
  FileText,
  Gauge,
  HourglassMedium,
  ImageSquare,
  Pulse,
  ShieldCheck,
  Stack,
  UploadSimple,
  VideoCamera,
  WarningOctagon,
  XCircle
} from "@phosphor-icons/react";
import { AnimatePresence, motion } from "framer-motion";
import { ChangeEvent, DragEvent, useEffect, useMemo, useState } from "react";
import {
  AnalyzeResponse,
  HealthResponse,
  InspectionJobStatus,
  InspectionJobResponse,
  InspectionResult,
  SampleInfo,
  displaySampleName,
  formatScore,
  priorityTone
} from "@/lib/orvex";

const navItems = ["Overview", "Inspections", "Assets", "Reports", "Datasets", "Audit"];
const allowedImageTypes = ["image/jpeg", "image/png", "image/webp", "image/tiff"];
type ApiState = "idle" | "loading" | "error";
type WorkspaceJobState = InspectionJobStatus | ApiState;

async function fetchJson<T>(url: string, init?: RequestInit): Promise<T> {
  const response = await fetch(url, {
    ...init,
    cache: "no-store"
  });

  if (!response.ok) {
    const text = await response.text();
    throw new Error(text || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function OrvexWorkspace() {
  const [health, setHealth] = useState<HealthResponse | null>(null);
  const [samples, setSamples] = useState<SampleInfo[]>([]);
  const [selectedName, setSelectedName] = useState<string>("");
  const [selectedImageUrl, setSelectedImageUrl] = useState<string | null>(null);
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [uploadedPreviewUrl, setUploadedPreviewUrl] = useState<string | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResponse | null>(null);
  const [inspectionJob, setInspectionJob] = useState<InspectionJobResponse | null>(null);
  const [loadingData, setLoadingData] = useState(true);
  const [analyzing, setAnalyzing] = useState(false);
  const [jobState, setJobState] = useState<WorkspaceJobState>("loading");
  const [dragging, setDragging] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const selectedSample = useMemo(
    () => samples.find((sample) => sample.name === selectedName) ?? null,
    [samples, selectedName]
  );
  const demoSamples = useMemo(() => samples.filter((sample) => sample.is_demo), [samples]);
  const quickSamples = useMemo(() => {
    const normal =
      samples.find((sample) => sample.name === "raptormaps-no_anomaly-10000") ??
      samples.find((sample) => sample.priority === "low");
    const anomalous =
      samples.find((sample) => sample.name === "raptormaps-hot_spot-06722") ??
      samples.find((sample) => ["high", "critical", "medium"].includes(sample.priority));
    return [
      normal ? { role: "normal" as const, sample: normal } : null,
      anomalous ? { role: "anomalous" as const, sample: anomalous } : null
    ].filter(Boolean) as { role: "normal" | "anomalous"; sample: SampleInfo }[];
  }, [samples]);
  const visualUrl = uploadedPreviewUrl ?? selectedImageUrl;
  const thermalizeVisual = Boolean(
    !uploadedPreviewUrl && selectedSample?.dataset === "RaptorMaps InfraredSolarModules"
  );
  const result = analysis?.result ?? null;

  useEffect(() => {
    let cancelled = false;

    async function loadWorkspace() {
      setLoadingData(true);
      setError(null);
      try {
        const [healthResponse, sampleResponse] = await Promise.all([
          fetchJson<HealthResponse>("/api/orvex/health"),
          fetchJson<SampleInfo[]>("/api/orvex/samples")
        ]);
        if (cancelled) {
          return;
        }

        setHealth(healthResponse);
        setSamples(sampleResponse);
        const preferredDemo =
          sampleResponse.find((sample) => sample.name === "raptormaps-hot_spot-06722") ??
          sampleResponse.find((sample) => sample.is_demo);
        setSelectedName(preferredDemo?.name ?? sampleResponse[0]?.name ?? "");
        setJobState("idle");
      } catch (loadError) {
        setError(loadError instanceof Error ? loadError.message : "Could not load Orvex API.");
        setJobState("error");
      } finally {
        if (!cancelled) {
          setLoadingData(false);
        }
      }
    }

    loadWorkspace();
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    if (!selectedSample?.image_available || uploadedFile) {
      setSelectedImageUrl(null);
      return;
    }

    let objectUrl: string | null = null;
    let cancelled = false;
    const sampleName = selectedSample.name;

    async function loadSampleImage() {
      try {
        const response = await fetch(`/api/orvex/samples/${sampleName}/image`, {
          cache: "no-store"
        });
        if (!response.ok) {
          setSelectedImageUrl(null);
          return;
        }
        const blob = await response.blob();
        objectUrl = URL.createObjectURL(blob);
        if (!cancelled) {
          setSelectedImageUrl(objectUrl);
        }
      } catch {
        if (!cancelled) {
          setSelectedImageUrl(null);
        }
      }
    }

    loadSampleImage();
    return () => {
      cancelled = true;
      if (objectUrl) {
        URL.revokeObjectURL(objectUrl);
      }
    };
  }, [selectedSample, uploadedFile]);

  useEffect(() => {
    if (!uploadedFile) {
      setUploadedPreviewUrl(null);
      return;
    }

    const objectUrl = URL.createObjectURL(uploadedFile);
    setUploadedPreviewUrl(objectUrl);
    return () => URL.revokeObjectURL(objectUrl);
  }, [uploadedFile]);

  function selectFile(file: File | null) {
    if (!file) {
      return;
    }

    if (file.type.startsWith("video/")) {
      setError("Video upload needs the planned frame-extraction job pipeline. This build enables image analysis only.");
      return;
    }

    if (!allowedImageTypes.includes(file.type)) {
      setError("Unsupported image type. Use JPEG, PNG, WebP, or TIFF.");
      return;
    }

    setUploadedFile(file);
    setAnalysis(null);
    setInspectionJob(null);
    setJobState("idle");
    setError(null);
  }

  function handleFileInput(event: ChangeEvent<HTMLInputElement>) {
    selectFile(event.target.files?.[0] ?? null);
    event.target.value = "";
  }

  function handleDrop(event: DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragging(false);
    selectFile(event.dataTransfer.files?.[0] ?? null);
  }

  async function runAnalysis() {
    setAnalyzing(true);
    setJobState("queued");
    setError(null);

    const body = new FormData();
    if (uploadedFile) {
      body.append("file", uploadedFile);
    } else if (selectedName) {
      body.append("sample_name", selectedName);
    }

    try {
      window.setTimeout(() => {
        setJobState((current) => (current === "queued" ? "processing" : current));
      }, 250);
      const job = await fetchJson<InspectionJobResponse>("/api/orvex/inspection-jobs", {
        method: "POST",
        body
      });
      setInspectionJob(job);
      setJobState(job.status);
      if (job.result) {
        setAnalysis({
          result: job.result,
          report_path: null,
          report_markdown: job.report_markdown
        });
      } else {
        setAnalysis(null);
      }
      if (job.error) {
        setError(job.error);
        setJobState("failed");
      }
    } catch (analysisError) {
      setError(analysisError instanceof Error ? analysisError.message : "Analysis failed.");
      setJobState("error");
    } finally {
      setAnalyzing(false);
    }
  }

  function clearUpload() {
    setUploadedFile(null);
    setUploadedPreviewUrl(null);
    setAnalysis(null);
    setInspectionJob(null);
    setJobState("idle");
    setError(null);
  }

  return (
    <main className="min-h-[100dvh] w-full max-w-full overflow-x-hidden bg-[#f3f2ee] text-[#171a16]">
      <div className="grid min-h-[100dvh] grid-cols-1 lg:grid-cols-[248px_minmax(0,1fr)]">
        <Rail health={health} />
        <section className="min-w-0">
          <TopBar health={health} loading={loadingData} />

          <div className="grid gap-4 px-4 pb-6 pt-4 md:px-6 xl:grid-cols-[320px_minmax(0,1fr)_350px]">
            <InputPanel
              analyzing={analyzing}
              demoSamples={demoSamples}
              dragging={dragging}
              error={error}
              loadingData={loadingData}
              onAnalyze={runAnalysis}
              onClearUpload={clearUpload}
              onDragLeave={() => setDragging(false)}
              onDragOver={(event) => {
                event.preventDefault();
                setDragging(true);
              }}
              onDrop={handleDrop}
              onFileInput={handleFileInput}
              quickSamples={quickSamples}
              samples={samples}
              selectedName={selectedName}
              selectedSample={selectedSample}
              setSelectedName={(name) => {
                setSelectedName(name);
                setUploadedFile(null);
                setAnalysis(null);
                setInspectionJob(null);
                setJobState("idle");
                setError(null);
              }}
              uploadedFile={uploadedFile}
            />

            <InspectionCanvas
              analyzing={analyzing}
              result={result}
              selectedSample={selectedSample}
              thermalizeVisual={thermalizeVisual}
              visualUrl={visualUrl}
            />

            <ResultInspector
              analysis={analysis}
              health={health}
              inspectionJob={inspectionJob}
              jobState={jobState}
              loading={analyzing}
              selectedSample={selectedSample}
            />
          </div>
        </section>
      </div>
    </main>
  );
}

function Rail({ health }: { health: HealthResponse | null }) {
  return (
    <aside className="hidden min-h-[100dvh] border-r border-white/10 bg-[#111612] text-white lg:flex lg:flex-col">
      <div className="px-5 py-6">
        <div className="text-2xl font-semibold tracking-tight">Orvex</div>
        <div className="mt-8 text-[11px] uppercase tracking-[0.16em] text-white/42">Workspace</div>
        <button
          className="mt-3 flex w-full items-center justify-between rounded-[7px] border border-white/14 bg-white/[0.04] px-3 py-2 text-left text-sm text-white"
          type="button"
        >
          Brightpeak Solar Farm
          <span className="text-white/45">A12</span>
        </button>
      </div>

      <nav className="space-y-1 px-3">
        {navItems.map((item) => {
          const active = item === "Inspections";
          return (
            <button
              className={`flex w-full items-center gap-3 rounded-[7px] px-3 py-2.5 text-sm transition ${
                active ? "bg-white/[0.10] text-white" : "text-white/64 hover:bg-white/[0.06] hover:text-white"
              }`}
              key={item}
              type="button"
            >
              <span className={`h-1.5 w-1.5 rounded-full ${active ? "bg-[#56b87a]" : "bg-white/28"}`} />
              {item}
            </button>
          );
        })}
      </nav>

      <div className="mt-auto border-t border-white/10 p-5">
        <div className="flex items-center gap-3">
          <div className="grid h-9 w-9 place-items-center rounded-full bg-[#3aa366] text-sm font-semibold text-white">AC</div>
          <div>
            <div className="text-sm font-medium">Ava Chen</div>
            <div className="text-xs text-white/45">Solar operations</div>
          </div>
        </div>
        <div className="mt-5 rounded-[7px] border border-white/10 bg-white/[0.04] p-3">
          <div className="flex items-center gap-2 text-xs text-white/54">
            <Pulse size={15} weight="duotone" />
            API mode
          </div>
          <div className="mt-1 font-mono text-sm text-white">{health?.ai_mode ?? "loading"}</div>
        </div>
      </div>
    </aside>
  );
}

function TopBar({ health, loading }: { health: HealthResponse | null; loading: boolean }) {
  return (
    <header className="border-b border-[#deddd6] bg-[#fbfaf6]/88 px-4 py-4 backdrop-blur md:px-6">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-center xl:justify-between">
        <div>
          <div className="flex flex-wrap items-center gap-2 text-sm text-[#687066]">
            <span>Inspections</span>
            <span>/</span>
            <span className="text-[#171a16]">PV thermal review</span>
            <span className="rounded-full border border-[#bdddc8] bg-[#e8f5ed] px-2 py-0.5 text-xs font-medium text-[#256d3f]">
              {loading ? "Connecting" : health?.status === "ok" ? "API online" : "Unknown"}
            </span>
          </div>
          <h1 className="mt-2 max-w-5xl text-2xl font-semibold tracking-tight md:text-3xl">
            Solar fault triage workspace
          </h1>
        </div>

        <div className="grid grid-cols-2 gap-2 text-xs text-[#687066] md:flex md:items-center">
          <Meta label="Asset" value="Array 12A" />
          <Meta label="Runtime" value={health?.ai_mode ?? "pending"} />
          <Meta label="Schema" value={health?.schema_version ?? "pending"} />
          <button
            className="inline-flex cursor-default items-center justify-center gap-2 rounded-[7px] border border-[#cfcfc7] bg-white px-3 py-2 text-sm font-medium text-[#4b544a]"
            disabled
            type="button"
          >
            <FileArrowDown size={17} weight="duotone" />
            Report available after analysis
          </button>
        </div>
      </div>
    </header>
  );
}

function Meta({ label, value }: { label: string; value: string }) {
  return (
    <div className="min-w-[118px]">
      <div className="text-[11px] uppercase tracking-[0.12em] text-[#82887f]">{label}</div>
      <div className="mt-1 truncate font-mono text-xs text-[#171a16]">{value}</div>
    </div>
  );
}

type InputPanelProps = {
  analyzing: boolean;
  demoSamples: SampleInfo[];
  dragging: boolean;
  error: string | null;
  loadingData: boolean;
  onAnalyze: () => void;
  onClearUpload: () => void;
  onDragLeave: () => void;
  onDragOver: (event: DragEvent<HTMLLabelElement>) => void;
  onDrop: (event: DragEvent<HTMLLabelElement>) => void;
  onFileInput: (event: ChangeEvent<HTMLInputElement>) => void;
  quickSamples: { role: "normal" | "anomalous"; sample: SampleInfo }[];
  samples: SampleInfo[];
  selectedName: string;
  selectedSample: SampleInfo | null;
  setSelectedName: (name: string) => void;
  uploadedFile: File | null;
};

function InputPanel(props: InputPanelProps) {
  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      className="min-w-0 border border-[#deddd6] bg-[#fbfaf6] p-4 shadow-[0_20px_50px_-38px_rgba(17,22,18,0.45)]"
      initial={{ opacity: 0, y: 12 }}
      transition={{ duration: 0.38 }}
    >
      <div className="flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Inspection input</h2>
          <p className="mt-1 text-sm leading-5 text-[#687066]">Use a curated sample or upload one panel image.</p>
        </div>
        <button
          className="rounded-[6px] border border-[#d8d6cd] bg-white p-2 text-[#4b544a] transition hover:border-[#171a16] active:translate-y-[1px]"
          onClick={() => window.location.reload()}
          title="Reload workspace"
          type="button"
        >
          <ArrowClockwise size={17} />
        </button>
      </div>

      <div className="mt-5 grid grid-cols-2 gap-2">
        <button className="rounded-[7px] bg-[#171a16] px-3 py-2 text-sm font-medium text-white" type="button">
          Analyze one image
        </button>
        <button
          className="inline-flex cursor-not-allowed items-center justify-center gap-2 rounded-[7px] border border-[#d9d8d1] bg-[#f0efea] px-3 py-2 text-sm font-medium text-[#858a81]"
          title="Video analysis needs the planned job pipeline with frame extraction."
          type="button"
        >
          <VideoCamera size={16} />
          Video upload unavailable
        </button>
      </div>

      <div className="mt-4 grid gap-2">
        <div className="text-xs font-semibold uppercase tracking-[0.12em] text-[#82887f]">Ready samples</div>
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-2 xl:grid-cols-1">
          {props.quickSamples.map(({ role, sample }) => (
            <button
              className={`rounded-[8px] border p-3 text-left transition active:translate-y-[1px] ${
                sample.name === props.selectedName && !props.uploadedFile
                  ? "border-[#2f8f5b] bg-[#edf7f1]"
                  : "border-[#deddd6] bg-white hover:border-[#a9aaa1]"
              }`}
              key={`${role}-${sample.name}`}
              onClick={() => props.setSelectedName(sample.name)}
              type="button"
            >
              <div className="text-sm font-semibold text-[#171a16]">
                {role === "normal" ? "Use normal panel sample" : "Use anomalous panel sample"}
              </div>
              <div className="mt-1 truncate text-xs text-[#687066]">{displaySampleName(sample)}</div>
            </button>
          ))}
        </div>
      </div>

      <label
        className={`mt-4 flex min-h-44 flex-col items-center justify-center border border-dashed p-5 text-center transition ${
          props.dragging ? "border-[#2f8f5b] bg-[#ecf6ef]" : "border-[#cfcfc7] bg-white"
        }`}
        onDragLeave={props.onDragLeave}
        onDragOver={props.onDragOver}
        onDrop={props.onDrop}
      >
        <input accept="image/jpeg,image/png,image/webp,image/tiff" className="hidden" onChange={props.onFileInput} type="file" />
        <UploadSimple className="text-[#2f8f5b]" size={30} weight="duotone" />
        <span className="mt-3 text-sm font-medium text-[#171a16]">
          {props.uploadedFile ? props.uploadedFile.name : "Upload solar panel image"}
        </span>
        <span className="mt-1 text-xs text-[#687066]">Click to choose a JPEG, PNG, WebP, or TIFF, or drop the file here.</span>
      </label>

      {props.uploadedFile ? (
        <button
          className="mt-3 w-full rounded-[7px] border border-[#d8d6cd] bg-white px-3 py-2 text-sm font-medium text-[#171a16] transition hover:border-[#171a16] active:translate-y-[1px]"
          onClick={props.onClearUpload}
          type="button"
        >
          Clear upload and use curated samples
        </button>
      ) : null}

      <div className="mt-5">
        <div className="flex items-center justify-between">
          <h3 className="text-sm font-semibold">Demo path</h3>
          <span className="font-mono text-xs text-[#687066]">{props.demoSamples.length || props.samples.length} samples</span>
        </div>
        <div className="no-scrollbar mt-3 max-h-[330px] space-y-2 overflow-auto pr-1">
          {props.loadingData
            ? Array.from({ length: 4 }).map((_, index) => (
                <div className="h-17 animate-pulse rounded-[8px] bg-[#ebe9e1]" key={index} />
              ))
            : (props.demoSamples.length ? props.demoSamples : props.samples).map((sample) => (
                <button
                  className={`w-full rounded-[8px] border p-3 text-left transition active:translate-y-[1px] ${
                    sample.name === props.selectedName
                      ? "border-[#2f8f5b] bg-[#edf7f1]"
                      : "border-[#deddd6] bg-white hover:border-[#a9aaa1]"
                  }`}
                  key={sample.name}
                  onClick={() => props.setSelectedName(sample.name)}
                  type="button"
                >
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="truncate text-sm font-medium text-[#171a16]">{displaySampleName(sample)}</div>
                      <div className="mt-1 truncate text-xs text-[#687066]">{sample.source_label || sample.dataset || "mock sample"}</div>
                    </div>
                    <span className={`rounded-full px-2 py-0.5 text-[11px] font-medium ${priorityTone[sample.priority].bg} ${priorityTone[sample.priority].text}`}>
                      {priorityTone[sample.priority].label}
                    </span>
                  </div>
                </button>
              ))}
        </div>
      </div>

      <AnimatePresence>
        {props.error ? (
          <motion.div
            animate={{ opacity: 1, y: 0 }}
            className="mt-4 border border-[#ddb29f] bg-[#f8ebe4] p-3 text-sm leading-5 text-[#8c3920]"
            exit={{ opacity: 0, y: -6 }}
            initial={{ opacity: 0, y: -6 }}
          >
            {props.error}
          </motion.div>
        ) : null}
      </AnimatePresence>

      <button
        className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-[7px] bg-[#1d6f43] px-4 py-3 text-sm font-semibold text-white transition hover:bg-[#185f39] active:translate-y-[1px] disabled:cursor-not-allowed disabled:bg-[#98aa9e]"
        disabled={props.analyzing || props.loadingData || (!props.selectedSample && !props.uploadedFile)}
        onClick={props.onAnalyze}
        type="button"
      >
        {props.analyzing ? <Pulse className="animate-pulse" size={18} weight="duotone" /> : <Gauge size={18} weight="duotone" />}
        {props.analyzing ? "Running image analysis" : "Run analysis for selected image"}
      </button>
    </motion.section>
  );
}

function InspectionCanvas({
  analyzing,
  result,
  selectedSample,
  thermalizeVisual,
  visualUrl
}: {
  analyzing: boolean;
  result: InspectionResult | null;
  selectedSample: SampleInfo | null;
  thermalizeVisual: boolean;
  visualUrl: string | null;
}) {
  return (
    <motion.section
      animate={{ opacity: 1, y: 0 }}
      className="min-w-0 border border-[#deddd6] bg-[#fbfaf6] p-4"
      initial={{ opacity: 0, y: 12 }}
      transition={{ delay: 0.06, duration: 0.38 }}
    >
      <div className="flex flex-col gap-3 md:flex-row md:items-center md:justify-between">
        <div>
          <h2 className="text-base font-semibold tracking-tight">Inspection canvas</h2>
          <p className="mt-1 text-sm text-[#687066]">
            {selectedSample?.visual_limitations || "Preview the selected asset and route the result to review."}
          </p>
        </div>
        <div className="flex items-center gap-2">
          {["Select", "Mark", "Compare"].map((tool) => (
            <button
              className="rounded-[6px] border border-[#d8d6cd] bg-white px-3 py-2 text-xs font-medium text-[#4b544a] transition hover:border-[#171a16] active:translate-y-[1px]"
              key={tool}
              type="button"
            >
              {tool}
            </button>
          ))}
        </div>
      </div>

      <div className="relative mt-4 aspect-[16/10] overflow-hidden border border-[#191f1a] bg-[#171a16]">
        {visualUrl ? (
          <div className="relative h-full w-full bg-[#151a15]">
            <img
              alt="Selected photovoltaic inspection input"
              className={`h-full w-full [image-rendering:pixelated] ${
                thermalizeVisual ? "object-cover opacity-80 grayscale contrast-[1.75]" : "object-contain"
              }`}
              src={visualUrl}
            />
            {thermalizeVisual ? (
              <div className="pointer-events-none absolute inset-0 bg-[radial-gradient(circle_at_48%_50%,rgba(255,231,105,0.96)_0_4%,rgba(226,74,42,0.88)_9%,transparent_22%),linear-gradient(135deg,#1d1748,#6f1a6f_42%,#d84546_72%,#f0b44b)] opacity-75 mix-blend-color" />
            ) : null}
          </div>
        ) : (
          <div className="thermal-grid h-full w-full" />
        )}

        <div className="pointer-events-none absolute inset-0 bg-[linear-gradient(90deg,rgba(255,255,255,0.05)_1px,transparent_1px),linear-gradient(rgba(255,255,255,0.05)_1px,transparent_1px)] bg-[size:96px_72px]" />

        {analyzing ? <div className="scanline pointer-events-none absolute inset-y-0 w-1/2" /> : null}

        {result?.findings.length ? (
          <motion.div
            animate={{ opacity: 1, scale: 1 }}
            className="absolute left-[43%] top-[40%] h-[24%] w-[25%] border border-white/90 bg-white/5 shadow-[0_0_0_999px_rgba(0,0,0,0.08)]"
            initial={{ opacity: 0, scale: 0.94 }}
            transition={{ type: "spring", stiffness: 130, damping: 18 }}
          >
            <span className="absolute -left-px -top-7 bg-white px-2 py-1 font-mono text-xs text-[#171a16]">A1</span>
            <span className="absolute left-1/2 top-1/2 h-10 w-10 -translate-x-1/2 -translate-y-1/2 rounded-full border border-white/90" />
          </motion.div>
        ) : null}

        <div className="absolute bottom-4 left-4 flex items-center gap-2 rounded-[7px] bg-white/92 px-3 py-2 text-xs font-medium text-[#171a16] backdrop-blur">
          <ImageSquare size={16} weight="duotone" />
          {selectedSample?.source_label || result?.image_modality || "thermal preview"}
        </div>
        <div className="absolute bottom-4 right-4 rounded-[7px] bg-[#111612]/80 px-3 py-2 font-mono text-xs text-white/82">
          {result?.latency_ms !== null && result?.latency_ms !== undefined ? `${result.latency_ms} ms` : "analysis pending"}
        </div>
      </div>

      <div className="mt-4 grid gap-3 md:grid-cols-4">
        {["IR module crop", "RGB alignment", "Classifier signal", "VLM report"].map((label, index) => (
          <div className="border border-[#deddd6] bg-white p-3" key={label}>
            <div className={`h-14 ${index === 0 ? "thermal-grid" : "bg-[#d8d8d0]"}`} />
            <div className="mt-2 text-xs font-medium text-[#171a16]">{label}</div>
          </div>
        ))}
      </div>
    </motion.section>
  );
}

function ResultInspector({
  analysis,
  health,
  inspectionJob,
  jobState,
  loading,
  selectedSample
}: {
  analysis: AnalyzeResponse | null;
  health: HealthResponse | null;
  inspectionJob: InspectionJobResponse | null;
  jobState: WorkspaceJobState;
  loading: boolean;
  selectedSample: SampleInfo | null;
}) {
  const result = analysis?.result ?? null;
  const priority = result?.priority ?? selectedSample?.priority ?? "inconclusive";
  const tone = priorityTone[priority];
  const primaryFinding = result?.findings[0] ?? null;

  function downloadReportJson() {
    if (!analysis || !inspectionJob) {
      return;
    }
    const payload = {
      job_id: inspectionJob.job_id,
      status: inspectionJob.status,
      source_type: inspectionJob.source_type,
      asset: inspectionJob.asset,
      result: analysis.result,
      report_markdown: analysis.report_markdown
    };
    const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement("a");
    anchor.href = url;
    anchor.download = `${inspectionJob.job_id}-orvex-report.json`;
    anchor.click();
    URL.revokeObjectURL(url);
  }

  return (
    <motion.aside
      animate={{ opacity: 1, y: 0 }}
      className="min-w-0 border border-[#deddd6] bg-[#fbfaf6]"
      initial={{ opacity: 0, y: 12 }}
      transition={{ delay: 0.12, duration: 0.38 }}
    >
      <div className="border-b border-[#deddd6] p-4">
        <div className="flex items-start justify-between gap-3">
          <div>
            <h2 className="text-base font-semibold tracking-tight">Inspection result</h2>
            <p className="mt-1 text-sm text-[#687066]">Provisional triage for human review.</p>
          </div>
          <span className={`rounded-full border px-2 py-1 text-xs font-medium ${tone.border} ${tone.bg} ${tone.text}`}>
            {tone.label}
          </span>
        </div>
      </div>

      <JobStateBanner state={jobState} />

      <div className="grid grid-cols-2 border-b border-[#deddd6]">
        <Metric label="Priority" value={tone.label} />
        <Metric label="Risk level" value={formatScore(result?.overall_risk_score)} suffix={result ? "estimated" : undefined} />
      </div>

      <div className="border-b border-[#deddd6] p-4">
        <h3 className="text-sm font-semibold">Main findings</h3>
        {loading ? (
          <div className="mt-3 space-y-2">
            <div className="h-3 animate-pulse rounded-full bg-[#deddd6]" />
            <div className="h-3 w-4/5 animate-pulse rounded-full bg-[#e7e5dd]" />
            <div className="h-3 w-3/5 animate-pulse rounded-full bg-[#e7e5dd]" />
          </div>
        ) : result?.findings.length ? (
          <ul className="mt-3 space-y-2 text-sm leading-5 text-[#4d554b]">
            {result.findings.slice(0, 3).map((finding) => (
              <li className="flex gap-2" key={`${finding.defect_type}-${finding.location_hint}`}>
                <WarningOctagon className="mt-0.5 shrink-0 text-[#a44421]" size={16} weight="duotone" />
                <span>{finding.defect_type.replaceAll("_", " ")} near {finding.location_hint || "the selected panel area"}.</span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="mt-2 text-sm leading-6 text-[#4d554b]">
            {result
              ? "Nenhuma anomalia detectada - inspecao concluida sem achados."
              : selectedSample?.summary ?? "Run an inspection to create a validated result."}
          </p>
        )}
      </div>

      <div className="border-b border-[#deddd6] p-4">
        <h3 className="text-sm font-semibold">Evidence</h3>
        <p className="mt-2 text-sm leading-5 text-[#687066]">
          {primaryFinding?.visual_evidence ??
            (result
              ? "A imagem analisada nao retornou achados de anomalia no contrato da API."
              : selectedSample?.source_label ?? "Evidence will reference the selected image after analysis.")}
        </p>
      </div>

      <div className="border-b border-[#deddd6] p-4">
        <h3 className="text-sm font-semibold">Recommended action</h3>
        <p className="mt-2 text-sm leading-5 text-[#4d554b]">
          {primaryFinding?.recommended_action ??
            (result
              ? "Manter em revisao humana de rotina e confirmar contra a imagem fonte."
              : "Run analysis before assigning a maintenance action.")}
        </p>
      </div>

      <div className={`border-b p-4 ${result?.human_review_required ?? true ? "border-[#ddb29f] bg-[#fff6ef]" : "border-[#deddd6]"}`}>
        <div className="flex items-center justify-between gap-3">
          <div>
            <div className="text-xs uppercase tracking-[0.12em] text-[#82887f]">human_review_required</div>
            <div className="mt-1 text-sm font-semibold text-[#171a16]">
              {result?.human_review_required ?? true ? "true - human review required" : "false - not flagged"}
            </div>
          </div>
          {(result?.human_review_required ?? true) ? (
            <WarningOctagon className="text-[#a44421]" size={26} weight="duotone" />
          ) : (
            <CheckCircle className="text-[#256d3f]" size={26} weight="duotone" />
          )}
        </div>
      </div>

      <div className="border-b border-[#deddd6] p-4">
        <h3 className="text-sm font-semibold">Trace</h3>
        <div className="mt-3 space-y-3 text-sm">
          <TraceRow icon={<Cpu size={17} weight="duotone" />} label="Model" value={result?.model_name ?? "pending"} />
          <TraceRow icon={<Stack size={17} weight="duotone" />} label="Job" value={inspectionJob?.job_id ?? "not created"} />
          <TraceRow icon={<Pulse size={17} weight="duotone" />} label="Status" value={inspectionJob?.status ?? "idle"} />
          <TraceRow icon={<Pulse size={17} weight="duotone" />} label="Mode" value={result?.model_mode ?? health?.ai_mode ?? "pending"} />
          <TraceRow icon={<ShieldCheck size={17} weight="duotone" />} label="Boundary" value="AI-assisted triage" />
          <TraceRow icon={<Stack size={17} weight="duotone" />} label="Schema" value={result?.schema_version ?? health?.schema_version ?? "pending"} />
        </div>
      </div>

      <div className="p-4">
        <details className="rounded-[7px] border border-[#deddd6] bg-white p-3" open={Boolean(analysis?.report_markdown)}>
          <summary className="cursor-pointer text-sm font-semibold text-[#171a16]">Report preview</summary>
          <pre className="mt-3 max-h-52 overflow-auto whitespace-pre-wrap text-xs leading-5 text-[#4d554b]">
            {analysis?.report_markdown ?? "Report appears here after analysis."}
          </pre>
        </details>
        <div className="mt-3 grid grid-cols-2 gap-2">
          <button
            className="inline-flex items-center justify-center gap-2 rounded-[7px] bg-[#1d6f43] px-3 py-2.5 text-sm font-semibold text-white transition hover:bg-[#185f39] active:translate-y-[1px] disabled:cursor-not-allowed disabled:bg-[#9aaa9d]"
            disabled={!analysis || !inspectionJob}
            onClick={downloadReportJson}
            type="button"
          >
            <FileArrowDown size={17} weight="duotone" />
            Download JSON report
          </button>
          <button
            className="inline-flex items-center justify-center gap-2 rounded-[7px] border border-[#d8d6cd] bg-white px-3 py-2.5 text-sm font-medium text-[#171a16] transition hover:border-[#171a16] active:translate-y-[1px]"
            disabled={!result}
            type="button"
          >
            <FileText size={17} weight="duotone" />
            Create review task
          </button>
        </div>
      </div>
    </motion.aside>
  );
}

function JobStateBanner({ state }: { state: WorkspaceJobState }) {
  const stateConfig: Record<
    WorkspaceJobState,
    {
      label: string;
      detail: string;
      icon: React.ReactNode;
      className: string;
    }
  > = {
    idle: {
      label: "No job started",
      detail: "Select a sample or upload an image, then run analysis.",
      icon: <ClipboardText size={18} weight="duotone" />,
      className: "border-[#deddd6] bg-white text-[#4d554b]"
    },
    loading: {
      label: "Loading workspace",
      detail: "Connecting to the Orvex API and loading samples.",
      icon: <CircleNotch className="animate-spin" size={18} weight="duotone" />,
      className: "border-[#b8cde0] bg-[#edf5fb] text-[#24506f]"
    },
    error: {
      label: "API or network error",
      detail: "The request did not complete. Check the API service and retry.",
      icon: <XCircle size={18} weight="duotone" />,
      className: "border-[#ddb29f] bg-[#f8ebe4] text-[#8c3920]"
    },
    queued: {
      label: "Job queued",
      detail: "The selected image has been submitted for inspection.",
      icon: <HourglassMedium size={18} weight="duotone" />,
      className: "border-[#dbc58d] bg-[#f7f0de] text-[#7a5714]"
    },
    processing: {
      label: "Job processing",
      detail: "The inspection result is being generated.",
      icon: <CircleNotch className="animate-spin" size={18} weight="duotone" />,
      className: "border-[#b8cde0] bg-[#edf5fb] text-[#24506f]"
    },
    completed: {
      label: "Job completed",
      detail: "Review the provisional result and report below.",
      icon: <CheckCircle size={18} weight="duotone" />,
      className: "border-[#b7d7c2] bg-[#e9f4ed] text-[#256d3f]"
    },
    failed: {
      label: "Job failed",
      detail: "The API returned a failed inspection job.",
      icon: <XCircle size={18} weight="duotone" />,
      className: "border-[#ddb29f] bg-[#f8ebe4] text-[#8c3920]"
    },
    unsupported: {
      label: "Input unsupported",
      detail: "This workflow currently accepts still images only.",
      icon: <WarningOctagon size={18} weight="duotone" />,
      className: "border-[#ddb29f] bg-[#f8ebe4] text-[#8c3920]"
    }
  };
  const config = stateConfig[state];

  return (
    <div className={`border-b p-4 ${config.className}`}>
      <div className="flex items-start gap-3">
        <span className="mt-0.5 shrink-0">{config.icon}</span>
        <div>
          <div className="text-sm font-semibold">{config.label}</div>
          <div className="mt-1 text-xs leading-5 opacity-85">{config.detail}</div>
        </div>
      </div>
    </div>
  );
}

function Metric({ label, value, suffix }: { label: string; value: string; suffix?: string }) {
  return (
    <div className="border-r border-[#deddd6] p-4 last:border-r-0">
      <div className="text-xs uppercase tracking-[0.12em] text-[#82887f]">{label}</div>
      <div className="mt-2 font-mono text-2xl text-[#171a16]">{value}</div>
      {suffix ? <div className="mt-1 text-[11px] uppercase tracking-[0.1em] text-[#82887f]">{suffix}</div> : null}
    </div>
  );
}

function TraceRow({ icon, label, value }: { icon: React.ReactNode; label: string; value: string }) {
  return (
    <div className="grid grid-cols-[22px_80px_minmax(0,1fr)] items-center gap-2">
      <span className="text-[#687066]">{icon}</span>
      <span className="text-[#687066]">{label}</span>
      <span className="truncate font-mono text-xs text-[#171a16]">{value}</span>
    </div>
  );
}
