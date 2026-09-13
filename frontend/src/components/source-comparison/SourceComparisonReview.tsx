import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2 } from "lucide-react";
import { getReviewQueue } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { SCDiscrepancy, SCProvenance } from "../../types";

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
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="text-xs uppercase text-slate-600 font-semibold">Part / Lot</TableHead>
                <TableHead className="text-xs uppercase text-slate-600 font-semibold">Field</TableHead>
                <TableHead className="text-xs uppercase text-slate-600 font-semibold">Type</TableHead>
                <TableHead className="text-xs uppercase text-slate-600 font-semibold">Provenance</TableHead>
                <TableHead className="text-xs uppercase text-slate-600 font-semibold">Source Values</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
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
    <TableRow className="group cursor-pointer">
      <TableCell>
        <div className="flex flex-col">
          <span className="text-sm font-mono font-bold text-slate-900">{item.part_number}</span>
          <span className="text-xs text-slate-600 font-mono">Lot {item.lot_number}</span>
        </div>
      </TableCell>
      <TableCell>
        <span className="text-sm font-medium text-slate-900 capitalize">
          {item.field_name.replace(/_/g, " ")}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-xs text-slate-600 capitalize">
          {item.field_type.replace(/_/g, " ")}
        </span>
      </TableCell>
      <TableCell>
        <ProvenanceBadge provenance={item.provenance} />
      </TableCell>
      <TableCell>
        <div className="flex gap-1.5 flex-wrap">
          {Object.entries(item.values).map(([source, value]) => (
            <SourceValueChip key={source} source={source} value={value} />
          ))}
        </div>
      </TableCell>
      <TableCell>
        <Button
          variant="default"
          size="xs"
          render={<Link to={`/source-comparison/review/${item.id}`} />}
        >
          Review
        </Button>
      </TableCell>
    </TableRow>
  );
}

function SourceValueChip({ source, value }: { source: string; value: string | number | null }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-slate-200 bg-slate-100 px-1.5 py-0.5 text-xs">
      <span className="font-semibold text-slate-600">{source}</span>
      <span className="font-mono font-medium text-slate-900">
        {value === null ? "—" : String(value)}
      </span>
    </span>
  );
}

function ProvenanceBadge({ provenance }: { provenance: SCProvenance }) {
  const variant =
    provenance === "llm-unavailable"
      ? "destructive"
      : provenance === "llm"
        ? "secondary"
        : "outline";
  const label =
    provenance === "exact-match"
      ? "Exact Match"
      : provenance === "numeric-threshold"
        ? "Numeric Threshold"
        : provenance === "llm"
          ? "LLM"
          : "LLM Unavailable";
  return (
    <Badge
      variant={variant}
      className={variant === "outline" ? "text-xs text-slate-700 border-slate-300" : "text-xs"}
    >
      {label}
    </Badge>
  );
}
