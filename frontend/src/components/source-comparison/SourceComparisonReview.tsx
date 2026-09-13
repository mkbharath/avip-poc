import { useCallback, useEffect, useMemo, useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Keyboard,
  Loader2,
} from "lucide-react";
import {
  decideBulk,
  decideDiscrepancy,
  getReviewQueue,
} from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { SCDiscrepancy, SCReviewState } from "../../types";
import {
  FieldLabel,
  PartLotCell,
  ProvenancePill,
  SourceValueCompareCard,
} from "./table-parts";

const PAGE_SIZE = 50;
const DEFAULT_REVIEWER = "IQA Inspector";

// ---------------------------------------------------------------------------
// SourceComparisonReview — a master/detail split-view review workbench.
//
// LEFT pane: a compact, scrollable queue of pending discrepancies with a
// per-page "select all" + a bulk action bar. Clicking a row makes it the
// "active" item shown in the detail pane; the checkbox toggles bulk selection.
//
// RIGHT pane: the full detail for the active item with a note field and
// Confirm / Dismiss actions. Deciding auto-advances to the next queue item.
//
// Keyboard quick-decide (when focus is not in an input): c confirm, d dismiss,
// j / ArrowDown next, k / ArrowUp previous, x toggle bulk-select.
//
// Presentation + API wiring only — all comparison logic is reused from
// ./table-parts and the existing source-comparison API module.
// ---------------------------------------------------------------------------

