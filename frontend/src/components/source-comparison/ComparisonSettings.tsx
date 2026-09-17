import { useMemo, useState } from "react";
import { keepPreviousData, useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import {
  ChevronLeft,
  ChevronRight,
  Loader2,
  Plus,
  SlidersHorizontal,
  Trash2,
} from "lucide-react";
import {
  deleteOverride,
  getComparisonConfig,
  getConfigAudit,
  listOverrides,
  setOverride,
  updateFieldDefault,
} from "../../api/source-comparison";
import { Button } from "@/components/ui/button";
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
  SCConfigAuditRow,
  SCFieldConfig,
  SCThresholdOverride,
} from "../../types";
import { humanizeField } from "./table-parts";

// Portal-wide auth is deferred, so every configuration write is attributed to a
// reviewer identity captured at the top of the page. This is passed as
// `changed_by` on every save. Defaults to a sensible placeholder.
const DEFAULT_REVIEWER = "IQA Inspector";

const AUDIT_PAGE_SIZE = 20;

// Friendly labels for the field types (mirrors the language used elsewhere in
// the Source Comparison feature).
const FIELD_TYPE_LABELS: Record<string, string> = {
  numeric: "Measurement",
  categorical: "Category",
  identifier: "Identifier",
  free_text: "Free text",
};

// Humanized labels for the audit change types.
const CHANGE_TYPE_LABELS: Record<SCConfigAuditRow["change_type"], string> = {
  field_default: "Field threshold",
  field_scope: "Field scope",
  part_override_set: "Override set",
  part_override_delete: "Override removed",
};

const uppercaseHeader =
  "px-4 py-3 text-xs font-semibold uppercase tracking-wider text-slate-500";

export function ComparisonSettings() {
  const [reviewer, setReviewer] = useState(DEFAULT_REVIEWER);
  const reviewerTrimmed = reviewer.trim();
  const reviewerMissing = reviewerTrimmed.length === 0;

  const { data: config, isLoading: configLoading } = useQuery({
    queryKey: ["sc", "config"],
    queryFn: getComparisonConfig,
  });

  const fields = config?.fields ?? [];
  const numericFields = useMemo(
    () => fields.filter((f) => f.type === "numeric"),
    [fields]
  );

  return (
    <div className="p-6 space-y-6">
      {/* Page header */}
      <div className="flex items-start justify-between gap-4">
        <div>
          <h1 className="flex items-center gap-2 text-xl font-bold text-foreground tracking-tight">
            <SlidersHorizontal className="w-5 h-5 text-slate-500" />
            Comparison Settings
          </h1>
          <p className="text-sm text-slate-600 mt-0.5">
            These tolerances decide which differences across LAIR, FAIR and SHQ
            get flagged for review. Tighten a threshold to catch smaller
            variations; widen it to reduce noise.
          </p>
        </div>
      </div>

      {/* Reviewer identity */}
      <Card className="rounded-xl border border-slate-200 p-4 shadow-sm">
        <div className="flex flex-col gap-1.5 sm:max-w-md">
          <label className="text-xs font-semibold uppercase tracking-wider text-slate-500">
            Reviewer identity
          </label>
          <Input
            value={reviewer}
            onChange={(e) => setReviewer(e.target.value)}
            placeholder="Your name or role"
            className={reviewerMissing ? "border-red-300 focus-visible:ring-red-200" : ""}
          />
          <p className="text-xs text-slate-500">
            Portal-wide sign-in is not wired up yet, so every change is recorded
            against this name. Required before saving.
          </p>
          {reviewerMissing && (
            <p className="text-xs font-medium text-red-600">
              Enter a reviewer identity to enable saving.
            </p>
          )}
        </div>
      </Card>

      {/* Field Defaults */}
      <FieldDefaultsSection
        fields={fields}
        loading={configLoading}
        reviewer={reviewerTrimmed}
        reviewerMissing={reviewerMissing}
      />

      {/* Per-Part Overrides */}
      <OverridesSection
        numericFields={numericFields}
        reviewer={reviewerTrimmed}
        reviewerMissing={reviewerMissing}
      />

      {/* Change History */}
      <ChangeHistorySection />
    </div>
  );
}

