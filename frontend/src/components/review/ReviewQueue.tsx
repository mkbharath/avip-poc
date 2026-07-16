import { useState } from "react";
import { Link } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { CheckCircle2, X } from "lucide-react";
import { getReviewQueue } from "../../api/inspections";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import {
  Table,
  TableBody,
  TableCell,
  TableHead,
  TableHeader,
  TableRow,
} from "@/components/ui/table";
import type { ReviewQueueItem } from "../../types";

export function ReviewQueue() {
  const [familyFilter, setFamilyFilter] = useState<string>("");
  const [classFilter, setClassFilter] = useState<string>("");

  const { data, isLoading } = useQuery({
    queryKey: ["reviewQueue"],
    queryFn: getReviewQueue,
    refetchInterval: 10_000,
  });

  const queue = data?.data || [];

  const filtered = queue.filter((item) => {
    if (familyFilter && item.family_name !== familyFilter) return false;
    if (classFilter && !item.defect_classes.includes(classFilter)) return false;
    return true;
  });

  const families = [...new Set(queue.map((i) => i.family_name))];
  const allClasses = [...new Set(queue.flatMap((i) => i.defect_classes))];

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div>
        <h1 className="text-xl font-bold text-foreground tracking-tight">IQA Review Queue</h1>
        <p className="text-sm text-muted-foreground mt-0.5">{filtered.length} items pending review</p>
      </div>

      {/* Filters row */}
      <div className="flex items-end gap-4">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Part Family</label>
          <Select value={familyFilter} onValueChange={(v) => setFamilyFilter(v ?? "")}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All families" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All families</SelectItem>
              {families.map((f) => (
                <SelectItem key={f} value={f}>{f}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Defect Class</label>
          <Select value={classFilter} onValueChange={(v) => setClassFilter(v ?? "")}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All classes" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All classes</SelectItem>
              {allClasses.map((c) => (
                <SelectItem key={c} value={c}>{c}</SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {(familyFilter || classFilter) && (
          <Button
            variant="ghost"
            size="sm"
            onClick={() => { setFamilyFilter(""); setClassFilter(""); }}
          >
            <X className="mr-1" />
            Clear filters
          </Button>
        )}
      </div>

      {/* Queue table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
        </div>
      ) : filtered.length === 0 ? (
        <div className="text-center py-20">
          <CheckCircle2 className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">Queue is empty</h3>
          <p className="text-sm text-muted-foreground/70 mt-1">All inspections have been reviewed</p>
        </div>
      ) : (
        <Card className="overflow-hidden">
          <Table>
            <TableHeader>
              <TableRow className="bg-muted/50">
                <TableHead className="text-xs uppercase">Priority</TableHead>
                <TableHead className="text-xs uppercase">Age</TableHead>
                <TableHead className="text-xs uppercase">Part Number</TableHead>
                <TableHead className="text-xs uppercase">Family</TableHead>
                <TableHead className="text-xs uppercase">Supplier</TableHead>
                <TableHead className="text-xs uppercase">Defects</TableHead>
                <TableHead className="text-xs uppercase">Confidence</TableHead>
                <TableHead className="text-xs uppercase">Decision</TableHead>
                <TableHead></TableHead>
              </TableRow>
            </TableHeader>
            <TableBody>
              {filtered.map((item) => (
                <QueueRow key={item.id} item={item} />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function QueueRow({ item }: { item: ReviewQueueItem }) {
  const ageMinutes = Math.floor(item.age_seconds / 60);
  const ageDisplay = ageMinutes < 60 ? `${ageMinutes}m` : `${Math.floor(ageMinutes / 60)}h ${ageMinutes % 60}m`;

  const ageSLA = ageMinutes > 240;
  const ageWarning = ageMinutes > 120;

  return (
    <TableRow className="group cursor-pointer">
      <TableCell>
        <PriorityBadge priority={item.priority} />
      </TableCell>
      <TableCell>
        <span className={`text-sm font-medium ${ageSLA ? "text-avip-fail" : ageWarning ? "text-avip-review" : "text-foreground"}`}>
          {ageDisplay}
        </span>
      </TableCell>
      <TableCell>
        <span className="text-sm font-mono font-bold text-foreground">{item.part_number}</span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">{item.family_name}</span>
      </TableCell>
      <TableCell>
        <span className="text-sm text-muted-foreground">{item.supplier}</span>
      </TableCell>
      <TableCell>
        <div className="flex gap-1 flex-wrap">
          {item.defect_classes.map((dc) => (
            <Badge key={dc} variant="outline" className="text-xs">
              {dc}
            </Badge>
          ))}
        </div>
      </TableCell>
      <TableCell>
        <ConfidenceBadge band={item.confidence_band} />
      </TableCell>
      <TableCell>
        <Badge variant={item.decision === "FAIL" ? "destructive" : "secondary"} className="text-xs">
          {item.decision}
        </Badge>
      </TableCell>
      <TableCell>
        <Button
          variant="default"
          size="xs"
          className="opacity-0 group-hover:opacity-100 transition-opacity"
          render={<Link to={`/review/${item.id}`} />}
        >
          Review
        </Button>
      </TableCell>
    </TableRow>
  );
}

function PriorityBadge({ priority }: { priority: number }) {
  const level = priority > 70 ? "high" : priority > 40 ? "medium" : "low";
  const colors = {
    high: "bg-red-100 text-red-700 border-red-200",
    medium: "bg-yellow-100 text-yellow-700 border-yellow-200",
    low: "bg-muted text-muted-foreground border-border",
  };

  return (
    <span className={`inline-flex items-center justify-center w-8 h-8 rounded-full text-xs font-bold border ${colors[level]}`}>
      {priority}
    </span>
  );
}

function ConfidenceBadge({ band }: { band: string }) {
  const variant = band === "high" ? "destructive" : band === "medium" ? "secondary" : "outline";
  return (
    <Badge variant={variant} className="text-xs">
      {band}
    </Badge>
  );
}
