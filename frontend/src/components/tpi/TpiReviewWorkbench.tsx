import { useCallback, useEffect, useMemo, useState } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowLeft,
  CheckCircle2,
  FileWarning,
  Link2,
  Loader2,
  Undo2,
  X,
} from "lucide-react";
import { getDraft, finalizeDraft, getPcbaDetail } from "../../api/tpi";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type {
  DraftTpi,
  TpiInput,
  TpiInputStatus,
  TpiInputType,
  TpiSection,
} from "../../types";

// Human-readable labels for the input types (matches the monitor view).
const INPUT_TYPE_LABELS: Record<TpiInputType, string> = {
  testing_procedure: "Testing procedure",
  operating_procedure: "Operating procedure",
  circuit_diagram: "Circuit diagram",
  drawing: "Drawing",
};

// Logical display order for the four source inputs: the two text procedures
// first (they feed the draft body), then the two visual inputs.
const SOURCE_INPUT_ORDER: TpiInputType[] = [
  "testing_procedure",
  "operating_procedure",
  "circuit_diagram",
  "drawing",
];

// Per-input ingestion/extraction status meaning (Req 1.4, 2.4), mirroring
// TpiMonitor's INPUT_STATUS_META: text + icon (not color-only) so the reviewer
// sees whether each source input was ingested or needs manual annotation.
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

const DEFAULT_REVIEWER = "IQA Reviewer";

// Lightweight non-blocking feedback (Req 6.8). The portal has no toast library,
// so — matching the codebase's local-state feedback pattern — we render a
// dismissible, auto-clearing banner rather than adding a dependency.
type Feedback = { kind: "success" | "error"; message: string } | null;

// ---------------------------------------------------------------------------
// TpiReviewWorkbench — deep-linkable per-PCBA review surface (/tpi/review/:pcbaId,
// Req 6.10). It shows the draft section by section with provenance back to the
// source inputs (Req 3.3) and visible incomplete markers (Req 3.4), supports
// inline section editing with per-section save/discard plus an unsaved-changes
// guard (Req 6.6), and finalizes with a reviewer name, an optional note, and
// non-blocking feedback (Req 6.8). Loading and not-found states mirror
// SourceComparisonWorkbench.
// ---------------------------------------------------------------------------