// ---------------------------------------------------------------------------
// Field Defaults
// ---------------------------------------------------------------------------

function FieldDefaultsSection({
  fields,
  loading,
  reviewer,
  reviewerMissing,
}: {
  fields: SCFieldConfig[];
  loading: boolean;
  reviewer: string;
  reviewerMissing: boolean;
}) {
  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Field defaults</h2>
        <p className="text-sm text-slate-600">
          The default tolerance and scope applied to every part. Numeric fields
          use a threshold; other field types are compared exactly.
        </p>
      </div>

      <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
              <TableHead className={uppercaseHeader}>Field</TableHead>
              <TableHead className={uppercaseHeader}>Type</TableHead>
              <TableHead className={`${uppercaseHeader} w-[140px]`}>In scope</TableHead>
              <TableHead className={`${uppercaseHeader} w-[200px]`}>Threshold</TableHead>
              <TableHead className={`${uppercaseHeader} w-[120px] text-right`}>
                Action
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-slate-100">
            {loading ? (
              <TableRow>
                <TableCell colSpan={5} className="px-4 py-10 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-300" />
                </TableCell>
              </TableRow>
            ) : fields.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={5}
                  className="px-4 py-10 text-center text-sm text-slate-500"
                >
                  No fields configured yet.
                </TableCell>
              </TableRow>
            ) : (
              fields.map((field) => (
                <FieldDefaultRow
                  key={field.field_name}
                  field={field}
                  reviewer={reviewer}
                  reviewerMissing={reviewerMissing}
                />
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </section>
  );
}

function FieldDefaultRow({
  field,
  reviewer,
  reviewerMissing,
}: {
  field: SCFieldConfig;
  reviewer: string;
  reviewerMissing: boolean;
}) {
  const queryClient = useQueryClient();
  const isNumeric = field.type === "numeric";

  const [inScope, setInScope] = useState(field.in_scope);
  const [threshold, setThreshold] = useState(
    field.threshold != null ? String(field.threshold) : ""
  );

  const initialThreshold = field.threshold != null ? String(field.threshold) : "";
  const dirty =
    inScope !== field.in_scope || (isNumeric && threshold !== initialThreshold);

  const mutation = useMutation({
    mutationFn: () => {
      const body: {
        threshold?: number;
        in_scope?: boolean;
        changed_by: string;
        note?: string;
      } = { changed_by: reviewer };
      if (inScope !== field.in_scope) body.in_scope = inScope;
      if (isNumeric && threshold !== initialThreshold) {
        body.threshold = threshold.trim() === "" ? 0 : Number(threshold);
      }
      return updateFieldDefault(field.field_name, body);
    },
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sc", "config"] });
      queryClient.invalidateQueries({ queryKey: ["sc", "config-audit"] });
    },
  });

  const errorMessage = mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <TableRow className="border-0 align-top transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3">
        <span className="text-sm font-medium text-slate-900">
          {humanizeField(field.field_name)}
        </span>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-slate-600">
        {FIELD_TYPE_LABELS[field.type] ?? field.type}
      </TableCell>
      <TableCell className="px-4 py-3">
        <ScopeToggle checked={inScope} onChange={setInScope} />
      </TableCell>
      <TableCell className="px-4 py-3">
        {isNumeric ? (
          <Input
            type="number"
            step="any"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
            className="w-[140px]"
            placeholder="0"
          />
        ) : (
          <span className="text-sm text-slate-500">—</span>
        )}
      </TableCell>
      <TableCell className="px-4 py-3 text-right">
        <div className="flex flex-col items-end gap-1">
          <Button
            size="sm"
            variant={dirty ? "default" : "outline"}
            disabled={!dirty || reviewerMissing || mutation.isPending}
            onClick={() => mutation.mutate()}
          >
            {mutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              "Save"
            )}
          </Button>
          {errorMessage && (
            <span className="max-w-[220px] text-right text-xs font-medium text-red-600">
              {errorMessage}
            </span>
          )}
          {mutation.isSuccess && !dirty && !errorMessage && (
            <span className="text-xs font-medium text-emerald-600">Saved</span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// A small, dependency-free in-scope toggle styled to match the slate palette.
function ScopeToggle({
  checked,
  onChange,
}: {
  checked: boolean;
  onChange: (next: boolean) => void;
}) {
  return (
    <button
      type="button"
      role="switch"
      aria-checked={checked}
      onClick={() => onChange(!checked)}
      className={`relative inline-flex h-5 w-9 shrink-0 items-center rounded-full transition-colors ${
        checked ? "bg-lam-green" : "bg-slate-300"
      }`}
    >
      <span
        className={`inline-block h-4 w-4 transform rounded-full bg-white shadow transition-transform ${
          checked ? "translate-x-4" : "translate-x-0.5"
        }`}
      />
    </button>
  );
}

// ---------------------------------------------------------------------------
// Per-Part Overrides
// ---------------------------------------------------------------------------

function OverridesSection({
  numericFields,
  reviewer,
  reviewerMissing,
}: {
  numericFields: SCFieldConfig[];
  reviewer: string;
  reviewerMissing: boolean;
}) {
  const queryClient = useQueryClient();

  const { data: overrides, isLoading } = useQuery({
    queryKey: ["sc", "config-overrides"],
    queryFn: () => listOverrides(),
  });

  const invalidateOverrides = () => {
    queryClient.invalidateQueries({ queryKey: ["sc", "config-overrides"] });
    queryClient.invalidateQueries({ queryKey: ["sc", "config-audit"] });
  };

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Per-part overrides</h2>
        <p className="text-sm text-slate-600">
          Give a specific part number a tighter or looser numeric tolerance than
          the field default. Overrides apply only to that part.
        </p>
      </div>

      <AddOverrideForm
        numericFields={numericFields}
        reviewer={reviewer}
        reviewerMissing={reviewerMissing}
        onSaved={invalidateOverrides}
      />

      <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
              <TableHead className={uppercaseHeader}>Part number</TableHead>
              <TableHead className={uppercaseHeader}>Field</TableHead>
              <TableHead className={`${uppercaseHeader} w-[160px]`}>Threshold</TableHead>
              <TableHead className={`${uppercaseHeader} w-[120px] text-right`}>
                Action
              </TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-slate-100">
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={4} className="px-4 py-10 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-300" />
                </TableCell>
              </TableRow>
            ) : (overrides ?? []).length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={4}
                  className="px-4 py-10 text-center text-sm text-slate-500"
                >
                  No overrides yet. Add one above to tune a single part.
                </TableCell>
              </TableRow>
            ) : (
              (overrides ?? []).map((ov) => (
                <OverrideRow
                  key={`${ov.part_number}::${ov.field_name}`}
                  override={ov}
                  reviewer={reviewer}
                  reviewerMissing={reviewerMissing}
                  onDeleted={invalidateOverrides}
                />
              ))
            )}
          </TableBody>
        </Table>
      </Card>
    </section>
  );
}

