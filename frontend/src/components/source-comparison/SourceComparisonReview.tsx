import { useCallback, useMemo, useState } from "react";
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
  ChevronRight as ChevronToggle,
  Loader2,
} from "lucide-react";
import {
  decideBulk,
  decideDiscrepancy,
  getReviewQueueGrouped,
} from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { cn } from "@/lib/utils";
import type { SCDiscrepancy, SCGroup } from "../../types";
import {
  FieldLabel,
  ProvenancePill,
  ProvenancePillCount,
  SourceValueCompareCard,
} from "./table-parts";

const PAGE_SIZE = 50;
const DEFAULT_REVIEWER = "IQA Inspector";

type Decision = "confirmed" | "dismissed";

// A stable key for a part/lot group. Expand state is keyed by this so that
// open panels stay open across refetches (as long as the group still exists).
function groupKey(group: Pick<SCGroup, "part_number" | "lot_number">): string {
  return `${group.part_number}|${group.lot_number}`;
}

// ---------------------------------------------------------------------------
// SourceComparisonReview — an ACCORDION review surface grouped by part/lot.
//
// Each part/lot GROUP is a collapsible panel. The panel header shows the
// part/lot, a difference count, and per-provenance count chips, plus
// group-level "Confirm all" / "Dismiss all" bulk actions. Expanding a panel
// reveals every pending discrepancy in that group at full width, each with its
// own Confirm / Dismiss buttons.
//
// Pagination is by GROUP (total_count is the number of groups). Multiple panels
// may be open at once. After any decision, the ["sc"] query key is invalidated
// so groups and counts refetch; a group that empties out drops away.
//
// Presentation + API wiring only — all comparison rendering is reused from
// ./table-parts and the existing source-comparison API module.
// ---------------------------------------------------------------------------

