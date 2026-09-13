import { useCallback, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  ArrowUpRight,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
  MessageSquarePlus,
  ThumbsDown,
  ThumbsUp,
} from "lucide-react";
import { decideDiscrepancy, getReviewQueue } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { SCDiscrepancy } from "../../types";
import { cardAccent, computeHeadline, SpotlightValues } from "./table-parts";

const PAGE_SIZE = 50;
const DEFAULT_REVIEWER = "IQA Inspector";

type Decision = "confirmed" | "dismissed";

// ---------------------------------------------------------------------------
// SourceComparisonReview — an attractive CARD FEED review surface.
//
// The FLAT per-discrepancy queue (getReviewQueue) drives a responsive grid of
// cards, one card per pending difference. Each card leads with a plain-language
// HEADLINE describing the difference in human terms, a colored accent bar tinted
// by how the difference was detected, and a spotlighted "odd one out" value so
// the reviewer instantly sees which source disagrees. Two plain-language actions
// ("Looks wrong" / "Not an issue") decide the card; on success the ["sc"] query
// key is invalidated and the card drops out.
//
// Pagination is per DISCREPANCY (total_count is the number of discrepancies).
// Presentation + API wiring only — all comparison logic is reused from
// ./table-parts and the existing source-comparison API module.
// ---------------------------------------------------------------------------

export function SourceComparisonReview() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);

  const { data, isLoading } = useQuery({
    queryKey: ["sc", "review-queue", page],
    queryFn: () => getReviewQueue({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: 5_000,
    placeholderData: keepPreviousData,
  });

  const items = useMemo(() => data?.data ?? [], [data]);
  const totalCount = data?.total_count ?? 0;
  const rangeStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + items.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * PAGE_SIZE < totalCount;

  const effectiveReviewer = useCallback(
    () => reviewer.trim() || DEFAULT_REVIEWER,
    [reviewer]
  );

  const decideMutation = useMutation({
    mutationFn: ({
      id,
      decision,
      note,
    }: {
      id: string;
      decision: Decision;
      note?: string;
    }) =>
      decideDiscrepancy(id, {
        decision,
        reviewer: effectiveReviewer(),
        note: note?.trim() ? note.trim() : undefined,
      }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["sc"] }),
  });

  // Track which card is mid-decision so only that card shows a spinner.
  const pendingId =
    decideMutation.isPending && decideMutation.variables
      ? decideMutation.variables.id
      : null;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden bg-slate-50">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold tracking-tight text-foreground">
            Source Comparison Review
          </h1>
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-slate-900">{totalCount}</span>{" "}
            pending {totalCount === 1 ? "difference" : "differences"} to review
          </p>
        </div>
        <label className="flex shrink-0 items-center gap-2">
          <span className="text-xs font-medium text-slate-600">Reviewer</span>
          <Input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            className="h-8 w-44 text-sm"
            aria-label="Reviewer name"
          />
        </label>
      </div>

      {/* Card feed (own scroll) */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-lam-navy" />
          </div>
        ) : totalCount === 0 ? (
          <EmptyState />
        ) : (
          <div className="mx-auto w-full max-w-7xl p-5 sm:p-6">
            <div className="grid gap-5 lg:grid-cols-2 2xl:grid-cols-3">
              {items.map((item) => (
                <DiscrepancyCard
                  key={item.id}
                  item={item}
                  onDecide={(decision, note) =>
                    decideMutation.mutate({ id: item.id, decision, note })
                  }
                  isPending={pendingId === item.id}
                />
              ))}
            </div>
          </div>
        )}
      </div>

      {/* Pagination footer */}
      <PaginationFooter
        rangeStart={rangeStart}
        rangeEnd={rangeEnd}
        totalCount={totalCount}
        canPrev={canPrev}
        canNext={canNext}
        onPrev={() => setPage((p) => Math.max(0, p - 1))}
        onNext={() => setPage((p) => p + 1)}
      />
    </div>
  );
}

// ---------------------------------------------------------------------------
// DiscrepancyCard — one attractive card for a single pending difference.
//
// Anatomy (top -> bottom):
//   1. Thin colored ACCENT BAR tinted by detection type.
//   2. HEADER: muted part · lot line + bold plain-language HEADLINE + a tiny
//      quiet "how detected" tag.
//   3. BODY: spotlighted odd value(s) with the agreeing / reference values
//      shown small and muted.
//   4. FOOTER: "Looks wrong" (confirm, green) + "Not an issue" (dismiss,
//      outline), an unobtrusive "add note" toggle, and a ghost Details link.
// ---------------------------------------------------------------------------