function AddOverrideForm({
  numericFields,
  reviewer,
  reviewerMissing,
  onSaved,
}: {
  numericFields: SCFieldConfig[];
  reviewer: string;
  reviewerMissing: boolean;
  onSaved: () => void;
}) {
  const [partNumber, setPartNumber] = useState("");
  const [fieldName, setFieldName] = useState("");
  const [threshold, setThreshold] = useState("");

  const mutation = useMutation({
    mutationFn: () =>
      setOverride({
        part_number: partNumber.trim(),
        field_name: fieldName,
        threshold: threshold.trim() === "" ? 0 : Number(threshold),
        changed_by: reviewer,
      }),
    onSuccess: () => {
      setPartNumber("");
      setFieldName("");
      setThreshold("");
      onSaved();
    },
  });

  const canSubmit =
    partNumber.trim() !== "" &&
    fieldName !== "" &&
    threshold.trim() !== "" &&
    !reviewerMissing &&
    !mutation.isPending;

  const errorMessage = mutation.error instanceof Error ? mutation.error.message : null;

  return (
    <Card className="rounded-xl border border-slate-200 p-4 shadow-sm">
      <div className="flex flex-wrap items-end gap-3">
        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Part number</label>
          <Input
            className="w-[180px]"
            placeholder="e.g. 853-000123"
            value={partNumber}
            onChange={(e) => setPartNumber(e.target.value)}
          />
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Field</label>
          <Select value={fieldName} onValueChange={(v) => setFieldName(v ?? "")}>
            <SelectTrigger className="w-[200px]">
              <SelectValue placeholder="Select field" />
            </SelectTrigger>
            <SelectContent>
              {numericFields.map((f) => (
                <SelectItem key={f.field_name} value={f.field_name}>
                  {humanizeField(f.field_name)}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        </div>

        <div className="space-y-1">
          <label className="text-xs font-medium text-muted-foreground">Threshold</label>
          <Input
            type="number"
            step="any"
            className="w-[140px]"
            placeholder="0"
            value={threshold}
            onChange={(e) => setThreshold(e.target.value)}
          />
        </div>

        <Button disabled={!canSubmit} onClick={() => mutation.mutate()}>
          {mutation.isPending ? (
            <Loader2 className="mr-1.5 h-4 w-4 animate-spin" />
          ) : (
            <Plus className="mr-1.5" />
          )}
          Add override
        </Button>
      </div>
      {errorMessage && (
        <p className="mt-2 text-xs font-medium text-red-600">{errorMessage}</p>
      )}
    </Card>
  );
}

function OverrideRow({
  override,
  reviewer,
  reviewerMissing,
  onDeleted,
}: {
  override: SCThresholdOverride;
  reviewer: string;
  reviewerMissing: boolean;
  onDeleted: () => void;
}) {
  const mutation = useMutation({
    mutationFn: () =>
      deleteOverride({
        part_number: override.part_number,
        field_name: override.field_name,
        changed_by: reviewer,
      }),
    onSuccess: onDeleted,
  });

  const errorMessage = mutation.error instanceof Error ? mutation.error.message : null;

  const handleDelete = () => {
    const ok = window.confirm(
      `Remove the ${humanizeField(override.field_name)} override for ${override.part_number}? The field default will apply again.`
    );
    if (ok) mutation.mutate();
  };

  return (
    <TableRow className="border-0 transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3">
        <span className="font-mono text-sm font-bold text-slate-900">
          {override.part_number}
        </span>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-slate-700">
        {humanizeField(override.field_name)}
      </TableCell>
      <TableCell className="px-4 py-3 font-mono text-sm tabular-nums text-slate-900">
        {override.threshold}
      </TableCell>
      <TableCell className="px-4 py-3 text-right">
        <div className="flex flex-col items-end gap-1">
          <Button
            size="sm"
            variant="outline"
            disabled={reviewerMissing || mutation.isPending}
            onClick={handleDelete}
            className="text-red-600 hover:text-red-700"
          >
            {mutation.isPending ? (
              <Loader2 className="h-3.5 w-3.5 animate-spin" />
            ) : (
              <>
                <Trash2 className="mr-1 h-3.5 w-3.5" />
                Delete
              </>
            )}
          </Button>
          {errorMessage && (
            <span className="max-w-[220px] text-right text-xs font-medium text-red-600">
              {errorMessage}
            </span>
          )}
        </div>
      </TableCell>
    </TableRow>
  );
}

// ---------------------------------------------------------------------------
// Change History
// ---------------------------------------------------------------------------

function ChangeHistorySection() {
  const [page, setPage] = useState(0);

  const { data, isLoading } = useQuery({
    queryKey: ["sc", "config-audit", page],
    queryFn: () => getConfigAudit(AUDIT_PAGE_SIZE, page * AUDIT_PAGE_SIZE),
    placeholderData: keepPreviousData,
  });

  const rows = data?.data ?? [];
  const totalCount = data?.total_count ?? 0;
  const rangeStart = totalCount === 0 ? 0 : page * AUDIT_PAGE_SIZE + 1;
  const rangeEnd = page * AUDIT_PAGE_SIZE + rows.length;
  const canPrev = page > 0;
  const canNext = (page + 1) * AUDIT_PAGE_SIZE < totalCount;

  return (
    <section className="space-y-3">
      <div>
        <h2 className="text-base font-semibold text-slate-900">Change history</h2>
        <p className="text-sm text-slate-600">
          Every threshold, scope and override change, newest first.
        </p>
      </div>

      <Card className="overflow-hidden rounded-xl border border-slate-200 p-0 shadow-sm">
        <Table>
          <TableHeader>
            <TableRow className="border-b border-slate-200 bg-slate-50 hover:bg-slate-50">
              <TableHead className={`${uppercaseHeader} w-[170px]`}>When</TableHead>
              <TableHead className={`${uppercaseHeader} w-[150px]`}>Change</TableHead>
              <TableHead className={uppercaseHeader}>Field / Part</TableHead>
              <TableHead className={uppercaseHeader}>Old → New</TableHead>
              <TableHead className={`${uppercaseHeader} w-[140px]`}>Changed by</TableHead>
              <TableHead className={uppercaseHeader}>Note</TableHead>
            </TableRow>
          </TableHeader>
          <TableBody className="divide-y divide-slate-100">
            {isLoading ? (
              <TableRow>
                <TableCell colSpan={6} className="px-4 py-10 text-center">
                  <Loader2 className="mx-auto h-6 w-6 animate-spin text-slate-300" />
                </TableCell>
              </TableRow>
            ) : rows.length === 0 ? (
              <TableRow>
                <TableCell
                  colSpan={6}
                  className="px-4 py-10 text-center text-sm text-slate-500"
                >
                  No configuration changes recorded yet.
                </TableCell>
              </TableRow>
            ) : (
              rows.map((row) => <AuditRow key={row.id} row={row} />)
            )}
          </TableBody>
        </Table>
        <div className="flex items-center justify-between border-t border-slate-200 bg-slate-50 px-4 py-3">
          <p className="text-xs text-slate-600">
            {totalCount === 0 ? (
              "No entries"
            ) : (
              <>
                Showing <span className="font-semibold text-slate-900">{rangeStart}</span>–
                <span className="font-semibold text-slate-900">{rangeEnd}</span> of{" "}
                <span className="font-semibold text-slate-900">{totalCount}</span>
              </>
            )}
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
    </section>
  );
}

function AuditRow({ row }: { row: SCConfigAuditRow }) {
  const target = row.field_name
    ? humanizeField(row.field_name)
    : row.part_number ?? "—";
  const partSuffix =
    row.field_name && row.part_number ? (
      <span className="font-mono text-xs text-slate-500"> · {row.part_number}</span>
    ) : null;

  return (
    <TableRow className="border-0 align-top transition-colors hover:bg-slate-50/70">
      <TableCell className="px-4 py-3 text-xs text-slate-600 tabular-nums">
        {formatTimestamp(row.changed_at)}
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-slate-700">
        {CHANGE_TYPE_LABELS[row.change_type] ?? row.change_type}
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-slate-900">
        {target}
        {partSuffix}
      </TableCell>
      <TableCell className="px-4 py-3 text-sm">
        <span className="font-mono text-slate-500">{row.old_value ?? "—"}</span>
        <span className="mx-1.5 text-slate-500">→</span>
        <span className="font-mono font-medium text-slate-900">
          {row.new_value ?? "—"}
        </span>
      </TableCell>
      <TableCell className="px-4 py-3 text-sm text-slate-700">
        {row.changed_by}
      </TableCell>
      <TableCell className="px-4 py-3 text-xs text-slate-500">
        {row.note ?? "—"}
      </TableCell>
    </TableRow>
  );
}

function formatTimestamp(iso: string): string {
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleString(undefined, {
    year: "numeric",
    month: "short",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}
