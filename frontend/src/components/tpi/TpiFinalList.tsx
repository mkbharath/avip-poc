import { useCallback, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Cpu,
  Download,
  FileCheck2,
  FileText,
  Info,
  Loader2,
  RotateCcw,
} from "lucide-react";
import { exportFinalUrl, listFinal } from "../../api/tpi";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import type { DraftTpi, TpiSection } from "../../types";

// ---------------------------------------------------------------------------
// Template-kind badge presentation (Req 5.2 vs 5.3, [CONFIRM] client template)
//
// The template is either the client's confirmed template or the documented
// placeholder used until that template is provided. We surface which one an
// export was rendered from — placeholder is called out so it is never mistaken
// for the confirmed client format.
// ---------------------------------------------------------------------------
const PLACEHOLDER_TEMPLATE_KINDS = new Set(["placeholder", "default"]);

function TemplateKindBadge({ kind }: { kind: string }) {
  const isPlaceholder = PLACEHOLDER_TEMPLATE_KINDS.has(kind.toLowerCase());
  return (
    <Badge
      variant="outline"
      className={
        isPlaceholder
          ? "gap-1 border-amber-300 bg-amber-50 font-semibold text-amber-800"
          : "gap-1 border-indigo-300 bg-indigo-50 font-semibold text-indigo-800"
      }
    >
      <FileText className="size-3" aria-hidden="true" />
      <span className="capitalize">{kind}</span> template
    </Badge>
  );
}

// Count the sections still marked incomplete (derived from flagged inputs,
// Req 3.4). These are surfaced on the card and tagged in the preview so a
// finalized-but-incomplete TPI is never silently presented as complete.
function incompleteCount(tpi: DraftTpi): number {
  return tpi.sections.filter((s) => s.incomplete).length;
}