function DiscrepancyCard({
  item,
  onDecide,
  isPending,
}: {
  item: SCDiscrepancy;
  onDecide: (decision: Decision, note?: string) => void;
  isPending: boolean;
}) {
  const [noteOpen, setNoteOpen] = useState(false);
  const [note, setNote] = useState("");

  const accent = cardAccent(item.provenance);
  const headline = computeHeadline(item);

  return (
    <div className="group flex flex-col overflow-hidden rounded-2xl border border-slate-200 bg-white shadow-sm transition-shadow duration-200 hover:shadow-md">
      {/* 1. Accent bar */}
      <div className={cn("h-1 w-full", accent.bar)} />

      <div className="flex flex-1 flex-col gap-4 p-5">
        {/* 2. Header */}
        <div className="min-w-0">
          <div className="flex items-center gap-2 text-[11px] font-medium text-slate-400">
            <span className="truncate font-mono">
              {item.part_number} · Lot {item.lot_number}
            </span>
          </div>
          <h3 className="mt-1 text-base font-semibold leading-snug text-slate-900">
            {headline}
          </h3>
          <span
            className={cn(
              "mt-1 inline-block text-[11px] font-medium",
              accent.tagText
            )}
          >
            {accent.detectLabel}
          </span>
        </div>

        {/* 3. Spotlighted values */}
        <SpotlightValues values={item.values} fieldType={item.field_type} />

        {/* Optional note input */}
        {noteOpen && (
          <Input
            autoFocus
            value={note}
            onChange={(e) => setNote(e.target.value)}
            placeholder="Add an optional note…"
            className="h-8 text-sm"
            aria-label="Optional reviewer note"
          />
        )}

        {/* 4. Footer actions */}
        <div className="mt-auto flex items-center gap-2 pt-1">
          <Button
            size="sm"
            className="h-9 flex-1 bg-avip-pass text-white hover:bg-avip-pass/90"
            onClick={() => onDecide("confirmed", note)}
            disabled={isPending}
          >
            {isPending ? (
              <Loader2 className="mr-1.5 size-4 animate-spin" />
            ) : (
              <ThumbsUp className="mr-1.5 size-4" />
            )}
            Looks wrong
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-9 flex-1"
            onClick={() => onDecide("dismissed", note)}
            disabled={isPending}
          >
            <ThumbsDown className="mr-1.5 size-4" />
            Not an issue
          </Button>
        </div>

        {/* Unobtrusive: add-note toggle + Details link */}
        <div className="flex items-center justify-between text-xs">
          <button
            type="button"
            onClick={() => setNoteOpen((o) => !o)}
            className="inline-flex items-center gap-1 text-slate-400 transition-colors hover:text-slate-600"
          >
            <MessageSquarePlus className="size-3.5" />
            {noteOpen ? "Hide note" : "Add note"}
          </button>
          <Link
            to={`/source-comparison/review/${item.id}`}
            className="inline-flex items-center gap-0.5 text-slate-400 opacity-0 transition-opacity hover:text-slate-600 group-hover:opacity-100"
          >
            Details
            <ArrowUpRight className="size-3.5" />
          </Link>
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// EmptyState — friendly "all caught up" panel.
// ---------------------------------------------------------------------------

function EmptyState() {
  return (
    <div className="px-6 py-24 text-center">
      <CheckCircle2 className="mx-auto mb-3 size-12 text-avip-pass/70" />
      <h3 className="text-base font-semibold text-slate-700">
        All caught up — no differences to review
      </h3>
      <p className="mt-1 text-sm text-slate-400">
        New differences will appear here automatically as they are flagged.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// PaginationFooter — Prev / Next + range readout.
// ---------------------------------------------------------------------------

function PaginationFooter({
  rangeStart,
  rangeEnd,
  totalCount,
  canPrev,
  canNext,
  onPrev,
  onNext,
}: {
  rangeStart: number;
  rangeEnd: number;
  totalCount: number;
  canPrev: boolean;
  canNext: boolean;
  onPrev: () => void;
  onNext: () => void;
}) {
  return (
    <div className="flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-4 py-2.5">
      <p className="text-[11px] text-slate-600">
        Showing{" "}
        <span className="font-semibold text-slate-900">{rangeStart}</span>–
        <span className="font-semibold text-slate-900">{rangeEnd}</span> of{" "}
        <span className="font-semibold text-slate-900">{totalCount}</span>
      </p>
      <div className="flex items-center gap-1.5">
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-2"
          disabled={!canPrev}
          onClick={onPrev}
        >
          <ChevronLeft className="size-4" />
          Prev
        </Button>
        <Button
          variant="outline"
          size="sm"
          className="h-7 px-2"
          disabled={!canNext}
          onClick={onNext}
        >
          Next
          <ChevronRight className="size-4" />
        </Button>
      </div>
    </div>
  );
}
