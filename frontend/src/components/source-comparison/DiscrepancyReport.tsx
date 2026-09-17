import { useEffect, useMemo, useState } from "react";
import {
  keepPreviousData,
  useMutation,
  useQuery,
  useQueryClient,
} from "@tanstack/react-query";
import {
  AlertTriangle,
  ChevronLeft,
  ChevronRight,
  Download,
  FileSearch,
  RotateCcw,
  X,
} from "lucide-react";
import {
  getReport,
  getReportHeader,
  getSupplierSummary,
  exportReportUrl,
  reopenDiscrepancy,
} from "../../api/source-comparison";
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
import type {
  SCAssumption,
  SCProvenance,
  SCReportRow,
  SCReviewState,
  SCSource,
  SCSupplierSummaryRow,
} from "../../types";
import {
  FieldLabel,
  PartLotCell,
  ProvenancePill,
  SourceValueCompare,
} from "./table-parts";

// The three sources, used to populate the source filter dropdown.
const SOURCE_COLUMNS: SCSource[] = ["LAIR", "FAIR", "SHQ"];

const PAGE_SIZE = 50;

// Non-technical-reviewer-friendly labels for the provenance codes (Req 7.5):
// each explains, in plain language, how the flag was determined.
const PROVENANCE_LABELS: Record<SCProvenance, string> = {
  "exact-match": "Exact match",
  "numeric-threshold": "Number tolerance",
  llm: "AI text review",
  "llm-unavailable": "Needs manual check",
};

// The review-status filter values. "confirmed" is the DEFAULT so the report
// opens exactly as it did before this filter existed (confirmed-only), keeping
// Property 5 and the existing tests intact — the other statuses are opt-in.
type ReviewStatusFilter = "confirmed" | "dismissed" | "pending" | "all";

const REVIEW_STATUS_OPTIONS: { value: ReviewStatusFilter; label: string }[] = [
  { value: "all", label: "All" },
  { value: "confirmed", label: "Confirmed" },
  { value: "dismissed", label: "Dismissed" },
  { value: "pending", label: "Pending" },
];

// Heading + subtitle wording per active status so it is always clear the table
// is no longer necessarily confirmed-only.
const STATUS_HEADING: Record<ReviewStatusFilter, string> = {
  confirmed: "Confirmed Discrepancy Report",
  dismissed: "Dismissed Discrepancy Report",
  pending: "Pending Discrepancy Report",
  all: "All Discrepancies Report",
};

const STATUS_SUBTITLE: Record<ReviewStatusFilter, string> = {
  confirmed: "Reviewer-confirmed differences",
  dismissed: "Dismissed differences",
  pending: "Pending differences awaiting review",
  all: "All differences (any review status)",
};

// Presentation for the inline review-state badge shown in the "All" view.
const REVIEW_STATE_BADGE: Record<SCReviewState, { label: string; className: string }> = {
  confirmed: {
    label: "Confirmed",
    className: "border-emerald-300 bg-emerald-50 text-emerald-800",
  },
  dismissed: {
    label: "Dismissed",
    className: "border-slate-300 bg-slate-100 text-slate-600",
  },
  pending: {
    label: "Pending",
    className: "border-amber-300 bg-amber-50 text-amber-800",
  },
};

// Default reviewer identity used for the Reopen action (portal-wide auth is
// deferred — this mirrors the review workbench's self-declared identity).
const DEFAULT_REVIEWER = "IQA Inspector";

