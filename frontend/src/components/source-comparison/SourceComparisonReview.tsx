import { useState } from "react";
import { Link } from "react-router-dom";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  CheckCircle2,
  ChevronLeft,
  ChevronRight,
  Loader2,
} from "lucide-react";
import { decideDiscrepancy, getReviewQueue } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import type { SCDiscrepancy } from "../../types";
import {
  FieldLabel,
  PartLotCell,
  ProvenancePill,
  SourceValueCompareCard,
} from "./table-parts";

const PAGE_SIZE = 50;
const DEFAULT_REVIEWER = "IQA Inspector";

export function SourceComparisonReview() {
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["sc", "review-queue", page],
    queryFn: () => getReviewQueue({ limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    refetchInterval: 5_000,
    placeholderData: keepPreviousData,
  });

  const queue = data?.data ?? [];
  const totalCount = data?.total_count ?? 0;
  const rangeStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + queue.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * PAGE_SIZE < totalCount;

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight">
          Source Comparison Review
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {totalCount} pending {totalCount === 1 ? "discrepancy" : "discrepancies"} awaiting review
        </p>
      </div>

      {/* Queue as a card feed */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
        </div>
      ) : queue.length === 0 ? (
        <div className="text-center py-20">
          <CheckCircle2 className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">No pending discrepancies</h3>
          <p className="text-sm text-muted-foreground/70 mt-1">
            All flagged discrepancies have been reviewed
          </p>
        </div>
      ) : (
        <div className="space-y-4">
          <div className="grid gap-4 xl:grid-cols-2">
            {queue.map((item) => (
              <DiscrepancyCard key={item.id} item={item} />
            ))}
          </div>
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
      )}
    </div>
  );
}

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
    <div className="flex items-center justify-between rounded-xl border border-slate-200 bg-slate-50 px-4 py-3">
      <p className="text-xs text-slate-600">
        Showing <span className="font-semibold text-slate-900">{rangeStart}</span>–
        <span className="font-semibold text-slate-900">{rangeEnd}</span> of{" "}
        <span className="font-semibold text-slate-900">{totalCount}</span>
      </p>
      <div className="flex items-center gap-2">
        <Button variant="outline" size="sm" disabled={!canPrev} onClick={onPrev}>
          <ChevronLeft className="mr-1" />
          Prev
        </Button>
        <Button variant="outline" size="sm" disabled={!canNext} onClick={onNext}>
          Next
          <ChevronRight className="ml-1" />
        </Button>
      </div>
    </div>
  );
}

function DiscrepancyCard({ item }: { item: SCDiscrepancy }) {
  const queryClient = useQueryClient();
  const [note, setNote] = useState("");

  const decideMutation = useMutation({
    mutationFn: (decision: "confirmed" | "dismissed") =>
      decideDiscrepancy(item.id, {
        decision,
        reviewer: DEFAULT_REVIEWER,
        note: note.trim() || undefined,
      }),
    onSuccess: () => {
      // Invalidate the whole "sc" tree so the review queue (and pending
      // counts) refetch — the decided card drops out of the pending list.
      queryClient.invalidateQueries({ queryKey: ["sc"] });
    },
  });

  const isPending = decideMutation.isPending;

  return (
    <Card className="gap-0 rounded-xl border border-slate-200 p-0 shadow-sm transition-shadow hover:shadow-md">
      {/* Header strip */}
      <div className="flex items-start justify-between gap-3 px-4 py-3">
        <PartLotCell partNumber={item.part_number} lotNumber={item.lot_number} />
        <ProvenancePill provenance={item.provenance} />
      </div>
      <div className="h-px bg-slate-200" />

      {/* Body */}
      <div className="space-y-3 px-4 py-3">
        <FieldLabel name={item.field_name} type={item.field_type} />
        <SourceValueCompareCard values={item.values} fieldType={item.field_type} />
      </div>

      {/* Footer actions */}
      <div className="flex flex-col gap-2 border-t border-slate-200 bg-slate-50/70 px-4 py-3 sm:flex-row sm:items-center">
        <Input
          value={note}
          onChange={(e) => setNote(e.target.value)}
          placeholder="Note (optional)"
          disabled={isPending}
          className="h-8 flex-1 text-sm"
          aria-label="Reviewer note (optional)"
        />
        <div className="flex items-center gap-2">
          <Button
            size="sm"
            className="bg-avip-pass text-white hover:bg-avip-pass/90"
            onClick={() => decideMutation.mutate("confirmed")}
            disabled={isPending}
          >
            {isPending ? <Loader2 className="mr-1 size-3.5 animate-spin" /> : null}
            Confirm
          </Button>
          <Button
            variant="outline"
            size="sm"
            onClick={() => decideMutation.mutate("dismissed")}
            disabled={isPending}
          >
            Dismiss
          </Button>
          <Button
            variant="ghost"
            size="sm"
            render={<Link to={`/source-comparison/review/${item.id}`} />}
          >
            Details
          </Button>
        </div>
      </div>
    </Card>
  );
}
