import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronDown,
  ChevronRight,
  CircleDashed,
  ClipboardList,
  Cpu,
  FileCheck2,
  FileWarning,
  Loader2,
  PencilLine,
  Play,
  PlusCircle,
  RotateCcw,
  Upload,
  X,
} from "lucide-react";
import {
  getPcbaDetail,
  getStatus,
  ingestInputs,
  listPcbas,
  processPcba,
  uploadInputs,
} from "../../api/tpi";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  TpiInput,
  TpiInputStatus,
  TpiInputType,
  TpiPcbaRow,
  TpiPcbaStatus,
  TpiStatus,
} from "../../types";

// Poll the pipeline while PCBAs move through ingestion/processing so the badges
// stay live, matching the source-comparison IngestionMonitor interval.
const REFETCH_INTERVAL_MS = 5000;

// ---------------------------------------------------------------------------
// Status badge presentation (Req 6.9, Req 7.3)
//
// Each pipeline status carries a distinct color AND a distinct label AND a
// lucide icon, so status is never conveyed by color alone. The icon is marked
// aria-hidden — the visible text label is what assistive tech announces.
// ---------------------------------------------------------------------------
const PCBA_STATUS_BADGE: Record<
  TpiPcbaStatus,
  { label: string; className: string; Icon: typeof CircleDashed }
> = {
  ingesting: {
    label: "Ingesting",
    className: "border-sky-300 bg-sky-50 text-sky-800",
    Icon: CircleDashed,
  },
  drafted: {
    label: "Drafted",
    className: "border-indigo-300 bg-indigo-50 text-indigo-800",
    Icon: FileCheck2,
  },
  in_review: {
    label: "In review",
    className: "border-amber-300 bg-amber-50 text-amber-800",
    Icon: PencilLine,
  },
  finalized: {
    label: "Finalized",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
    Icon: CheckCircle2,
  },
};

function PcbaStatusBadge({ status }: { status: TpiPcbaStatus }) {
  const cfg = PCBA_STATUS_BADGE[status] ?? {
    label: status,
    className: "border-slate-300 bg-slate-100 text-slate-700",
    Icon: CircleDashed,
  };
  const { Icon } = cfg;
  return (
    <Badge variant="outline" className={`gap-1 font-semibold ${cfg.className}`}>
      <Icon aria-hidden="true" />
      {cfg.label}
    </Badge>
  );
}

// Per-input ingestion/extraction status (Req 1.4, 2.4): a flagged input is
// shown with a warning icon + text, an ingested one with a check.
const INPUT_STATUS_META: Record<
  TpiInputStatus,
  { label: string; className: string; Icon: typeof CheckCircle2 }
> = {
  ingested: {
    label: "Ingested",
    className: "text-emerald-700",
    Icon: CheckCircle2,
  },
  flagged_for_manual_annotation: {
    label: "Needs manual annotation",
    className: "text-amber-700",
    Icon: FileWarning,
  },
};

const INPUT_TYPE_LABELS: Record<TpiInputType, string> = {
  testing_procedure: "Testing procedure",
  operating_procedure: "Operating procedure",
  circuit_diagram: "Circuit diagram",
  drawing: "Drawing",
};

// ---------------------------------------------------------------------------
// Demo seeding (Req 10.1, [CONFIRM] visual-input format)
//
// Ingestion needs input file paths. Real ingestion happens elsewhere; for the
// demonstration flow we seed the known sample fixtures shipped under
// backend/sample_data/tpi/<PCBA>/. These are clearly-marked fixtures pending
// real client samples, so the affordance below is labelled "demo".
// ---------------------------------------------------------------------------
const SAMPLE_FIXTURE_ROOT = "sample_data/tpi";

const SAMPLE_PCBA_IDS = [
  "PCBA-444-027654-002",
  "PCBA-444-027654-003",
  "PCBA-444-027654-004",
  "PCBA-622-073891-010",
] as const;