export function DiscrepancyReport() {
  const [partFilter, setPartFilter] = useState("");
  const [lotFilter, setLotFilter] = useState("");
  const [sourceFilter, setSourceFilter] = useState("");
  const [fieldFilter, setFieldFilter] = useState("");
  const [provenanceFilter, setProvenanceFilter] = useState("");
  const [supplierFilter, setSupplierFilter] = useState("");
  // Default = confirmed so the page opens exactly as it did before.
  const [statusFilter, setStatusFilter] = useState<ReviewStatusFilter>("confirmed");

  const queryClient = useQueryClient();

  // Build the filters object sent to the API (only non-empty entries).
  const filters = useMemo(() => {
    const f: Record<string, string> = {};
    if (partFilter.trim()) f.part_number = partFilter.trim();
    if (lotFilter.trim()) f.lot_number = lotFilter.trim();
    if (sourceFilter) f.source = sourceFilter;
    if (fieldFilter) f.field = fieldFilter;
    if (provenanceFilter) f.provenance = provenanceFilter;
    if (supplierFilter) f.supplier = supplierFilter;
    // Only send review_state when the reviewer opts out of the confirmed-only
    // default, so the default request stays byte-for-byte as before and hits
    // the unchanged confirmed-only report path on the backend.
    if (statusFilter !== "confirmed") f.review_state = statusFilter;
    return f;
  }, [
    partFilter,
    lotFilter,
    sourceFilter,
    fieldFilter,
    provenanceFilter,
    supplierFilter,
    statusFilter,
  ]);

  // Filters for the "By supplier" rollup: the same part/lot/source/field/
  // provenance filters, but NOT the supplier filter (the rollup surfaces every
  // supplier) and NOT review_state (the backend rollup is confirmed-only).
  const summaryFilters = useMemo(() => {
    const f: Record<string, string> = {};
    if (partFilter.trim()) f.part_number = partFilter.trim();
    if (lotFilter.trim()) f.lot_number = lotFilter.trim();
    if (sourceFilter) f.source = sourceFilter;
    if (fieldFilter) f.field = fieldFilter;
    if (provenanceFilter) f.provenance = provenanceFilter;
    return f;
  }, [partFilter, lotFilter, sourceFilter, fieldFilter, provenanceFilter]);

  // Whether the active view can contain decided rows that offer a Reopen action
  // and should show a status badge column.
  const showStatusColumn = statusFilter === "all";

  const [page, setPage] = useState(0);

  // Reset to the first page whenever the active filters change.
  useEffect(() => {
    setPage(0);
  }, [filters]);

  const { data: reportData, isLoading } = useQuery({
    queryKey: ["sc", "report", filters, page],
    queryFn: () => getReport(filters, { limit: PAGE_SIZE, offset: page * PAGE_SIZE }),
    placeholderData: keepPreviousData,
  });

  const { data: header } = useQuery({
    queryKey: ["sc", "report-header"],
    queryFn: getReportHeader,
  });

  // The confirmed-only "By supplier" rollup. Keyed on the summary filters
  // (supplier + review_state excluded) so it refreshes with the other filters
  // but not when only the supplier filter changes.
  const { data: supplierSummary } = useQuery({
    queryKey: ["sc", "supplier-summary", summaryFilters],
    queryFn: () => getSupplierSummary(summaryFilters),
    placeholderData: keepPreviousData,
  });

  // Reopen a decided discrepancy → returns it to pending, then refresh the
  // report and the review queue so both views reflect the change.
  const reopenMutation = useMutation({
    mutationFn: (id: string) =>
      reopenDiscrepancy(id, { reviewer: DEFAULT_REVIEWER }),
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sc", "report"] });
      queryClient.invalidateQueries({ queryKey: ["sc", "review"] });
    },
  });

  const rows: SCReportRow[] = reportData?.data ?? [];
  const totalCount = reportData?.total_count ?? 0;
  const rangeStart = totalCount === 0 ? 0 : page * PAGE_SIZE + 1;
  const rangeEnd = page * PAGE_SIZE + rows.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * PAGE_SIZE < totalCount;

  // Field and provenance option lists derived from the current result set so the
  // filter dropdowns stay relevant.
  const fieldOptions = [...new Set(rows.map((r) => r.field_name))].sort();
  const provenanceOptions = [...new Set(rows.map((r) => r.provenance))].sort();

  // Supplier options: suppliers aren't known in advance, so derive them from
  // the supplier values present on the current result rows. When a supplier
  // filter is active the result rows only contain that supplier, so also fold
  // in the active filter value and the rollup's suppliers to keep the dropdown
  // from collapsing to a single option.
  const supplierOptions = useMemo(() => {
    const set = new Set<string>();
    for (const r of rows) {
      const s = r.part_context?.supplier;
      if (s && s.trim()) set.add(s);
    }
    for (const s of supplierSummary?.data ?? []) {
      if (s.supplier && s.supplier !== "(unknown)") set.add(s.supplier);
    }
    if (supplierFilter) set.add(supplierFilter);
    return [...set].sort();
  }, [rows, supplierSummary, supplierFilter]);

  const hasFilters =
    partFilter ||
    lotFilter ||
    sourceFilter ||
    fieldFilter ||
    provenanceFilter ||
    supplierFilter ||
    statusFilter !== "confirmed";

  const clearFilters = () => {
    setPartFilter("");
    setLotFilter("");
    setSourceFilter("");
    setFieldFilter("");
    setProvenanceFilter("");
    setSupplierFilter("");
    setStatusFilter("confirmed");
  };

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="text-xl font-bold text-foreground tracking-tight">
            {STATUS_HEADING[statusFilter]}
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            {STATUS_SUBTITLE[statusFilter]} across LAIR, FAIR, and SHQ records
            {" · "}
            {totalCount} row{totalCount === 1 ? "" : "s"}
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
          <label className="text-xs font-medium text-slate-600">
            Review status
          </label>
          <Select
            value={statusFilter}
            onValueChange={(v) =>
              setStatusFilter((v as ReviewStatusFilter) || "confirmed")
            }
          >
            <SelectTrigger className="w-[150px]">
              <SelectValue />
            </SelectTrigger>
            <SelectContent>
              {REVIEW_STATUS_OPTIONS.map((o) => (
                <SelectItem key={o.value} value={o.value}>
                  {o.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-600">Part Number</label>
          <Input
            className="w-[160px]"
            placeholder="All parts"
            value={partFilter}
            onChange={(e) => setPartFilter(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-600">Lot Number</label>
          <Input
            className="w-[160px]"
            placeholder="All lots"
            value={lotFilter}
            onChange={(e) => setLotFilter(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-600">Source</label>
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
          <label className="text-xs font-medium text-slate-600">Field</label>
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
          <label className="text-xs font-medium text-slate-600">How flagged</label>
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

        <div className="space-y-1">
          <label className="text-xs font-medium text-slate-600">Supplier</label>
          <Select
            value={supplierFilter}
            onValueChange={(v) => setSupplierFilter(v ?? "")}
          >
            <SelectTrigger className="w-[190px]">
              <SelectValue placeholder="All suppliers" />
            </SelectTrigger>
            <SelectContent>
              <SelectItem value="">All suppliers</SelectItem>
              {supplierOptions.map((s) => (
                <SelectItem key={s} value={s}>
                  {s}
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

      {/* By-supplier rollup panel (confirmed-only supplier-quality summary) */}
      <SupplierSummaryPanel
        rows={supplierSummary?.data ?? []}
        activeSupplier={supplierFilter}
        onSelectSupplier={(s) => setSupplierFilter(s)}
      />

      {/* Report table */}
      {isLoading ? (
        <div className="flex items-center justify-center py-20">
          <div className="animate-spin w-8 h-8 border-4 border-lam-navy border-t-transparent rounded-full" />
        </div>
      ) : rows.length === 0 ? (
        <div className="text-center py-20">
          <FileSearch className="w-16 h-16 text-muted-foreground/30 mx-auto mb-4" />
          <h3 className="text-lg font-medium text-muted-foreground">
            No discrepancies to show
          </h3>
          <p className="text-sm text-muted-foreground/70 mt-1">
            {hasFilters
              ? "No differences match the current filters."
              : "Differences will appear here once records are compared and reviewed."}
          </p>
        </div>
      ) : (
        <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
          <Table>
            <TableHeader>
              <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
                <TableHead className="w-[150px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Part / Lot
                </TableHead>
                <TableHead className="w-[160px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Field
                </TableHead>
                <TableHead className="w-[160px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  How Flagged
                </TableHead>
                {showStatusColumn && (
                  <TableHead className="w-[110px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                    Status
                  </TableHead>
                )}
                <TableHead className="w-[440px] px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Source Values
                </TableHead>
                <TableHead className="w-[120px] px-4 py-3 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                  Actions
                </TableHead>
              </TableRow>
            </TableHeader>
            <TableBody className="divide-y divide-slate-100">
              {rows.map((row) => (
                <ReportRow
                  key={row.id}
                  row={row}
                  showStatus={showStatusColumn}
                  onReopen={() => reopenMutation.mutate(row.id)}
                  reopening={
                    reopenMutation.isPending &&
                    reopenMutation.variables === row.id
                  }
                />
              ))}
            </TableBody>
          </Table>
          <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-3">
            <p className="text-xs text-slate-600">
              Showing <span className="font-semibold text-slate-900">{rangeStart}</span>–
              <span className="font-semibold text-slate-900">{rangeEnd}</span> of{" "}
              <span className="font-semibold text-slate-900">{totalCount}</span>
            </p>
            <div className="flex items-center gap-2">
              <Button
                variant="outline"
                size="sm"
                disabled={!canPrev}
                onClick={() => setPage((p) => Math.max(0, p - 1))}
              >
                <ChevronLeft className="mr-1" />
                Prev
              </Button>
              <Button
                variant="outline"
                size="sm"
                disabled={!canNext}
                onClick={() => setPage((p) => p + 1)}
              >
                Next
                <ChevronRight className="ml-1" />
              </Button>
            </div>
          </div>
        </Card>
      )}
    </div>
  );
}

function ReportRow({
  row,
  showStatus,
  onReopen,
  reopening,
}: {
  row: SCReportRow;
  showStatus: boolean;
  onReopen: () => void;
  reopening: boolean;
}) {
  // A row can be reopened only when we know it is currently decided
  // (confirmed or dismissed). review_state is present on the opt-in views; the
  // default confirmed-only report omits it, in which case rows are confirmed.
  const effectiveState: SCReviewState = row.review_state ?? "confirmed";
  const canReopen = effectiveState === "confirmed" || effectiveState === "dismissed";

  return (
    <TableRow className="border-0 transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3.5 align-top">
        <PartLotCell
          partNumber={row.part_number}
          lotNumber={row.lot_number}
          context={row.part_context}
        />
        {row.part_context?.supplier ? (
          <span className="mt-1 inline-block text-xs text-slate-500">
            {row.part_context.supplier}
          </span>
        ) : null}
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <FieldLabel name={row.field_name} type={row.field_type} />
      </TableCell>
      <TableCell className="px-4 py-3.5 align-top">
        <ProvenancePill provenance={row.provenance} />
      </TableCell>
      {showStatus && (
        <TableCell className="px-4 py-3.5 align-top">
          <ReviewStateBadge state={effectiveState} />
        </TableCell>
      )}
      <TableCell className="px-4 py-3.5 align-top">
        <div className="w-full min-w-0">
          <SourceValueCompare values={row.values} fieldType={row.field_type} />
        </div>
      </TableCell>
      <TableCell className="px-4 py-3.5 text-right align-top">
        {canReopen ? (
          <Button
            variant="outline"
            size="sm"
            disabled={reopening}
            onClick={onReopen}
            title="Return this discrepancy to the pending review queue"
          >
            <RotateCcw className="mr-1" />
            {reopening ? "Reopening…" : "Reopen"}
          </Button>
        ) : (
          <span className="text-xs text-muted-foreground/60">—</span>
        )}
      </TableCell>
    </TableRow>
  );
}

function ReviewStateBadge({ state }: { state: SCReviewState }) {
  const cfg = REVIEW_STATE_BADGE[state];
  return (
    <Badge variant="outline" className={`font-semibold ${cfg.className}`}>
      {cfg.label}
    </Badge>
  );
}

function SupplierSummaryPanel({
  rows,
  activeSupplier,
  onSelectSupplier,
}: {
  rows: SCSupplierSummaryRow[];
  activeSupplier: string;
  onSelectSupplier: (supplier: string) => void;
}) {
  const [open, setOpen] = useState(true);

  if (rows.length === 0) return null;

  const topDiscrepancies = rows[0]?.discrepancy_count ?? 0;

  return (
    <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
      <button
        type="button"
        onClick={() => setOpen((o) => !o)}
        className="flex w-full items-center justify-between gap-2 border-b border-slate-200 bg-slate-50 px-4 py-2.5 text-left hover:bg-slate-100"
      >
        <span className="flex items-center gap-2">
          <span className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            By supplier
          </span>
          <span className="text-xs text-slate-500">
            {rows.length} supplier{rows.length === 1 ? "" : "s"} · confirmed
            discrepancies
          </span>
        </span>
        {open ? (
          <ChevronLeft className="size-4 rotate-90 text-slate-500" />
        ) : (
          <ChevronRight className="size-4 rotate-90 text-slate-500" />
        )}
      </button>
      {open && (
        <Table>
          <TableHeader>
            <TableRow className="border-b border-slate-200 bg-white hover:bg-white">
              <TableHead className="px-4 py-2.5 text-xs font-semibold uppercase tracking-wider text-slate-500">
                Supplier
              </TableHead>
              <TableHead className="w-[140px] px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                Discrepancies
              </TableHead>
              <TableHead className="w-[100px] px-4 py-2.5 text-right text-xs font-semibold uppercase tracking-wider text-slate-500">
                Parts
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-slate-100">
            {rows.map((r) => {
              const isActive = activeSupplier === r.supplier;
              const isSelectable = r.supplier !== "(unknown)";
              const barPct =
                topDiscrepancies > 0
                  ? Math.max(4, (r.discrepancy_count / topDiscrepancies) * 100)
                  : 0;
              return (
                <TableRow
                  key={r.supplier}
                  className={`border-0 transition-colors ${
                    isActive ? "bg-lam-navy/5" : "hover:bg-slate-50/70"
                  } ${isSelectable ? "cursor-pointer" : ""}`}
                  onClick={
                    isSelectable
                      ? () => onSelectSupplier(isActive ? "" : r.supplier)
                      : undefined
                  }
                  title={
                    isSelectable
                      ? isActive
                        ? "Clear supplier filter"
                        : `Filter to ${r.supplier}`
                      : undefined
                  }
                >
                  <TableCell className="px-4 py-2.5">
                    <div className="flex items-center gap-2">
                      <span
                        className={`text-sm ${
                          r.supplier === "(unknown)"
                            ? "italic text-slate-500"
                            : "font-medium text-slate-800"
                        }`}
                      >
                        {r.supplier}
                      </span>
                      {isActive ? (
                        <Badge
                          variant="outline"
                          className="border-lam-navy/30 bg-lam-navy/10 text-[10px] font-semibold text-lam-navy"
                        >
                          filtered
                        </Badge>
                      ) : null}
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-2.5 text-right">
                    <div className="flex items-center justify-end gap-2">
                      <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                        <div
                          className="h-full rounded-full bg-amber-400"
                          style={{ width: `${barPct}%` }}
                        />
                      </div>
                      <span className="text-sm font-semibold tabular-nums text-slate-900">
                        {r.discrepancy_count}
                      </span>
                    </div>
                  </TableCell>
                  <TableCell className="px-4 py-2.5 text-right text-sm tabular-nums text-slate-600">
                    {r.part_count}
                  </TableCell>
                </TableRow>
              );
            })}
          </TableBody>
        </Table>
      )}
    </Card>
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
            <p className="text-sm font-semibold text-amber-900">Data assumptions</p>
            <p className="text-xs text-amber-800 mt-0.5">
              Some items below are confirmed by the client; others are working
              assumptions still pending client confirmation.
            </p>
          </div>
          <ul className="space-y-1.5">
            {assumptions.map((a) => {
              const confirmed = a.status === "confirmed";
              return (
                <li
                  key={a.key}
                  className={`flex items-start gap-2 text-xs ${
                    confirmed ? "text-emerald-900" : "text-amber-900"
                  }`}
                >
                  <Badge
                    variant="outline"
                    className={`font-semibold ${
                      confirmed
                        ? "border-emerald-300 bg-emerald-100 text-emerald-900"
                        : "border-amber-300 bg-amber-100 text-amber-900"
                    }`}
                  >
                    {a.status}
                  </Badge>
                  <span>
                    <span className="font-medium">{a.label}</span>
                    {a.value ? (
                      <span className={confirmed ? "text-emerald-800" : "text-amber-800"}>
                        {" "}
                        — {a.value}
                      </span>
                    ) : null}
                  </span>
                </li>
              );
            })}
          </ul>
        </div>
      </div>
    </div>
  );
}