export function TpiFinalList() {
  const {
    data: finals,
    isLoading,
    isError,
    refetch,
  } = useQuery({
    queryKey: ["tpi", "final"],
    queryFn: listFinal,
  });

  // Which finalized TPIs are expanded to show the inline section preview.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());
  const toggleExpanded = useCallback((pcbaId: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(pcbaId)) next.delete(pcbaId);
      else next.add(pcbaId);
      return next;
    });
  }, []);

  const rows = finals ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">
            Final TPIs
          </h1>
          <p className="mt-0.5 text-sm text-slate-600">
            Reviewed-and-finalized Test Procedure Instructions, ready to preview
            and export
            {" · "}
            {rows.length} finalized
          </p>
        </div>
      </div>

      {/* Conditional side-by-side affordance — pending the [CONFIRM] item */}
      <ReferenceComparisonPanel />

      {/* Finalized-TPI list — loading / error / empty / data */}
      {isLoading ? (
        <LoadingState />
      ) : isError ? (
        <ErrorState onRetry={() => refetch()} />
      ) : rows.length === 0 ? (
        <EmptyState />
      ) : (
        <div className="space-y-3">
          {rows.map((tpi) => (
            <FinalTpiCard
              key={tpi.pcba_id}
              tpi={tpi}
              expanded={expanded.has(tpi.pcba_id)}
              onToggle={() => toggleExpanded(tpi.pcba_id)}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// Per-finalized-TPI card: summary row + expandable read-only preview
// ---------------------------------------------------------------------------
function FinalTpiCard({
  tpi,
  expanded,
  onToggle,
}: {
  tpi: DraftTpi;
  expanded: boolean;
  onToggle: () => void;
}) {
  const sectionCount = tpi.sections.length;
  const incomplete = incompleteCount(tpi);

  return (
    <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
      <div className="flex flex-wrap items-center gap-3 px-4 py-3.5">
        {/* Expand / collapse the inline preview */}
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={expanded}
          aria-label={
            expanded
              ? `Hide preview for ${tpi.pcba_id}`
              : `Preview ${tpi.pcba_id}`
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
          <p className="flex items-center gap-1.5 truncate font-mono text-base font-semibold text-slate-900">
            <FileCheck2 className="size-4 shrink-0 text-emerald-600" aria-hidden="true" />
            {tpi.pcba_id}
          </p>
          <p className="mt-0.5 flex items-center gap-1.5 text-xs text-slate-500">
            <Cpu className="size-3.5 text-slate-500" aria-hidden="true" />
            Generated via{" "}
            <span className="font-medium text-slate-700">{tpi.provider}</span>
            {" · "}
            {sectionCount} section{sectionCount === 1 ? "" : "s"}
          </p>
        </div>

        <TemplateKindBadge kind={tpi.template_kind} />

        {incomplete > 0 ? (
          <Badge
            variant="outline"
            className="gap-1 border-amber-300 bg-amber-50 font-semibold text-amber-800"
          >
            <AlertTriangle className="size-3" aria-hidden="true" />
            {incomplete} incomplete
          </Badge>
        ) : null}

        {/* Export / download the finalized-TPI PDF. Mirrors the source-comparison
            CSV export: a plain anchor to the /api/v1 export URL (no blob fetch),
            which is the simplest reliable download (Req 6.12, 5.1). */}
        <Button
          variant="default"
          size="sm"
          render={
            <a
              href={exportFinalUrl(tpi.pcba_id)}
              download
              title={`Download the finalized TPI for ${tpi.pcba_id} (PDF)`}
            />
          }
        >
          <Download className="mr-1.5" aria-hidden="true" />
          Download PDF
        </Button>
      </div>

      {expanded ? <TpiPreview tpi={tpi} /> : null}
    </Card>
  );
}

// A clean, read-only preview of the finalized TPI's sections (Req 6.12): each
// section's title and content, with an [INCOMPLETE] tag on sections still
// derived from flagged inputs so they stay visible rather than hidden.
function TpiPreview({ tpi }: { tpi: DraftTpi }) {
  if (tpi.sections.length === 0) {
    return (
      <div className="border-t border-slate-100 bg-slate-50/60 px-4 py-4 text-sm text-slate-500">
        This finalized TPI has no sections to preview.
      </div>
    );
  }

  return (
    <div className="space-y-3 border-t border-slate-100 bg-slate-50/60 px-4 py-4">
      <p className="text-xs font-semibold uppercase tracking-wide text-slate-600">
        Preview
      </p>
      <ol className="space-y-3">
        {tpi.sections.map((section, index) => (
          <PreviewSection key={section.key} index={index + 1} section={section} />
        ))}
      </ol>
    </div>
  );
}

function PreviewSection({
  index,
  section,
}: {
  index: number;
  section: TpiSection;
}) {
  return (
    <li className="rounded-lg border border-slate-200 bg-white px-4 py-3">
      <div className="flex flex-wrap items-center gap-2">
        <h4 className="text-base font-semibold text-slate-900">
          {index}. {section.title}
        </h4>
        {section.incomplete ? (
          <Badge
            variant="outline"
            className="gap-1 border-amber-300 bg-amber-50 text-[10px] font-semibold uppercase tracking-wide text-amber-800"
          >
            <AlertTriangle className="size-3" aria-hidden="true" />
            Incomplete
          </Badge>
        ) : null}
      </div>
      {section.content.trim() ? (
        <p className="mt-1.5 whitespace-pre-wrap text-sm leading-relaxed text-slate-800">
          {section.content}
        </p>
      ) : (
        <p className="mt-1.5 text-sm italic text-slate-500">
          No content recorded for this section.
        </p>
      )}
    </li>
  );
}

// ---------------------------------------------------------------------------
// Conditional side-by-side comparison (Req 10.3, [CONFIRM])
//
// A side-by-side comparison against an existing human-authored TPI depends on
// the [CONFIRM] item "human-authored TPI availability", which is NOT available.
// Rather than fake a comparison, we surface a clearly-labelled pending panel so
// the affordance is honest and traceable to the open item.
// ---------------------------------------------------------------------------
function ReferenceComparisonPanel() {
  return (
    <div className="rounded-lg border border-slate-200 bg-slate-50 px-4 py-3">
      <div className="flex items-start gap-3">
        <Info className="mt-0.5 size-5 shrink-0 text-slate-400" aria-hidden="true" />
        <div className="min-w-0 flex-1 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-base font-semibold text-slate-800">
              Side-by-side vs. human-authored TPI
            </p>
            <Badge
              variant="outline"
              className="border-amber-300 bg-amber-100 font-semibold text-amber-900"
            >
              CONFIRM
            </Badge>
            <Badge
              variant="outline"
              className="border-slate-300 bg-white text-[10px] uppercase tracking-wide text-slate-500"
            >
              Pending
            </Badge>
          </div>
          <p className="text-sm text-slate-600">
            Comparing a generated-and-reviewed TPI side by side with an existing
            human-authored reference depends on the client providing at least one
            reference TPI. That item is still pending confirmation, so no
            comparison is shown — this is surfaced rather than silently assumed.
            Once a reference TPI is available, the side-by-side view will be
            enabled here.
          </p>
        </div>
        <Button variant="outline" size="sm" disabled title="Pending client-provided reference TPIs">
          Compare
        </Button>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// Loading / error / empty states (Req 6.2, 6.3, 6.4 baseline)
// ---------------------------------------------------------------------------
function LoadingState() {
  return (
    <div className="flex items-center justify-center py-20">
      <Loader2 className="size-8 animate-spin text-lam-navy" aria-hidden="true" />
      <span className="sr-only">Loading finalized TPIs…</span>
    </div>
  );
}

function ErrorState({ onRetry }: { onRetry: () => void }) {
  return (
    <div className="py-20 text-center">
      <AlertTriangle
        className="mx-auto mb-4 size-16 text-muted-foreground/30"
        aria-hidden="true"
      />
      <h3 className="text-lg font-medium text-muted-foreground">
        We couldn't load the finalized TPIs
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

function EmptyState() {
  return (
    <div className="py-20 text-center">
      <FileCheck2
        className="mx-auto mb-4 size-16 text-muted-foreground/30"
        aria-hidden="true"
      />
      <h3 className="text-lg font-medium text-muted-foreground">
        No finalized TPIs yet
      </h3>
      <p className="mx-auto mt-1 max-w-md text-sm text-muted-foreground/70">
        No finalized TPIs yet — finalize a reviewed draft to see it here.
      </p>
    </div>
  );
}
