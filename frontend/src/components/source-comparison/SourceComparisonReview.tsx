import { useState } from "react";
import { Link } from "react-router-dom";
import { keepPreviousData, useQuery } from "@tanstack/react-query";
import { CheckCircle2, ChevronLeft, ChevronRight } from "lucide-react";
import { getReviewQueue } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SCDiscrepancy } from "../../types";
import {
  FieldLabel,
  PartLotCell,
  ProvenancePill,
  SourceValueCompare,
} from "./table-parts";

const PAGE_SIZE = 50;

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

      {/* Queue table */}
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
        <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
                <TableHead className="w-[150px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Part / Lot
                </TableHead>
                <TableHead className="w-[160px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Field
                </TableHead>
                <TableHead className="w-[160px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  How Flagged
                </TableHead>
                <TableHead className="w-[480px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Source Values
                </TableHead>
                <TableHead className="w-[110px] px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Action
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="divide-y divide-slate-100">
              {queue.map((item) => (
                <DiscrepancyRow key={item.id} item={item} />
              ))}
            </TableBody>
          </Table>
          <PaginationFooter
            rangeStart={rangeStart}
            rangeEnd={rangeEnd}
            totalCount={totalCount}
            canPrev={canPrev}
            canNext={canNext}
            onPrev={() => setPage((p) => Math.max(0, p - 1))}
            onNext={() => setPage((p) => p + 1)}
          />
        </Card>
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
    <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-3">
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

function DiscrepancyRow({ item }: { item: SCDiscrepancy }) {
  return (
    <TableRow className="border-0 transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3.5 align-top">
        <PartLotCell partNumber={item.part_number} lotNumber={item.lot_number} />
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <FieldLabel name={item.field_name} type={item.field_type} />
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <ProvenancePill provenance={item.provenance} />
      </TableCell>
      <TableCell className="w-[480px] max-w-[480px] px-4 py-3.5 align-top">
        <div className="w-full min-w-0">
          <SourceValueCompare values={item.values} fieldType={item.field_type} />
        </div>
      </TableCell>
      <TableCell className="w-[110px] px-4 py-3.5 text-right align-top">
        <Button
          variant="default"
          size="sm"
          render={<Link to={`/source-comparison/review/${item.id}`} />}
        >
          Review
        </Button>
      </TableCell>
    </TableRow>
  );
}