// The four confirmed input types and their fixture filenames (visual inputs are
// .txt stand-ins until the format is [CONFIRM]ed — see the fixtures README).
const SAMPLE_INPUT_FILES: { input_type: TpiInputType; filename: string }[] = [
  { input_type: "testing_procedure", filename: "testing_procedure.md" },
  { input_type: "operating_procedure", filename: "operating_procedure.md" },
  { input_type: "circuit_diagram", filename: "circuit_diagram.txt" },
  { input_type: "drawing", filename: "drawing.txt" },
];

function sampleInputsFor(pcbaId: string) {
  return SAMPLE_INPUT_FILES.map((f) => ({
    input_type: f.input_type,
    filename: f.filename,
    path: `${SAMPLE_FIXTURE_ROOT}/${pcbaId}/${f.filename}`,
  }));
}

// ---------------------------------------------------------------------------
// Non-blocking notification (Req 6.8)
//
// The portal has no shared toast library, so this is a minimal, self-contained,
// auto-dismissing notification that mirrors the portal's banner styling and
// stays out of the way (fixed, bottom-right, dismissible).
// ---------------------------------------------------------------------------
type ToastKind = "success" | "error";
interface ToastMessage {
  id: number;
  kind: ToastKind;
  text: string;
}

function ToastStack({
  toasts,
  onDismiss,
}: {
  toasts: ToastMessage[];
  onDismiss: (id: number) => void;
}) {
  if (toasts.length === 0) return null;
  return (
    <div
      className="fixed bottom-6 right-6 z-50 flex w-80 flex-col gap-2"
      role="status"
      aria-live="polite"
    >
      {toasts.map((t) => {
        const success = t.kind === "success";
        const Icon = success ? CheckCircle2 : AlertTriangle;
        return (
          <div
            key={t.id}
            className={`flex items-start gap-2 rounded-lg border px-4 py-3 shadow-elevated ${
              success
                ? "border-emerald-200 bg-emerald-50 text-emerald-900"
                : "border-red-200 bg-red-50 text-red-900"
            }`}
          >
            <Icon
              aria-hidden="true"
              className={`mt-0.5 size-5 shrink-0 ${
                success ? "text-emerald-600" : "text-red-600"
              }`}
            />
            <p className="flex-1 text-sm">{t.text}</p>
            <button
              type="button"
              onClick={() => onDismiss(t.id)}
              aria-label="Dismiss notification"
              // Raw button: add a focus-visible ring so keyboard users get a
              // visible focus indicator matching the design system (Req 7.1).
              className="rounded p-0.5 text-current/70 hover:text-current focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <X className="size-4" aria-hidden="true" />
            </button>
          </div>
        );
      })}
    </div>
  );
}

