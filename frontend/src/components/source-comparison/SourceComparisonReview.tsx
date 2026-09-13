import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
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

export function SourceComparisonReview() {
  const { data, isLoading } = useQuery({
    queryKey: ["sc", "review-queue"],
    queryFn: getReviewQueue,
    refetchInterval: 5_000,
  });

  const queue = data?.data ?? [];

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight">
          Source Comparison Review
        </h1>
        <p className="text-sm text-muted-foreground mt-0.5">
          {queue.length} pending {queue.length === 1 ? "discrepancy" : "discrepancies"} awaiting review
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
          <Table>
            <TableHeader>
              <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
                <TableHead className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Part / Lot
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Field
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  How Flagged
                </TableHead>
                <TableHead className="px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Source Values
                </TableHead>
                <TableHead className="px-4 py-3 text-right text-[11px] font-semibold uppercase tracking-wider text-slate-500">
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
        </Card>
      )}
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
      <TableCell className="px-4 py-3.5 align-top">
        <div className="min-w-[280px]">
          <SourceValueCompare values={item.values} fieldType={item.field_type} />
        </div>
      </TableCell>
      <TableCell className="px-4 py-3.5 text-right align-top">
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
