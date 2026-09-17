import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  ArrowUpRight,
  FileText,
  Inbox,
  Loader2,
} from "lucide-react";
import { listDrafts } from "../../api/tpi";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import type { DraftTpi } from "../../types";

// ---------------------------------------------------------------------------
// TpiReviewList — the /tpi/review queue.
//
// Lists the drafts awaiting review (review_state === "drafted") as a card feed.
// Each card summarizes a draft (PCBA id, template kind, provider, section count,
// and how many sections are still incomplete) and links to the deep-linkable
// per-PCBA workbench at /tpi/review/{pcba_id} (Req 6.10). Loading, error, and
// empty states use the shared UI, mirroring the source-comparison views.
// ---------------------------------------------------------------------------

export function TpiReviewList() {
  const {
    data: drafts = [],
    isLoading,
    isError,
    refetch,
    isFetching,
  } = useQuery({
    queryKey: ["tpi", "drafts", "drafted"],
    queryFn: () => listDrafts("drafted"),
  });

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold tracking-tight text-foreground">
            TPI Review
          </h1>
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-slate-900">{drafts.length}</span>{" "}
            {drafts.length === 1 ? "draft" : "drafts"} awaiting review
          </p>
        </div>
      </div>

      {/* Body (own scroll) */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-lam-navy" aria-hidden />
            <span className="sr-only">Loading drafts…</span>
          </div>
        ) : isError ? (
          <ErrorState onRetry={() => refetch()} isRetrying={isFetching} />
        ) : drafts.length === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto w-full max-w-7xl p-5 sm:p-6">
            <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
              {drafts.map((draft) => (
                <DraftCard key={draft.pcba_id} draft={draft} />
              ))}
            </div>
          </div>
        )}
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// DraftCard — one card summarizing a draft awaiting review.
// ---------------------------------------------------------------------------

function DraftCard({ draft }: { draft: DraftTpi }) {
  const sectionCount = draft.sections.length;
  const incompleteCount = draft.sections.filter((s) => s.incomplete).length;

  return (
    <div className="group flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md">
      <div className="flex flex-1 flex-col gap-4 p-5">
        {/* Header */}
        <div className="min-w-0">
          <div className="flex items-center gap-2">
            <FileText className="size-4 shrink-0 text-slate-500" aria-hidden />
            <p className="truncate font-mono text-base font-semibold text-slate-900">
              {draft.pcba_id}
            </p>
          </div>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <Badge variant="secondary" className="text-xs">
              {draft.template_kind === "client"
                ? "Client template"
                : "Placeholder template"}
            </Badge>
            <Badge variant="outline" className="text-xs text-slate-700 border-slate-300">
              {draft.provider}
            </Badge>
          </div>
        </div>

        {/* Section summary */}
        <div className="flex items-center gap-4 text-sm text-slate-600">
          <span>
            <span className="font-semibold text-slate-900">{sectionCount}</span>{" "}
            {sectionCount === 1 ? "section" : "sections"}
          </span>
          {incompleteCount > 0 ? (
            <span className="inline-flex items-center gap-1 font-medium text-avip-review">
              <AlertTriangle className="size-3.5" aria-hidden />
              {incompleteCount} incomplete
            </span>
          ) : (
            // Meaningful status text — slate-600 meets WCAG AA (Req 7.3).
            <span className="text-slate-600">All sections drafted</span>
          )}
        </div>

        {/* Footer action */}
        <div className="mt-auto pt-1">
          <Button
            size="sm"
            className="w-full"
            render={<Link to={`/tpi/review/${draft.pcba_id}`} />}
          >
            Open
            <ArrowUpRight className="ml-1 size-4" aria-hidden />
          </Button>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ErrorState — non-technical error with a retry affordance (Req 6.3).
// ---------------------------------------------------------------------------

function ErrorState({
  onRetry,
  isRetrying,
}: {
  onRetry: () => void;
  isRetrying: boolean;
}) {
  return (
    <div className="px-6 py-24 text-center">
      <AlertTriangle className="mx-auto mb-3 size-12 text-destructive/60" aria-hidden />
      <h3 className="text-base font-semibold text-slate-700">
        Could not load drafts
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Something went wrong while fetching drafts awaiting review.
      </p>
      <Button
        variant="outline"
        size="sm"
        className="mt-4"
        onClick={onRetry}
        disabled={isRetrying}
      >
        {isRetrying ? (
          <Loader2 className="mr-1.5 size-4 animate-spin" aria-hidden />
        ) : null}
        Retry
      </Button>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState — explains what to do next when nothing is awaiting review.
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="px-6 py-24 text-center">
      <Inbox className="mx-auto mb-3 size-12 text-slate-300" aria-hidden />
      <h3 className="text-base font-semibold text-slate-700">
        No drafts awaiting review
      </h3>
      <p className="mt-1 text-sm text-slate-500">
        Process a PCBA from the TPI Monitor to generate a draft, and it will
        appear here for review.
      </p>
    </div>
  );
}