export function TpiMonitor() {
  const queryClient = useQueryClient();

  const [toasts, setToasts] = useState<ToastMessage[]>([]);
  const [uploadOpen, setUploadOpen] = useState(false);
  // Provider chosen for the next Process run (Part A). Defaults to the
  // configured default surfaced by /tpi/status once it loads.
  const [provider, setProvider] = useState<"mock" | "openai">("mock");
  const dismissToast = useCallback(
    (id: number) => setToasts((ts) => ts.filter((t) => t.id !== id)),
    []
  );
  const pushToast = useCallback(
    (kind: ToastKind, text: string) => {
      const id = Date.now() + Math.random();
      setToasts((ts) => [...ts, { id, kind, text }]);
      // Auto-dismiss so the notification stays non-blocking.
      window.setTimeout(() => dismissToast(id), 5000);
    },
    [dismissToast]
  );

  const {
    data: pcbas,
    isLoading: pcbasLoading,
    isError: pcbasError,
    refetch: refetchPcbas,
  } = useQuery({
    queryKey: ["tpi", "pcbas"],
    queryFn: listPcbas,
    refetchInterval: REFETCH_INTERVAL_MS,
    placeholderData: keepPreviousData,
  });

  const { data: status } = useQuery({
    queryKey: ["tpi", "status"],
    queryFn: getStatus,
    refetchInterval: REFETCH_INTERVAL_MS,
    placeholderData: keepPreviousData,
  });

  // Seed the provider selection from the backend's configured default the first
  // time status loads (only mock/openai are selectable). Subsequent user edits
  // are preserved — this only runs while the value is still the initial "mock".
  const statusProvider = status?.llm_provider;
  const providerSeededRef = useRef(false);
  useEffect(() => {
    if (providerSeededRef.current) return;
    if (statusProvider === "mock" || statusProvider === "openai") {
      setProvider(statusProvider);
      providerSeededRef.current = true;
    }
  }, [statusProvider]);

  // Which PCBA rows are expanded to show per-input detail.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggleExpanded = useCallback((pcbaId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(pcbaId)) next.delete(pcbaId);
      else next.add(pcbaId);
      return next;
    });
  }, []);

  const invalidatePipeline = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["tpi", "pcbas"] });
    queryClient.invalidateQueries({ queryKey: ["tpi", "status"] });
  }, [queryClient]);

  // Process a PCBA (extract → map → generate). Track which PCBA is running so
  // only its control shows a pending state and is disabled (Req 6.7).
  const processMutation = useMutation({
    mutationFn: (pcbaId: string) => processPcba(pcbaId, provider),
    onSuccess: (_draft, pcbaId) => {
      pushToast("success", `Draft TPI generated for ${pcbaId}.`);
      queryClient.invalidateQueries({ queryKey: ["tpi", "pcba-detail", pcbaId] });
      invalidatePipeline();
    },
    onError: (err, pcbaId) => {
      pushToast(
        "error",
        `Couldn't process ${pcbaId}. ${
          err instanceof Error ? err.message : "Please try again."
        }`
      );
    },
  });

  // Demo seeding: ingest the sample fixtures for every sample PCBA that isn't
  // present yet, then refresh the list.
  const seedMutation = useMutation({
    mutationFn: async () => {
      const existing = new Set((pcbas ?? []).map((p) => p.pcba_id));
      const toSeed = SAMPLE_PCBA_IDS.filter((id) => !existing.has(id));
      for (const pcbaId of toSeed) {
        await ingestInputs(pcbaId, sampleInputsFor(pcbaId));
      }
      return toSeed.length;
    },
    onSuccess: (seededCount) => {
      pushToast(
        "success",
        seededCount > 0
          ? `Ingested ${seededCount} sample PCBA${seededCount === 1 ? "" : "s"}.`
          : "All sample PCBAs are already ingested."
      );
      invalidatePipeline();
    },
    onError: (err) => {
      pushToast(
        "error",
        `Couldn't ingest sample PCBAs. ${
          err instanceof Error ? err.message : "Please try again."
        }`
      );
    },
  });

  const rows = pcbas ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">
            TPI Monitor
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Sample PCBAs moving through ingestion, extraction, and draft
            generation
          </p>
        </div>
        <div className="flex items-center gap-2">
          {/* Provider selector (Part A): choose which multimodal provider the
              next Process run uses. Labelled for screen-reader/keyboard use. */}
          <div className="flex items-center gap-1.5">
            <Label
              htmlFor="tpi-provider-select"
              className="text-sm font-medium text-slate-700"
            >
              Provider
            </Label>
            <select
              id="tpi-provider-select"
              value={provider}
              onChange={(e) =>
                setProvider(e.target.value === "openai" ? "openai" : "mock")
              }
              title="Multimodal provider used for the next Process run"
              className="h-8 rounded-md border border-slate-300 bg-white px-2 text-sm font-medium text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <option value="mock">mock</option>
              <option value="openai">openai</option>
            </select>
          </div>
          <Button
            variant="default"
            size="sm"
            onClick={() => setUploadOpen((v) => !v)}
            aria-expanded={uploadOpen}
            title="Upload your own four PCBA input files"
          >
            <Upload className="mr-1.5" aria-hidden="true" />
            Upload a PCBA
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => seedMutation.mutate()}
            disabled={seedMutation.isPending}
            title="Ingest the bundled sample fixtures (demonstration seeding)"
          >
            {seedMutation.isPending ? (
              <Loader2 className="mr-1.5 animate-spin" aria-hidden="true" />
            ) : (
              <PlusCircle className="mr-1.5" aria-hidden="true" />
            )}
            {seedMutation.isPending ? "Ingesting…" : "Ingest sample PCBAs"}
            {/* Meaningful label — use a slate-600 shade that meets WCAG AA (Req 7.3). */}
            <span className="ml-1.5 text-xs font-semibold uppercase tracking-wide text-slate-600">
              demo
            </span>
          </Button>
        </div>
      </div>

      {/* Real upload intake: the user submits their own four files (multipart),
          distinct from the demo seeding which references bundled fixtures. */}
      {uploadOpen ? (
        <UploadPanel
          onClose={() => setUploadOpen(false)}
          pushToast={pushToast}
          onIngested={invalidatePipeline}
        />
      ) : null}

      {/* Pipeline / config status: active provider, status-count summary, and
          any unresolved [CONFIRM] open items (Req 6.9). */}
      <StatusSummary status={status} />
      <ConfirmItemsBanner status={status} />

      {/* PCBA list — loading / error / empty / data */}
      {pcbasLoading && rows.length === 0 ? (
        <LoadingState />
      ) : pcbasError ? (
        <ErrorState onRetry={() => refetchPcbas()} />
      ) : rows.length === 0 ? (
        <EmptyState
          onSeed={() => seedMutation.mutate()}
          seeding={seedMutation.isPending}
        />
      ) : (
        <div className="space-y-3">
          {rows.map((row) => (
            <PcbaCard
              key={row.pcba_id}
              row={row}
              expanded={expanded.has(row.pcba_id)}
              onToggle={() => toggleExpanded(row.pcba_id)}
              onProcess={() => processMutation.mutate(row.pcba_id)}
              processing={
                processMutation.isPending &&
                processMutation.variables === row.pcba_id
              }
            />
          ))}
        </div>
      )}

      <ToastStack toasts={toasts} onDismiss={dismissToast} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Upload panel — real multipart intake (Req 1.1)
