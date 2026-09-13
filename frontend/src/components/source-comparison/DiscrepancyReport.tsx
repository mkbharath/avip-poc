import { useMemo, useState } from "react";
import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, Download, FileSearch, X } from "lucide-react";
import { getReport, getReportHeader, exportReportUrl } from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
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
import type { SCAssumption, SCProvenance, SCReportRow, SCSource } from "../../types";
import {
  FieldLabel,
  PartLotCell,
  ProvenancePill,
  SourceValueCompare,
} from "./table-parts";

// The three sources, used to populate the source filter dropdown.
const SOURCE_COLUMNS: SCSource[] = ["LAIR", "FAIR", "SHQ"];

// Non-technical-reviewer-friendly labels for the provenance codes (Req 7.5):
// each explains, in plain language, how the flag was determined.
const PROVENANCE_LABELS: Record<SCProvenance, string> = {
  "exact-match": "Exact match",
  "numeric-threshold": "Number tolerance",
  llm: "AI text review",
  "llm-unavailable": "Needs manual check",
};

export function DiscrepancyReport() {
  const [partFilter, setPartFilter] = useState("");
  const [lotFilter, setLotFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [fieldFilter, setFieldFilter] = useState("");
  const [provenanceFilter, setProvenanceFilter] = useState("");

  // Build the filters object sent to the API (only non-empty entries).
  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (partFilter.trim()) f.part_number = partFilter.trim();
    if (lotFilter.trim()) f.lot_number = lotFilter.trim();
    if (sourceFilter) f.source = sourceFilter;
    if (fieldFilter) f.field = fieldFilter;
    if (provenanceFilter) f.provenance = provenanceFilter;
    return f;
  }, [partFilter, lotFilter, sourceFilter, fieldFilter, provenanceFilter]);

  const { data: reportData, isLoading } = useQuery({
    queryKey: ["sc", "report", filters],
    queryFn: () => getReport(filters),
  });

  const { data: header } = useQuery({
    queryKey: ["sc", "report-header"],
    queryFn: getReportHeader,
  });

  const rows: SCReportRow[] = reportData?.data ?? [];

  // Field and provenance option lists derived from the current result set so the
  // filter dropdowns stay relevant.
  const fieldOptions = [...new Set(rows.map((r) => r.field_name))].sort();
  const provenanceOptions = [...new Set(rows.map((r) => r.provenance))].sort();

  const hasFilters =
    partFilter || lotFilter || sourceFilter || fieldFilter || provenanceFilter;

  const clearFilters = () => {
    setPartFilter("");
    setLotFilter("");
    setSourceFilter("");
    setFieldFilter("");
    setProvenanceFilter("");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">
            Confirmed Discrepancy Report
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            Reviewer-confirmed differences across LAIR, FAIR, and SHQ records
            {" · "}
            {rows.length} row{rows.length === 1 ? "" : "s"}
          </p>
        </div>
        <Button variant="default" render={<a href={exportReportUrl(filters)} download />}>
          <Download className="mr-1.5" />
          Export CSV
        </Button>
      </div>

      {/* Assumptions banner (Req 8.5) */}
      <AssumptionsBanner assumptions={header?.assumptions ?? []} />

      {/* Filters row */}
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Part Number</label>
          <Input
            className="w-[160px]"
            placeholder="All parts"
            value={partFilter}
            onChange={(e) => setPartFilter(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Lot Number</label>
          <Input
            className="w-[160px]"
            placeholder="All lots"
            value={lotFilter}
            onChange={(e) => setLotFilter(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Source</label>
          <Select value={sourceFilter} onValueChange={(v) => setSourceFilter(v ?? "")}>
            <SelectTrigger className="w-[150px]">
              <SelectValue placeholder="All sources" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All sources</SelectItem>
              {SOURCE_COLUMNS.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Field</label>
          <Select value={fieldFilter} onValueChange={(v) => setFieldFilter(v ?? "")}>
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All fields" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All fields</SelectItem>
              {fieldOptions.map((f) => (
                <SelectItem key={f} value={f}>
                  {f}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">How flagged</label>
          <Select
            value={provenanceFilter}
            onValueChange={(v) => setProvenanceFilter(v ?? "")}
          >
            <SelectTrigger className="w-[180px]">
              <SelectValue placeholder="All methods" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All methods</SelectItem>
              {provenanceOptions.map((p) => (
                <SelectItem key={p} value={p}>
                  {PROVENANCE_LABELS[p] ?? p}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        {hasFilters && (
          <Button variant="ghost" size="sm" onClick={clearFilters}>
            <X className="mr-1" />
            Clear filters
          </Button>
        )}
      </div>

      {/* Report table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
        </div>
      ) : rows.length === 0 ? (
        <div className="text-center py-20">
          <FileSearch className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">No confirmed discrepancies</h3>
          <p className="text-sm text-muted-foreground/70 mt-1">
            {hasFilters
              ? "No confirmed differences match the current filters."
              : "Confirmed differences will appear here once reviewers act on the queue."}
          </p>
        </div>
      ) : (
        <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
          <Table className="table-fixed">
            <TableHeader>
              <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
                <TableHead className="w-[180px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Part / Lot
                </TableHead>
                <TableHead className="w-[200px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Field
                </TableHead>
                <TableHead className="w-[180px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  How Flagged
                </TableHead>
                <TableHead className="w-[420px] px-4 py-3 text-[11px] font-semibold uppercase tracking-wider text-slate-500">
                  Source Values
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <ReportRow key={row.id} row={row} />
              ))}
            </TableBody>
          </Table>
        </Card>
      )}
    </div>
  );
}

function ReportRow({ row }: { row: SCReportRow }) {
  return (
    <TableRow className="border-0 transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3.5 align-top">
        <PartLotCell partNumber={row.part_number} lotNumber={row.lot_number} />
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <FieldLabel name={row.field_name} type={row.field_type} />
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <ProvenancePill provenance={row.provenance} />
      </TableCell>
      <TableCell className="w-[420px] max-w-[420px] px-4 py-3.5 align-top">
        <div className="w-full min-w-0 max-w-[388px]">
          <SourceValueCompare values={row.values} fieldType={row.field_type} />
        </div>
      </TableCell>
    </TableRow>
  );
}

function AssumptionsBanner({ assumptions }: { assumptions: SCAssumption[] }) {
  if (assumptions.length === 0) return null;

  return (
    <div className="rounded-lg border border-amber-200 bg-amber-50 px-4 py-3">
      <div className="flex items-start gap-3">
        <AlertTriangle className="w-5 h-5 text-amber-600 shrink-0 mt-0.5" />
        <div className="space-y-2">
          <div>
            <p className="text-sm font-semibold text-amber-900">
              Assumptions in effect — pending client confirmation
            </p>
            <p className="text-xs text-amber-800 mt-0.5">
              The results below rely on the following working assumptions. Please confirm them.
            </p>
          </div>
          <ul className="space-y-1.5">
            {assumptions.map((a) => (
              <li key={a.key} className="flex items-start gap-2 text-xs text-amber-900">
                <Badge
                  variant="outline"
                  className="border-amber-300 bg-amber-100 text-amber-900 font-semibold"
                >
                  {a.status === "unresolved" ? "unresolved" : "assumed"}
                </Badge>
                <span>
                  <span className="font-medium">{a.label}</span>
                  {a.value ? <span className="text-amber-800"> — {a.value}</span> : null}
                </span>
              </li>
            ))}
          </ul>
        </div>
      </div>
    </div>
  );
}