export function SourceComparisonReview() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  const [selectedIds, setSelectedIds] = useState<Set<string>>(new Set());
  const [activeId, setActiveId] = useState<string | null>(null);
  const [note, setNote] = useState("");

  const { data, isLoading } = useQuery({
    queryKey: ["sc", "review-queue", page],
    queryFn: () => getReviewQueue({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: 5_000,
    placeholderData: keepPreviousData,
  });

  const queue = useMemo(() => data?.data ?? [], [data]);
  const totalCount = data?.total_count ?? 0;
  const rangeStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + queue.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * PAGE_SIZE < totalCount;

  const activeIndex = activeId
    ? queue.findIndex((item) => item.id === activeId)
    : -1;
  const activeItem = activeIndex >= 0 ? queue[activeIndex] : null;

  // Keep activeId valid as the queue refetches. If the active item was decided
  // (dropped out of the queue), advance to the item now occupying its slot, or
  // fall back to the last item / clear when the page empties.
  useEffect(() => {
    if (queue.length === 0) {
      if (activeId !== null) setActiveId(null);
      return;
    }
    if (activeId && queue.some((item) => item.id === activeId)) return;

    // The previous active item is gone. Prefer the item at the same index
    // (the next pending one), else the last item.
    const fallbackIndex =
      activeIndex >= 0 ? Math.min(activeIndex, queue.length - 1) : 0;
    const fallback = queue[fallbackIndex];
    setActiveId(fallback ? fallback.id : null);
    // We intentionally depend on `queue` identity (changes on refetch).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [queue]);

  // Reset transient editing state when the active item changes.
  useEffect(() => {
    setNote("");
  }, [activeId]);

  // Prune selected ids that are no longer on this page (e.g. after decide or
  // page change) so the bulk bar count stays honest.
  useEffect(() => {
    setSelectedIds((prev) => {
      if (prev.size === 0) return prev;
      const pageIds = new Set(queue.map((item) => item.id));
      const next = new Set([...prev].filter((id) => pageIds.has(id)));
      return next.size === prev.size ? prev : next;
    });
  }, [queue]);

  const invalidateQueue = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["sc"] });
  }, [queryClient]);

  // ---- Navigation helpers -------------------------------------------------

  const selectByIndex = useCallback(
    (index: number) => {
      if (index < 0 || index >= queue.length) return;
      setActiveId(queue[index].id);
    },
    [queue]
  );

  const advanceAfterDecide = useCallback(
    (decidedIndex: number) => {
      // After deciding, the item drops out; the next pending item slides into
      // this index. Point at that index (clamped), or clear if it was last.
      if (queue.length <= 1) {
        setActiveId(null);
        return;
      }
      const nextIndex = Math.min(decidedIndex, queue.length - 2);
      const candidate = queue.filter((item) => item.id !== queue[decidedIndex]?.id)[
        nextIndex
      ];
      setActiveId(candidate ? candidate.id : null);
    },
    [queue]
  );

  // ---- Single decision ----------------------------------------------------

  const decideMutation = useMutation({
    mutationFn: ({
      id,
      decision,
    }: {
      id: string;
      decision: "confirmed" | "dismissed";
    }) =>
      decideDiscrepancy(id, {
        decision,
        reviewer: reviewer.trim() || DEFAULT_REVIEWER,
        note: note.trim() || undefined,
      }),
    onSuccess: (_result, variables) => {
      const decidedIndex = queue.findIndex((item) => item.id === variables.id);
      // Drop the decided item from any bulk selection.
      setSelectedIds((prev) => {
        if (!prev.has(variables.id)) return prev;
        const next = new Set(prev);
        next.delete(variables.id);
        return next;
      });
      if (decidedIndex >= 0) advanceAfterDecide(decidedIndex);
      invalidateQueue();
    },
  });

  const decideActive = useCallback(
    (decision: "confirmed" | "dismissed") => {
      if (!activeItem || decideMutation.isPending) return;
      decideMutation.mutate({ id: activeItem.id, decision });
    },
    [activeItem, decideMutation]
  );

  // ---- Bulk decision ------------------------------------------------------

  const bulkMutation = useMutation({
    mutationFn: (decision: "confirmed" | "dismissed") =>
      decideBulk({
        discrepancy_ids: [...selectedIds],
        decision,
        reviewer: reviewer.trim() || DEFAULT_REVIEWER,
        note: note.trim() || undefined,
      }),
    onSuccess: () => {
      setSelectedIds(new Set());
      invalidateQueue();
    },
  });

  // ---- Selection helpers --------------------------------------------------

  const toggleSelect = useCallback((id: string) => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }, []);

  const pageIds = useMemo(() => queue.map((item) => item.id), [queue]);
  const allPageSelected =
    pageIds.length > 0 && pageIds.every((id) => selectedIds.has(id));
  const somePageSelected = pageIds.some((id) => selectedIds.has(id));

  const toggleSelectAllOnPage = useCallback(() => {
    setSelectedIds((prev) => {
      const next = new Set(prev);
      if (pageIds.every((id) => next.has(id))) {
        for (const id of pageIds) next.delete(id);
      } else {
        for (const id of pageIds) next.add(id);
      }
      return next;
    });
  }, [pageIds]);

  // ---- Keyboard quick-decide ---------------------------------------------

  useEffect(() => {
    function isTypingTarget(target: EventTarget | null): boolean {
      if (!(target instanceof HTMLElement)) return false;
      const tag = target.tagName;
      return tag === "INPUT" || tag === "TEXTAREA" || target.isContentEditable;
    }

    function onKeyDown(event: KeyboardEvent) {
      if (event.metaKey || event.ctrlKey || event.altKey) return;
      if (isTypingTarget(event.target)) return;
      if (queue.length === 0) return;

      const index = activeId
        ? queue.findIndex((item) => item.id === activeId)
        : -1;

      switch (event.key) {
        case "j":
        case "ArrowDown":
          event.preventDefault();
          selectByIndex(index < 0 ? 0 : Math.min(index + 1, queue.length - 1));
          break;
        case "k":
        case "ArrowUp":
          event.preventDefault();
          selectByIndex(index < 0 ? 0 : Math.max(index - 1, 0));
          break;
        case "c":
          if (activeId) {
            event.preventDefault();
            decideActive("confirmed");
          }
          break;
        case "d":
          if (activeId) {
            event.preventDefault();
            decideActive("dismissed");
          }
          break;
        case "x":
          if (activeId) {
            event.preventDefault();
            toggleSelect(activeId);
          }
          break;
        default:
          break;
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [queue, activeId, selectByIndex, decideActive, toggleSelect]);

  const bulkPending = bulkMutation.isPending;
  const selectedCount = selectedIds.size;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold tracking-tight text-foreground">
            Source Comparison Review
          </h1>
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-slate-900">{totalCount}</span>{" "}
            pending {totalCount === 1 ? "discrepancy" : "discrepancies"}
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-3">
          <ShortcutsHint />
          <label className="flex items-center gap-2">
            <span className="text-xs font-medium text-slate-600">Reviewer</span>
            <Input
              value={reviewer}
              onChange={(e) => setReviewer(e.target.value)}
              className="h-8 w-44 text-sm"
              aria-label="Reviewer name"
            />
          </label>
        </div>
      </div>

      {/* Split body */}
      <div className="flex min-h-0 flex-1">
        {/* LEFT — list pane */}
        <div className="flex w-[400px] shrink-0 flex-col border-r border-slate-200 bg-slate-50/50">
          {/* Select-all + bulk bar */}
          <div className="shrink-0 border-b border-slate-200 bg-white">
            <div className="flex items-center gap-2 px-4 py-2.5">
              <input
                type="checkbox"
                className="size-4 rounded border-slate-300 text-lam-navy focus:ring-2 focus:ring-lam-navy/40"
                checked={allPageSelected}
                ref={(el) => {
                  if (el) el.indeterminate = somePageSelected && !allPageSelected;
                }}
                onChange={toggleSelectAllOnPage}
                disabled={queue.length === 0}
                aria-label="Select all on this page"
              />
              <span className="text-xs font-medium text-slate-600">
                Select all on page
              </span>
            </div>

            {selectedCount > 0 && (
              <div className="flex items-center justify-between gap-2 border-t border-slate-200 bg-lam-navy/5 px-4 py-2">
                <span className="text-xs font-semibold text-slate-700">
                  {selectedCount} selected
                </span>
                <div className="flex items-center gap-2">
                  <Button
                    size="sm"
                    className="h-7 bg-avip-pass px-2.5 text-xs text-white hover:bg-avip-pass/90"
                    onClick={() => bulkMutation.mutate("confirmed")}
                    disabled={bulkPending}
                  >
                    {bulkPending ? (
                      <Loader2 className="mr-1 size-3.5 animate-spin" />
                    ) : null}
                    Confirm selected
                  </Button>
                  <Button
                    variant="outline"
                    size="sm"
                    className="h-7 px-2.5 text-xs"
                    onClick={() => bulkMutation.mutate("dismissed")}
                    disabled={bulkPending}
                  >
                    Dismiss selected
                  </Button>
                </div>
              </div>
            )}
          </div>

          {/* List (own scroll) */}
          <div className="min-h-0 flex-1 overflow-y-auto">
            {isLoading ? (
              <div className="flex items-center justify-center py-20">
                <Loader2 className="size-6 animate-spin text-lam-navy" />
              </div>
            ) : queue.length === 0 ? (
              <div className="px-6 py-16 text-center">
                <CheckCircle2 className="mx-auto mb-3 size-12 text-slate-300" />
                <h3 className="text-sm font-medium text-slate-600">
                  No pending discrepancies
                </h3>
                <p className="mt-1 text-xs text-slate-400">
                  All flagged discrepancies have been reviewed
                </p>
              </div>
            ) : (
              <ul className="divide-y divide-slate-100">
                {queue.map((item) => (
                  <QueueRow
                    key={item.id}
                    item={item}
                    active={item.id === activeId}
                    selected={selectedIds.has(item.id)}
                    onSelectRow={() => setActiveId(item.id)}
                    onToggle={() => toggleSelect(item.id)}
                  />
                ))}
              </ul>
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

        {/* RIGHT — detail pane (own scroll) */}
        <div className="min-w-0 flex-1 overflow-y-auto bg-white">
          {activeItem ? (
            <DetailPane
              item={activeItem}
              note={note}
              onNoteChange={setNote}
              onConfirm={() => decideActive("confirmed")}
              onDismiss={() => decideActive("dismissed")}
              isPending={decideMutation.isPending}
            />
          ) : (
            <EmptyDetail />
          )}
        </div>
      </div>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ShortcutsHint — a compact keyboard legend shown in the header.
// ---------------------------------------------------------------------------

function ShortcutsHint() {
  return (
    <div className="hidden items-center gap-1.5 rounded-md border border-slate-200 bg-slate-50 px-2.5 py-1 text-[11px] text-slate-500 lg:flex">
      <Keyboard className="size-3.5 text-slate-400" />
      <span>
        <Kbd>C</Kbd> confirm · <Kbd>D</Kbd> dismiss · <Kbd>J</Kbd>/<Kbd>K</Kbd>{" "}
        move · <Kbd>X</Kbd> select
      </span>
    </div>
  );
}

function Kbd({ children }: { children: React.ReactNode }) {
  return (
    <kbd className="rounded border border-slate-300 bg-white px-1 font-mono text-[10px] font-semibold text-slate-600">
      {children}
    </kbd>
  );
}

// ---------------------------------------------------------------------------
// QueueRow — a compact list item in the left pane.
// ---------------------------------------------------------------------------

function QueueRow({
  item,
  active,
  selected,
  onSelectRow,
  onToggle,
}: {
  item: SCDiscrepancy;
  active: boolean;
  selected: boolean;
  onSelectRow: () => void;
  onToggle: () => void;
}) {
  return (
    <li>
      <div
        role="button"
        tabIndex={0}
        onClick={onSelectRow}
        onKeyDown={(e) => {
          if (e.key === "Enter" || e.key === " ") {
            e.preventDefault();
            onSelectRow();
          }
        }}
        className={cn(
          "flex cursor-pointer items-start gap-3 border-l-2 px-4 py-3 outline-none transition-colors",
          "focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-lam-navy/40",
          active
            ? "border-l-lam-navy bg-slate-100"
            : "border-l-transparent hover:bg-slate-100/60"
        )}
      >
        <input
          type="checkbox"
          className="mt-0.5 size-4 shrink-0 rounded border-slate-300 text-lam-navy focus:ring-2 focus:ring-lam-navy/40"
          checked={selected}
          onChange={onToggle}
          onClick={(e) => e.stopPropagation()}
          aria-label={`Select ${item.part_number} ${item.field_name}`}
        />
        <div className="min-w-0 flex-1 space-y-1.5">
          <PartLotCell partNumber={item.part_number} lotNumber={item.lot_number} />
          <div className="truncate text-xs font-medium capitalize text-slate-700">
            {item.field_name.replace(/_/g, " ")}
          </div>
          <div>
            <ProvenancePill provenance={item.provenance} />
          </div>
        </div>
      </div>
    </li>
  );
}

// ---------------------------------------------------------------------------
// PaginationFooter — Prev / Next + range readout for the list pane.
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
    <div className="flex shrink-0 items-center justify-between border-t border-slate-200 bg-white px-3 py-2.5">
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

// ---------------------------------------------------------------------------
// EmptyDetail — right-pane placeholder when nothing is selected.
// ---------------------------------------------------------------------------

function EmptyDetail() {
  return (
    <div className="flex h-full flex-col items-center justify-center px-8 text-center">
      <div className="rounded-full bg-slate-100 p-4">
        <Keyboard className="size-8 text-slate-400" />
      </div>
      <h3 className="mt-4 text-base font-medium text-slate-700">
        Select a discrepancy to review
      </h3>
      <p className="mt-1 max-w-sm text-sm text-slate-500">
        Pick an item from the list, or use <Kbd>J</Kbd> / <Kbd>K</Kbd> to move
        through the queue. Press <Kbd>C</Kbd> to confirm, <Kbd>D</Kbd> to
        dismiss, and <Kbd>X</Kbd> to add it to a bulk selection.
      </p>
    </div>
  );
}

// ---------------------------------------------------------------------------
// ReviewStateBadge — small badge mirroring the workbench styling.
// ---------------------------------------------------------------------------

function ReviewStateBadge({ state }: { state: SCReviewState }) {
  return (
    <Badge
      variant={
        state === "confirmed"
          ? "destructive"
          : state === "dismissed"
            ? "outline"
            : "secondary"
      }
      className="text-xs capitalize"
    >
      {state}
    </Badge>
  );
}

// ---------------------------------------------------------------------------
// DetailPane — the full review surface for the active item.
// ---------------------------------------------------------------------------

function DetailPane({
  item,
  note,
  onNoteChange,
  onConfirm,
  onDismiss,
  isPending,
}: {
  item: SCDiscrepancy;
  note: string;
  onNoteChange: (value: string) => void;
  onConfirm: () => void;
  onDismiss: () => void;
  isPending: boolean;
}) {
  const needsManualComparison =
    item.provenance === "llm-unavailable" || item.provenance === "llm";
  const alreadyDecided = item.review_state !== "pending";

  return (
    <div className="mx-auto w-full max-w-3xl space-y-6 p-6">
      {/* Header: part/lot + provenance + state */}
      <div className="flex items-start justify-between gap-4">
        <PartLotCell partNumber={item.part_number} lotNumber={item.lot_number} />
        <div className="flex shrink-0 items-center gap-2">
          <ProvenancePill provenance={item.provenance} />
          <ReviewStateBadge state={item.review_state} />
        </div>
      </div>

      {/* Field name / type */}
      <FieldLabel name={item.field_name} type={item.field_type} />

      {/* Manual-comparison notice for LLM provenance */}
      {needsManualComparison && (
        <div className="flex items-start gap-3 rounded-lg border border-avip-review/40 bg-avip-review/5 px-4 py-3">
          <AlertTriangle className="mt-0.5 size-5 flex-shrink-0 text-avip-review" />
          <div className="text-sm text-slate-700">
            {item.provenance === "llm-unavailable" ? (
              <>
                <span className="font-semibold">
                  Automated comparison unavailable.
                </span>{" "}
                The LLM provider could not evaluate this free-text field, so it
                requires manual comparison. Review the source values below and
                decide.
              </>
            ) : (
              <>
                <span className="font-semibold">LLM-assisted flag.</span> This
                free-text field was flagged by the LLM check. Confirm the values
                genuinely differ before deciding.
              </>
            )}
          </div>
        </div>
      )}

      {/* Source values — full width, free-text fully readable in this pane */}
      <div>
        <h3 className="mb-3 text-[10px] font-semibold uppercase tracking-wider text-slate-600">
          Source Values
        </h3>
        <SourceValueCompareCard values={item.values} fieldType={item.field_type} />
      </div>

      {/* Decision panel */}
      <div className="space-y-3 rounded-xl border border-slate-200 bg-slate-50/70 p-4">
        <h3 className="text-sm font-semibold text-foreground">Review Decision</h3>

        {alreadyDecided ? (
          <p className="text-sm text-slate-700">
            This discrepancy has already been {item.review_state}
            {item.reviewer ? ` by ${item.reviewer}` : ""}
            {item.reviewer_note ? ` — "${item.reviewer_note}"` : ""}.
          </p>
        ) : (
          <>
            <div className="space-y-1.5">
              <label className="text-xs font-medium text-slate-600">
                Note <span className="font-normal text-slate-400">(optional)</span>
              </label>
              <textarea
                value={note}
                onChange={(e) => onNoteChange(e.target.value)}
                rows={2}
                placeholder="Add an optional note about this decision..."
                disabled={isPending}
                className="flex w-full resize-none rounded-lg border border-input bg-white px-3 py-2 text-sm outline-none placeholder:text-muted-foreground focus-visible:border-ring focus-visible:ring-3 focus-visible:ring-ring/50 disabled:opacity-60"
              />
            </div>

            <div className="flex gap-2 pt-1">
              <Button
                className="flex-1 bg-avip-pass text-white hover:bg-avip-pass/90"
                size="sm"
                onClick={onConfirm}
                disabled={isPending}
              >
                {isPending ? (
                  <Loader2 className="mr-1 size-3.5 animate-spin" />
                ) : null}
                Confirm
              </Button>
              <Button
                variant="outline"
                className="flex-1"
                size="sm"
                onClick={onDismiss}
                disabled={isPending}
              >
                Dismiss
              </Button>
            </div>
          </>
        )}
      </div>
    </div>
  );
}