//
// A user submits their own four input files from the browser. The PCBA id is
// required; each of the four files is optional but at least one is required.
// Every control is labelled (Label + htmlFor/id) for keyboard + screen-reader
// use, and the submit button disables while the upload is pending.
// ---------------------------------------------------------------------------
const UPLOAD_FILE_FIELDS: { field: TpiInputType; label: string; id: string }[] =
  [
    { field: "testing_procedure", label: "Testing procedure", id: "upload-testing-procedure" },
    { field: "operating_procedure", label: "Operating procedure", id: "upload-operating-procedure" },
    { field: "circuit_diagram", label: "Circuit diagram", id: "upload-circuit-diagram" },
    { field: "drawing", label: "Drawing", id: "upload-drawing" },
  ];

function UploadPanel({
  onClose,
  pushToast,
  onIngested,
}: {
  onClose: () => void;
  pushToast: (kind: ToastKind, text: string) => void;
  onIngested: () => void;
}) {
  const [pcbaId, setPcbaId] = useState("");
  const [selected, setSelected] = useState<Partial<Record<TpiInputType, File>>>(
    {}
  );

  const trimmedId = pcbaId.trim();
  const chosenFiles = Object.values(selected).filter(Boolean) as File[];
  const canSubmit = trimmedId.length > 0 && chosenFiles.length > 0;

  const uploadMutation = useMutation({
    mutationFn: () => uploadInputs(trimmedId, selected),
    onSuccess: (inputs) => {
      pushToast(
        "success",
        `Uploaded ${inputs.length} input${
          inputs.length === 1 ? "" : "s"
        } for ${trimmedId}.`
      );
      onIngested();
      onClose();
    },
    onError: (err) => {
      pushToast(
        "error",
        `Couldn't upload files for ${trimmedId || "PCBA"}. ${
          err instanceof Error ? err.message : "Please try again."
        }`
      );
    },
  });

  const setFile = useCallback((field: TpiInputType, file: File | undefined) => {
    setSelected((prev) => {
      const next = { ...prev };
      if (file) next[field] = file;
      else delete next[field];
      return next;
    });
  }, []);

  return (
    <Card className="rounded-xl border border-slate-200 p-4 shadow-sm">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h2 className="text-base font-semibold text-slate-900">
            Upload a PCBA
          </h2>
          <p className="mt-0.5 text-xs text-slate-500">
            Submit your own input files. Provide a PCBA id and at least one of the
            four inputs.
          </p>
        </div>
        <button
          type="button"
          onClick={onClose}
          aria-label="Close upload panel"
          className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          <X className="size-4" aria-hidden="true" />
        </button>
      </div>

      <form
        className="space-y-4"
        onSubmit={(e) => {
          e.preventDefault();
          if (canSubmit) uploadMutation.mutate();
        }}
      >
        <div className="space-y-1.5">
          <Label htmlFor="upload-pcba-id">PCBA id</Label>
          <Input
            id="upload-pcba-id"
            value={pcbaId}
            onChange={(e) => setPcbaId(e.target.value)}
            placeholder="e.g. PCBA-778-100200-050"
            required
            className="max-w-sm font-mono"
          />
        </div>

        <div className="grid gap-3 sm:grid-cols-2">
          {UPLOAD_FILE_FIELDS.map(({ field, label, id }) => (
            <div key={field} className="space-y-1.5">
              <Label htmlFor={id}>
                {label}{" "}
                <span className="font-normal text-slate-500">(optional)</span>
              </Label>
              <input
                id={id}
                type="file"
                onChange={(e) => setFile(field, e.target.files?.[0])}
                className="block w-full text-sm text-slate-600 file:mr-3 file:rounded-md file:border file:border-slate-300 file:bg-slate-50 file:px-3 file:py-1.5 file:text-xs file:font-medium file:text-slate-700 hover:file:bg-slate-100 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
              />
            </div>
          ))}
        </div>

        <div className="flex items-center gap-3">
          <Button
            type="submit"
            variant="default"
            size="sm"
            disabled={!canSubmit || uploadMutation.isPending}
          >
            {uploadMutation.isPending ? (
              <>
                <Loader2 className="mr-1.5 animate-spin" aria-hidden="true" />
                Uploading…
              </>
            ) : (
              <>
                <Upload className="mr-1.5" aria-hidden="true" />
                Upload
              </>
            )}
          </Button>
          {!canSubmit ? (
            <p className="text-xs text-slate-500">
              Enter a PCBA id and choose at least one file.
            </p>
          ) : null}
        </div>
      </form>
    </Card>
  );
}