export function TpiReviewWorkbench() {
  const { pcbaId } = useParams<{ pcbaId: string }>();
  const navigate = useNavigate();
  const queryClient = useQueryClient();

  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  const [note, setNote] = useState("");
  const [feedback, setFeedback] = useState<Feedback>(null);

  // Edited section content, keyed by section key. Initialized from the fetched
  // draft; each entry holds the "committed" (saved-locally) edited content.
  const [edited, setEdited] = useState<Record<string, string>>({});

  const {
    data: draft,
    isLoading,
    isError,
  } = useQuery({
    queryKey: ["tpi", "draft", pcbaId],
    queryFn: () => getDraft(pcbaId!),
    enabled: !!pcbaId,
  });

  // Fetch the PCBA detail for its inputs (which carry input_type,
  // detected_format, and preview_url) so we can show the source images
  // alongside the generated analysis (Part B).
  const { data: pcbaDetail } = useQuery({
    queryKey: ["tpi", "pcba-detail", pcbaId],
    queryFn: () => getPcbaDetail(pcbaId!),
    enabled: !!pcbaId,
  });

  // Seed local edit state once the draft arrives (and whenever a fresh draft is
  // fetched). Committed edits start equal to the draft content.
  useEffect(() => {
    if (!draft) return;
    setEdited(
      Object.fromEntries(draft.sections.map((s) => [s.key, s.content]))
    );
  }, [draft]);

  // Unsaved changes = any committed edit that differs from the fetched draft.
  const hasUnsavedChanges = useMemo(() => {
    if (!draft) return false;
    return draft.sections.some((s) => (edited[s.key] ?? s.content) !== s.content);
  }, [draft, edited]);

  // Warn on browser/tab navigation while there are unsaved edits (Req 6.6).
  useEffect(() => {
    if (!hasUnsavedChanges) return;
    const handler = (e: BeforeUnloadEvent) => {
      e.preventDefault();
      e.returnValue = "";
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [hasUnsavedChanges]);

  // Guarded in-app navigation: confirm before leaving with unsaved edits.
  const guardedNavigate = useCallback(
    (to: string) => {
      if (
        hasUnsavedChanges &&
        !window.confirm(
          "You have unsaved changes. Leave this draft and discard them?"
        )
      ) {
        return;
      }
      navigate(to);
    },
    [hasUnsavedChanges, navigate]
  );

  // Build the corrected sections, preserving provenance + incomplete markers
  // (only the content is replaced by the reviewer's committed edits, Req 6.6).
  const buildCorrectedSections = useCallback(
    (d: DraftTpi): TpiSection[] =>
      d.sections.map((s) => ({
        ...s,
        content: edited[s.key] ?? s.content,
      })),
    [edited]
  );

  const finalizeMutation = useMutation({
    mutationFn: () =>
      finalizeDraft(pcbaId!, {
        reviewer: reviewer.trim() || DEFAULT_REVIEWER,
        note: note.trim() || undefined,
        corrected_sections: buildCorrectedSections(draft!),
      }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["tpi"] });
      setFeedback({ kind: "success", message: "TPI finalized." });
      navigate("/tpi/final");
    },
    onError: () => {
      setFeedback({
        kind: "error",
        message: "Could not finalize the TPI. Please try again.",
      });
    },
  });

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-[calc(100vh-3rem)]">
        <Loader2 className="w-8 h-8 text-lam-navy animate-spin" aria-hidden />
        <span className="sr-only">Loading draft…</span>
      </div>
    );
  }

  if (isError || !draft) {
    return (
      <div className="p-6">
        <Button
          variant="ghost"
          size="sm"
          onClick={() => navigate("/tpi/review")}
        >
          <ArrowLeft className="mr-1" />
          Back to Review
        </Button>
        <div className="text-center py-20">
          <AlertTriangle className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">
            Draft not found
          </h3>
          <p className="text-sm text-muted-foreground/70 mt-1">
            The draft you are looking for does not exist or has not been
            generated yet.
          </p>
        </div>
      </div>
    );
  }

  const incompleteCount = draft.sections.filter((s) => s.incomplete).length;
  // Finalize is gated on a non-empty reviewer name; surface the reason to AT.
  const reviewerMissing = reviewer.trim().length === 0;

  return (
    <div className="flex flex-col min-h-[calc(100vh-3rem)]">
      {/* Subheader */}
      <div className="flex items-center justify-between px-6 py-3 bg-background border-b">
        <div className="flex items-center gap-4">
          <Button
            variant="ghost"
            size="sm"
            onClick={() => guardedNavigate("/tpi/review")}
          >
            <ArrowLeft className="mr-1" />
            Review
          </Button>
          <div className="w-px h-5 bg-border" />
          <div>
            <h1 className="text-sm font-bold text-foreground font-mono">
              {draft.pcba_id}
            </h1>
            <p className="text-xs text-slate-600">
              {draft.sections.length}{" "}
              {draft.sections.length === 1 ? "section" : "sections"} · via{" "}
              {draft.provider}
            </p>
            {/* Honest note about what the provider actually did (Part B). */}
            <p className="mt-0.5 text-[11px] text-slate-500">
              {draft.provider === "openai"
                ? "Analyzed by OpenAI vision."
                : "Mock provider: image shown for reference; analysis is synthetic (not vision-based). Select OpenAI to analyze the image."}
            </p>
          </div>
        </div>
        <div className="flex items-center gap-2">
          {hasUnsavedChanges ? (
            <Badge variant="secondary" className="text-xs">
              <AlertTriangle className="size-3" aria-hidden />
              Unsaved changes
            </Badge>
          ) : null}
          <Badge
            variant="secondary"
            className="text-xs"
            title="TPI template used for this draft"
          >
            {draft.template_kind === "client"
              ? "Client template"
              : "Placeholder template"}
          </Badge>
          <Badge variant="outline" className="text-xs capitalize text-slate-700 border-slate-300">
            {draft.review_state.replace(/_/g, " ")}
          </Badge>
        </div>
      </div>

      <div className="flex-1 p-6 space-y-6 w-full max-w-7xl mx-auto">
        {/* Non-blocking feedback (Req 6.8) */}
        {feedback ? (
          <div
            role="status"
            aria-live="polite"
            className={
              feedback.kind === "success"
                ? "flex items-start gap-3 rounded-lg border border-avip-pass/40 bg-avip-pass/5 px-4 py-3"
                : "flex items-start gap-3 rounded-lg border border-destructive/40 bg-destructive/5 px-4 py-3"
            }
          >
            {feedback.kind === "success" ? (
              <CheckCircle2 className="w-5 h-5 text-avip-pass flex-shrink-0 mt-0.5" aria-hidden />
            ) : (
              <AlertTriangle className="w-5 h-5 text-destructive flex-shrink-0 mt-0.5" aria-hidden />
            )}
            <p className="flex-1 text-sm text-slate-700">{feedback.message}</p>
            <button
              type="button"
              onClick={() => setFeedback(null)}
              aria-label="Dismiss notification"
              // Raw button: focus-visible ring for keyboard operability (Req 7.1).
              className="rounded text-slate-500 transition-colors hover:text-slate-700 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring/50"
            >
              <X className="size-4" aria-hidden />
            </button>
          </div>
        ) : null}

        {/* Incomplete summary notice */}
        {incompleteCount > 0 ? (
          <div className="flex items-start gap-3 rounded-lg border border-avip-review/40 bg-avip-review/5 px-4 py-3">
            <AlertTriangle className="w-5 h-5 text-avip-review flex-shrink-0 mt-0.5" aria-hidden />
            <div className="text-sm text-slate-700">
              <span className="font-semibold">
                {incompleteCount}{" "}
                {incompleteCount === 1 ? "section is" : "sections are"}{" "}
                incomplete.
              </span>{" "}
              These were derived from inputs flagged for manual annotation.
              Review and complete them before finalizing.
            </div>
          </div>
        ) : null}

        {/* Source inputs — ALL four source inputs across the top: the text
            procedures as readable excerpts and the visual inputs as image
            previews (Part B). The generated ANALYSIS for each is the mapped
            section content shown below. */}
        <SourceInputsPanel
          pcbaId={draft.pcba_id}
          inputs={pcbaDetail?.inputs ?? []}
        />

        {/* Section-by-section review (Req 6.5) */}
        <div className="space-y-4">
          <h3 className="text-sm font-semibold uppercase tracking-wide text-slate-700">
            TPI Sections
          </h3>
          {draft.sections.map((section) => (
            <SectionEditor
              key={section.key}
              section={section}
              value={edited[section.key] ?? section.content}
              onChange={(content) =>
                setEdited((prev) => ({ ...prev, [section.key]: content }))
              }
              onDiscard={() =>
                setEdited((prev) => ({
                  ...prev,
                  [section.key]: section.content,
                }))
              }
            />
          ))}
        </div>

        {/* Finalize panel */}
        <Card className="p-5 space-y-4">
          <h3 className="text-sm font-semibold text-foreground">Finalize TPI</h3>

          <div className="space-y-2">
            <Label htmlFor="tpi-reviewer">Reviewer</Label>
            <Input
              id="tpi-reviewer"
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              // A reviewer name is required to finalize; mark the field invalid
              // and point it at the helper text so AT announces the requirement
              // (Req 7.4).
              aria-invalid={reviewerMissing || undefined}
              aria-describedby="tpi-reviewer-help"
            />
            <p
              id="tpi-reviewer-help"
              className={
                reviewerMissing
                  ? "text-xs text-destructive"
                  : "text-xs text-slate-600"
              }
            >
              {reviewerMissing
                ? "A reviewer name is required before you can finalize."
                : "Recorded on the audit entry for this finalize decision."}
            </p>
          </div>

          <div className="space-y-2">
            <Label htmlFor="tpi-note">
              Note{" "}
              <span className="text-muted-foreground font-normal">
                (optional)
              </span>
            </Label>
            <textarea
              id="tpi-note"
              value={note}
              onChange={(e) => setNote(e.target.value)}
              rows={3}
              placeholder="Add an optional note about this review decision..."
              className="flex w-full rounded-lg border border-input bg-transparent px-3 py-2 text-sm placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none resize-none"
            />
          </div>

          <div className="flex items-center justify-between gap-3 pt-1">
            <p className="text-xs text-slate-500">
              Finalizing records the current section content as the final TPI
              and writes an audit entry.
            </p>
            <Button
              className="shrink-0 bg-avip-pass hover:bg-avip-pass/90 text-white"
              size="sm"
              onClick={() => finalizeMutation.mutate()}
              disabled={finalizeMutation.isPending || reviewerMissing}
              // Associate the reason the control is disabled so AT can announce
              // WHY finalize is unavailable (Req 7.4).
              aria-describedby={reviewerMissing ? "tpi-reviewer-help" : undefined}
            >
              {finalizeMutation.isPending ? (
                <>
                  <Loader2 className="mr-1.5 size-4 animate-spin" aria-hidden />
                  Finalizing...
                </>
              ) : (
                "Finalize"
              )}
            </Button>
          </div>
        </Card>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// SourceInputsPanel — shows ALL FOUR source inputs that fed the draft, in a
// logical order (testing procedure, operating procedure, circuit diagram,
// drawing). Each input renders a card with its type label, detected-format
// badge, and a per-input status indicator (ingested / needs manual annotation,
// text + icon — not color-only). VISUAL inputs (circuit diagram / drawing) show
// their <img> preview when the backend supplied a preview_url (with an honest
// note when it did not); TEXT inputs (testing / operating procedure) show a
// readable, scrollable excerpt of the actual source procedure content. This is
// the "source input + its analysis" view: the source lives here; the generated
// analysis is the section content shown below. Accessible: labelled section
// heading, descriptive img alt text, and status shown as text alongside its
// icon.
// ---------------------------------------------------------------------------
function SourceInputsPanel({
  pcbaId,
  inputs,
}: {
  pcbaId: string;
  inputs: TpiInput[];
}) {
  // Render whenever there is at least one input of ANY type (only bail out on
  // an empty list) — the panel must show text procedures too, not just visuals.
  if (inputs.length === 0) return null;

  // Order logically: text procedures first, then visual inputs; anything with
  // an unknown type falls to the end but is still shown (never dropped).
  const orderedInputs = [...inputs].sort((a, b) => {
    const ai = SOURCE_INPUT_ORDER.indexOf(a.input_type);
    const bi = SOURCE_INPUT_ORDER.indexOf(b.input_type);
    return (ai === -1 ? Number.MAX_SAFE_INTEGER : ai) -
      (bi === -1 ? Number.MAX_SAFE_INTEGER : bi);
  });

  return (
    <section aria-labelledby="tpi-source-inputs-heading" className="space-y-4">
      <h3
        id="tpi-source-inputs-heading"
        className="text-sm font-semibold uppercase tracking-wide text-slate-700"
      >
        Source inputs
      </h3>
      <div className="grid gap-4 grid-cols-1 sm:grid-cols-2 xl:grid-cols-4">
        {orderedInputs.map((input) => {
          const typeLabel =
            INPUT_TYPE_LABELS[input.input_type] ?? input.input_type;
          const statusMeta = INPUT_STATUS_META[input.status];
          const isVisual =
            input.input_type === "circuit_diagram" ||
            input.input_type === "drawing";
          return (
            <Card key={input.id} className="overflow-hidden rounded-xl border border-slate-200 shadow-sm p-0">
              <div className="flex items-center justify-between gap-2 border-b border-slate-100 px-4 py-2.5">
                <span className="text-base font-semibold text-slate-900">
                  {typeLabel}
                </span>
                <div className="flex items-center gap-2">
                  {input.detected_format ? (
                    <Badge
                      variant="outline"
                      className="text-[10px] uppercase text-slate-600 border-slate-300"
                    >
                      {input.detected_format}
                    </Badge>
                  ) : null}
                  {statusMeta ? (
                    <span
                      className={`inline-flex items-center gap-1 text-xs font-medium ${statusMeta.className}`}
                    >
                      <statusMeta.Icon className="size-3.5" aria-hidden />
                      {statusMeta.label}
                    </span>
                  ) : null}
                </div>
              </div>
              {isVisual ? (
                input.preview_url ? (
                  <div className="bg-slate-50 p-3">
                    <img
                      src={input.preview_url}
                      alt={`${typeLabel} for ${pcbaId}`}
                      className="mx-auto max-h-72 w-auto rounded border border-slate-200 bg-white"
                    />
                  </div>
                ) : (
                  <div className="px-4 py-6 text-center text-sm text-slate-500">
                    No image preview — text stand-in or non-image format.
                  </div>
                )
              ) : input.text_excerpt ? (
                <div className="bg-slate-50 p-3">
                  <div
                    className="max-h-72 overflow-auto rounded border border-slate-200 bg-white p-4 text-sm leading-relaxed text-slate-800 whitespace-pre-wrap"
                    aria-label={`${typeLabel} excerpt for ${pcbaId}`}
                  >
                    {input.text_excerpt}
                  </div>
                </div>
              ) : (
                <div className="px-4 py-6 text-center text-sm text-slate-500">
                  No preview available.
                </div>
              )}
              <p className="truncate px-4 py-2 font-mono text-xs text-slate-500">
                {input.filename}
              </p>
            </Card>
          );
        })}
      </div>
    </section>
  );
}

// ---------------------------------------------------------------------------
// SectionEditor — one editable TPI section with provenance + incomplete marker.
//
// The section shows its title, an [INCOMPLETE — pending manual annotation]
// marker when applicable (Req 3.4), the source-input provenance (Req 3.3), and
// an inline textarea for the content. Per-section Save (commit locally) and
// Discard (revert to the fetched draft) actions surface only when the draft
// value has been changed (Req 6.6). Editing is staged in the parent's `edited`
// map; "Save" here simply blurs/keeps the staged value, while "Discard" reverts
// it to the original.
// ---------------------------------------------------------------------------

function SectionEditor({
  section,
  value,
  onChange,
  onDiscard,
}: {
  section: TpiSection;
  value: string;
  onChange: (content: string) => void;
  onDiscard: () => void;
}) {
  // Local draft text so "Save" can commit and "Discard" can revert cleanly. It
  // is seeded from the committed value and re-synced when that value changes
  // (e.g. after a discard from the parent).
  const [local, setLocal] = useState(value);
  useEffect(() => {
    setLocal(value);
  }, [value]);

  const dirtyVsCommitted = local !== value;
  const changedVsDraft = value !== section.content;

  return (
    <Card className="rounded-xl border border-slate-200 shadow-sm p-5 space-y-3">
      {/* Section header */}
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <h4 className="text-base font-semibold text-slate-900">
            {section.title}
          </h4>
          <p className="mt-0.5 font-mono text-xs text-slate-500">
            {section.key}
          </p>
        </div>
        {section.incomplete ? (
          <Badge variant="destructive" className="shrink-0 text-[11px]">
            <AlertTriangle className="size-3" aria-hidden />
            Incomplete — pending manual annotation
          </Badge>
        ) : null}
      </div>

      {/* Provenance (Req 3.3) — the source-input count is the provenance signal
          a reviewer needs; the raw uuids read as debug output, so we omit them. */}
      <div className="flex flex-wrap items-center gap-2">
        <span className="inline-flex items-center gap-1 text-sm text-slate-600">
          <Link2 className="size-3.5" aria-hidden />
          {section.source_input_ids.length > 0
            ? `Derived from ${section.source_input_ids.length} source ${
                section.source_input_ids.length === 1 ? "input" : "inputs"
              }`
            : "No linked source inputs"}
        </span>
      </div>

      {/* Inline editable content (Req 6.6) */}
      <div className="space-y-2">
        <Label htmlFor={`section-${section.key}`} className="sr-only">
          {section.title} content
        </Label>
        <textarea
          id={`section-${section.key}`}
          value={local}
          onChange={(e) => setLocal(e.target.value)}
          rows={Math.min(12, Math.max(4, local.split("\n").length + 1))}
          className="flex w-full rounded-lg border border-input bg-transparent px-3 py-2 text-[15px] leading-relaxed text-slate-900 placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 outline-none resize-y"
        />
      </div>

      {/* Per-section save / discard (Req 6.6) */}
      <div className="flex items-center justify-between gap-2">
        {/* Meaningful edit-state text — slate-600 meets WCAG AA (Req 7.3). */}
        <span className="text-xs text-slate-600">
          {changedVsDraft ? "Edited from the generated draft" : "Unchanged"}
        </span>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="sm"
            onClick={() => {
              setLocal(section.content);
              onDiscard();
            }}
            disabled={!changedVsDraft && !dirtyVsCommitted}
          >
            <Undo2 className="mr-1 size-3.5" aria-hidden />
            Discard
          </Button>
          <Button
            size="sm"
            onClick={() => onChange(local)}
            disabled={!dirtyVsCommitted}
          >
            Save
          </Button>
        </div>
      </div>
    </Card>
  );
}