export function SourceComparisonReview() {
  const queryClient = useQueryClient();
  const [page, setPage] = useState(0);
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  // Controlled expand state — a Set of "part|lot" keys. Multiple open allowed.
  const [expanded, setExpanded] = useState<Set<string>>(new Set());

  const { data, isLoading } = useQuery({
    queryKey: ["sc", "review-queue-grouped", page],
    queryFn: () =>
      getReviewQueueGrouped({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: 5_000,
    placeholderData: keepPreviousData,
  });

  const groups = useMemo(() => data?.data ?? [], [data]);
  const totalCount = data?.total_count ?? 0; // number of GROUPS
  const rangeStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + groups.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * PAGE_SIZE < totalCount;

  const effectiveReviewer = () => reviewer.trim() || DEFAULT_REVIEWER;

  const invalidateAll = useCallback(() => {
    queryClient.invalidateQueries({ queryKey: ["sc"] });
  }, [queryClient]);

  const toggleGroup = useCallback((key: string) => {
    setExpanded((prev) => {
      const next = new Set(prev);
      if (next.has(key)) next.delete(key);
      else next.add(key);
      return next;
    });
  }, []);

  // ---- Per-item decision --------------------------------------------------

  const decideMutation = useMutation({
    mutationFn: ({ id, decision }: { id: string; decision: Decision }) =>
      decideDiscrepancy(id, { decision, reviewer: effectiveReviewer() }),
    onSuccess: invalidateAll,
  });

  // ---- Group-level bulk decision ------------------------------------------

  const bulkMutation = useMutation({
    mutationFn: ({
      ids,
      decision,
    }: {
      ids: string[];
      decision: Decision;
      key: string;
    }) =>
      decideBulk({
        discrepancy_ids: ids,
        decision,
        reviewer: effectiveReviewer(),
      }),
    onSuccess: invalidateAll,
  });

  // Track which group is mid-bulk so we can disable just that group's buttons.
  const bulkPendingKey =
    bulkMutation.isPending && bulkMutation.variables
      ? bulkMutation.variables.key
      : null;

  return (
    <div className="flex h-[calc(100vh-3.5rem)] flex-col overflow-hidden bg-slate-50/50">
      {/* Header */}
      <div className="flex shrink-0 items-center justify-between gap-4 border-b border-slate-200 bg-white px-6 py-3">
        <div className="min-w-0">
          <h1 className="truncate text-lg font-bold tracking-tight text-foreground">
            Source Comparison Review
          </h1>
          <p className="text-sm text-muted-foreground">
            <span className="font-semibold text-slate-900">{totalCount}</span>{" "}
            part/lot {totalCount === 1 ? "group" : "groups"} with pending
            differences
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

      {/* Accordion body (own scroll) */}
      <div className="min-h-0 flex-1 overflow-y-auto">
        {isLoading ? (
          <div className="flex items-center justify-center py-24">
            <Loader2 className="size-6 animate-spin text-lam-navy" />
          </div>
        ) : totalCount === 0 ? (
          <div className="px-6 py-24 text-center">
            <CheckCircle2 className="mx-auto mb-3 size-12 text-slate-300" />
            <h3 className="text-sm font-medium text-slate-600">
              No pending discrepancies
            </h3>
            <p className="mt-1 text-xs text-slate-400">
              All flagged discrepancies have been reviewed
            </p>
          </div>
        ) : (
          <div className="mx-auto w-full max-w-5xl space-y-3 p-4 sm:p-6">
            {groups.map((group) => {
              const key = groupKey(group);
              return (
                <GroupPanel
                  key={key}
                  group={group}
                  open={expanded.has(key)}
                  onToggle={() => toggleGroup(key)}
                  onDecideItem={(id, decision) =>
                    decideMutation.mutate({ id, decision })
                  }
                  onBulk={(decision) =>
                    bulkMutation.mutate({
                      ids: group.discrepancies.map((d) => d.id),
                      decision,
                      key,
                    })
                  }
                  itemPending={decideMutation.isPending}
                  bulkPending={bulkPendingKey === key}
                />
              );
            })}
          </div>
        )}
      </div>

      {/* Pagination footer (by GROUP) */}
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
// GroupPanel — one collapsible accordion panel for a part/lot group.
// ---------------------------------------------------------------------------

function GroupPanel({
  group,
  open,
  onToggle,
  onDecideItem,
  onBulk,
  itemPending,
  bulkPending,
}: {
  group: SCGroup;
  open: boolean;
  onToggle: () => void;
  onDecideItem: (id: string, decision: Decision) => void;
  onBulk: (decision: Decision) => void;
  itemPending: boolean;
  bulkPending: boolean;
}) {
  const provenanceEntries = Object.entries(group.provenance_counts).filter(
    ([, count]) => count > 0
  );
  const panelId = `group-panel-${group.part_number}-${group.lot_number}`;

  return (
    <div className="overflow-hidden rounded-xl border border-slate-200 bg-white shadow-sm">
      {/* Trigger header */}
      <div
        className={cn(
          "flex items-center gap-3 px-4 py-3 transition-colors",
          open ? "bg-slate-50" : "bg-white hover:bg-slate-50/70"
        )}
      >
        <button
          type="button"
          onClick={onToggle}
          aria-expanded={open}
          aria-controls={panelId}
          className="flex min-w-0 flex-1 items-center gap-3 rounded-md text-left outline-none focus-visible:ring-2 focus-visible:ring-lam-navy/40"
        >
          <ChevronToggle
            className={cn(
              "size-4 shrink-0 text-slate-400 transition-transform duration-200",
              open && "rotate-90"
            )}
          />
          <div className="flex min-w-0 flex-col leading-tight">
            <span className="truncate font-mono text-sm font-bold text-slate-900">
              {group.part_number}
            </span>
            <span className="truncate font-mono text-xs text-slate-500">
              Lot {group.lot_number}
            </span>
          </div>
          <div className="ml-2 flex min-w-0 items-center gap-2">
            <span className="whitespace-nowrap rounded-full bg-slate-100 px-2.5 py-1 text-xs font-semibold text-slate-700">
              {group.count} {group.count === 1 ? "difference" : "differences"}
            </span>
            <div className="flex flex-wrap items-center gap-1.5">
              {provenanceEntries.map(([provenance, count]) => (
                <ProvenancePillCount
                  key={provenance}
                  provenance={provenance}
                  count={count}
                />
              ))}
            </div>
          </div>
        </button>

        {/* Group-level bulk actions — stop propagation so clicks don't toggle. */}
        <div
          className="flex shrink-0 items-center gap-2"
          onClick={(e) => e.stopPropagation()}
        >
          <Button
            size="sm"
            className="h-7 bg-avip-pass px-2.5 text-xs text-white hover:bg-avip-pass/90"
            onClick={() => onBulk("confirmed")}
            disabled={bulkPending}
          >
            {bulkPending ? (
              <Loader2 className="mr-1 size-3.5 animate-spin" />
            ) : null}
            Confirm all
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-7 px-2.5 text-xs"
            onClick={() => onBulk("dismissed")}
            disabled={bulkPending}
          >
            Dismiss all
          </Button>
        </div>
      </div>

      {/* Body */}
      {open && (
        <div
          id={panelId}
          className="divide-y divide-slate-100 border-t border-slate-200"
        >
          {group.discrepancies.map((item) => (
            <DiscrepancyRow
              key={item.id}
              item={item}
              onConfirm={() => onDecideItem(item.id, "confirmed")}
              onDismiss={() => onDecideItem(item.id, "dismissed")}
              isPending={itemPending}
            />
          ))}
        </div>
      )}
    </div>
  );
}

// ---------------------------------------------------------------------------
// DiscrepancyRow — one full-width discrepancy inside an expanded group.
// ---------------------------------------------------------------------------

function DiscrepancyRow({
  item,
  onConfirm,
  onDismiss,
  isPending,
}: {
  item: SCDiscrepancy;
  onConfirm: () => void;
  onDismiss: () => void;
  isPending: boolean;
}) {
  const needsManualCheck =
    item.provenance === "llm-unavailable" || item.provenance === "llm";

  return (
    <div className="space-y-3 px-4 py-4 sm:px-5">
      {/* Field label + provenance + per-item actions */}
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div className="flex flex-wrap items-center gap-3">
          <FieldLabel name={item.field_name} type={item.field_type} />
          <ProvenancePill provenance={item.provenance} />
        </div>
        <div className="flex shrink-0 items-center gap-2">
          <Button
            size="sm"
            className="h-8 bg-avip-pass px-3 text-xs text-white hover:bg-avip-pass/90"
            onClick={onConfirm}
            disabled={isPending}
          >
            Confirm
          </Button>
          <Button
            variant="outline"
            size="sm"
            className="h-8 px-3 text-xs"
            onClick={onDismiss}
            disabled={isPending}
          >
            Dismiss
          </Button>
        </div>
      </div>

      {/* Manual-check note for LLM provenance */}
      {needsManualCheck && (
        <div className="flex items-start gap-2 rounded-lg border border-avip-review/40 bg-avip-review/5 px-3 py-2 text-xs text-slate-700">
          <AlertTriangle className="mt-0.5 size-4 shrink-0 text-avip-review" />
          <span>
            {item.provenance === "llm-unavailable"
              ? "Automated comparison unavailable — review the source values manually before deciding."
              : "LLM-assisted flag — confirm the values genuinely differ before deciding."}
          </span>
        </div>
      )}

      {/* Source values — full width, nothing truncated */}
      <SourceValueCompareCard values={item.values} fieldType={item.field_type} />
    </div>
  );
}

// ---------------------------------------------------------------------------
// PaginationFooter — Prev / Next + range readout, by GROUP.
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
        <span className="font-semibold text-slate-900">{totalCount}</span> groups
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