// ---------------------------------------------------------------------------
// Per-PCBA card
// ---------------------------------------------------------------------------
function PcbaCard({
  row,
  expanded,
  onToggle,
  onProcess,
  processing,
}: {
  row: TpiPcbaRow;
  expanded: boolean;
  onToggle: () => void;
  onProcess: () => void;
  processing: boolean;
}) {
  // A draft exists once the PCBA has moved past ingestion.
  const hasDraft =
    row.status === "drafted" ||
    row.status === "in_review" ||
    row.status === "finalized";

  return (
    <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3.5">
        {/* Expand / collapse per-input detail */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={
            expanded
              ? `Hide inputs for ${row.pcba_id}`
              : `Show inputs for ${row.pcba_id}`
          }
          // Raw button: add a focus-visible ring for keyboard operability (Req 7.1).
          className="rounded p-1 text-slate-500 hover:bg-slate-100 hover:text-slate-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
        >
          {expanded ? (
            <ChevronDown className="size-4" aria-hidden="true" />
          ) : (
            <ChevronRight className="size-4" aria-hidden="true" />
          )}
        </button>

        <div className="min-w-0 flex-1">
          <p className="truncate font-mono text-base font-semibold text-slate-900">
            {row.pcba_id}
          </p>
          <p className="mt-0.5 text-xs text-slate-500">
            Created {formatDate(row.created_at)}
            {row.template_kind ? (
              <>
                {" · "}
                <span className="capitalize">{row.template_kind}</span> template
              </>
            ) : null}
          </p>
        </div>

        <PcbaStatusBadge status={row.status} />

        {row.review_state ? (
          <Badge
            variant="outline"
            className="border-slate-300 bg-slate-50 text-xs capitalize text-slate-600"
          >
            {row.review_state.replace(/_/g, " ")}
          </Badge>
        ) : null}

        <div className="flex items-center gap-2">
          <Button
            variant="default"
            size="sm"
            onClick={onProcess}
            disabled={processing}
            title="Run extraction, mapping, and draft generation"
          >
            {processing ? (
              <>
                <Loader2 className="mr-1.5 animate-spin" aria-hidden="true" />
                Processing…
              </>
            ) : (
              <>
                <Play className="mr-1.5" aria-hidden="true" />
                {hasDraft ? "Re-process" : "Process"}
              </>
            )}
          </Button>
          {hasDraft ? (
            <Button
              variant="outline"
              size="sm"
              render={<Link to={`/tpi/review/${row.pcba_id}`} />}
            >
              <ClipboardList className="mr-1.5" aria-hidden="true" />
              Review
            </Button>
          ) : null}
        </div>
      </div>

      {expanded ? <PcbaInputDetail pcbaId={row.pcba_id} /> : null}
    </Card>
  );
}

// Lazily loads the PCBA's per-input ingestion/extraction status when expanded.
function PcbaInputDetail({ pcbaId }: { pcbaId: string }) {
  const { data, isLoading, isError, refetch } = useQuery({
    queryKey: ["tpi", "pcba-detail", pcbaId],
    queryFn: () => getPcbaDetail(pcbaId),
  });

  if (isLoading) {
    return (
      <div className="flex items-center gap-2 border-t border-slate-100 bg-slate-50/60 px-4 py-4 text-sm text-slate-500">
        <Loader2 className="size-4 animate-spin" aria-hidden="true" />
        Loading inputs…
      </div>
    );
  }

  if (isError || !data) {
    return (
      <div className="flex items-center justify-between gap-3 border-t border-slate-100 bg-slate-50/60 px-4 py-4">
        <p className="text-sm text-slate-600">
          Couldn't load this PCBA's inputs.
        </p>
        <Button variant="outline" size="sm" onClick={() => refetch()}>
          <RotateCcw className="mr-1" aria-hidden="true" />
          Retry
        </Button>
      </div>
    );
  }

  const inputs: TpiInput[] = data.inputs ?? [];

  if (inputs.length === 0) {
    return (
      <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-4 text-sm text-slate-500">
        No inputs recorded for this PCBA yet.
      </div>
    );
  }

  return (
    <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-3">
      <p className="mb-2 text-xs font-semibold uppercase tracking-wide text-slate-600">
        Inputs
      </p>
      <ul className="divide-y divide-slate-100 rounded-lg border border-slate-200 bg-white">
        {inputs.map((inp) => (
          <InputRow key={inp.id} input={inp} />
        ))}
      </ul>
    </div>
  );
}

function InputRow({ input }: { input: TpiInput }) {
  const meta = INPUT_STATUS_META[input.status] ?? {
    label: input.status,
    className: "text-slate-600",
    Icon: CircleDashed,
  };
  const { Icon } = meta;
  const typeLabel = INPUT_TYPE_LABELS[input.input_type] ?? input.input_type;

  return (
    <li className="flex flex-wrap items-center gap-x-3 gap-y-1 px-3 py-2.5">
      <span className="w-40 shrink-0 text-sm font-medium text-slate-800">
        {typeLabel}
      </span>
      <span className="min-w-0 flex-1 truncate font-mono text-xs text-slate-500">
        {input.filename}
      </span>
      {input.detected_format ? (
        <Badge
          variant="outline"
          className="border-slate-300 bg-slate-50 text-[10px] uppercase text-slate-600"
        >
          {input.detected_format}
        </Badge>
      ) : (
        <span className="text-xs uppercase text-slate-600">
          format unknown
        </span>
      )}
      <span
        className={`inline-flex items-center gap-1 text-xs font-medium ${meta.className}`}
      >
        <Icon className="size-3.5" aria-hidden="true" />
        {meta.label}
      </span>
    </li>
  );
}

// ---------------------------------------------------------------------------
// Status summary + [CONFIRM] banner (Req 6.9)
// ---------------------------------------------------------------------------
function StatusSummary({ status }: { status: TpiStatus | undefined }) {
  const counts = status?.pcba_status_counts ?? {};

  // Show the four pipeline stages in order, plus the provider chip.
  const ordered: TpiPcbaStatus[] = [
    "ingesting",
    "drafted",
    "in_review",
    "finalized",
  ];

  return (
    <div className="flex flex-wrap items-center gap-3">
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700">
        <Cpu className="size-3.5 text-slate-500" aria-hidden="true" />
        LLM provider:{" "}
        <span className="font-semibold text-slate-900">
          {status?.llm_provider ?? "—"}
        </span>
      </span>
      <span className="inline-flex items-center gap-1.5 rounded-lg border border-slate-200 bg-white px-3 py-1.5 text-xs font-medium text-slate-700">
        Total PCBAs:{" "}
        <span className="font-semibold text-slate-900">
          {status?.total_pcbas ?? 0}
        </span>
      </span>
      {ordered.map((s) => {
        const cfg = PCBA_STATUS_BADGE[s];
        const count = counts[s] ?? 0;
        const { Icon } = cfg;
        return (
          <span
            key={s}
            className={`inline-flex items-center gap-1.5 rounded-lg border px-3 py-1.5 text-xs font-medium ${cfg.className}`}
          >
            <Icon className="size-3.5" aria-hidden="true" />
            {cfg.label}:{" "}
            <span className="font-semibold tabular-nums">{count}</span>
          </span>
        );
      })}
    </div>
  );
}

function ConfirmItemsBanner({ status }: { status: TpiStatus | undefined }) {
  const items = status?.confirm_items ?? [];
  if (items.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-start gap-3">
        <AlertTriangle
          className="mt-0.5 size-5 shrink-0 text-amber-600"
          aria-hidden="true"
        />
        <div className="space-y-2">
          <div>
            <p className="text-sm font-semibold text-amber-900">
              Open items awaiting client confirmation
            </p>
            <p className="mt-0.5 text-xs text-amber-800">
              These items are surfaced rather than silently assumed. The pipeline
              runs with the documented placeholder until each is confirmed.
            </p>
          </div>
          <ul className="space-y-1.5">
            {items.map((item) => (
              <li
                key={item.key}
                className="flex items-start gap-2 text-xs text-amber-900"
              >
                <Badge
                  variant="outline"
                  className="border-amber-300 bg-amber-100 font-semibold text-amber-900"
                >
                  CONFIRM
                </Badge>
                <span>
                  <span className="font-medium">{item.label}</span>
                  {item.detail ? (
                    <span className="text-amber-800"> — {item.detail}</span>
                  ) : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading / error / empty states (Req 6.2, 6.3, 6.4)
// ---------------------------------------------------------------------------
function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="size-8 animate-spin text-lam-navy" aria-hidden="true" />
      <span className="sr-only">Loading PCBAs…</span>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="text-center py-20">
      <AlertTriangle
        className="mx-auto mb-4 size-16 text-muted-foreground/30"
        aria-hidden="true"
      />
      <h3 className="text-lg font-medium text-muted-foreground">
        We couldn't load the PCBAs
      </h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground/70">
        Something went wrong reaching the TPI service. Check your connection and
        try again.
      </p>
      <Button variant="outline" size="sm" className="mt-5" onClick={onRetry}>
        <RotateCcw className="mr-1.5" aria-hidden="true" />
        Retry
      </Button>
    </div>
  );
}

function EmptyState({
  onSeed,
  seeding,
}: {
  onSeed: () => void;
  seeding: boolean;
}) {
  return (
    <div className="text-center py-20">
      <ClipboardList
        className="mx-auto mb-4 size-16 text-muted-foreground/30"
        aria-hidden="true"
      />
      <h3 className="text-lg font-medium text-muted-foreground">
        No PCBAs yet
      </h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground/70">
        Ingest the bundled sample inputs to begin. Each PCBA's four inputs are
        ingested, then you can run processing to generate a draft TPI.
      </p>
      <Button variant="default" size="sm" className="mt-5" onClick={onSeed} disabled={seeding}>
        {seeding ? (
          <Loader2 className="mr-1.5 animate-spin" aria-hidden="true" />
        ) : (
          <PlusCircle className="mr-1.5" aria-hidden="true" />
        )}
        {seeding ? "Ingesting…" : "Ingest sample PCBAs"}
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Utilities
// ---------------------------------------------------------------------------
function formatDate(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
