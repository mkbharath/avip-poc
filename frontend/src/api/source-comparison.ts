import { api } from "./client";
import type {
  SCAlignedGroup,
  SCComparisonConfig,
  SCConfigAuditPage,
  SCDiscrepancy,
  SCFieldConfig,
  SCGroup,
  SCRejectedRecord,
  SCReportHeader,
  SCReportRow,
  SCStatus,
  SCSupplierSummaryRow,
  SCThresholdOverride,
} from "../types";

type Filters = Record<string, string>;

interface Pagination {
  limit?: number;
  offset?: number;
}

/** Shape returned by paginated list endpoints. */
export interface Paginated<T> {
  data: T[];
  total_count: number;
  limit: number;
  offset: number;
}

function buildQuery(params?: Filters): string {
  if (!params) return "";
  const query = new URLSearchParams(params).toString();
  return query ? `?${query}` : "";
}

/** Merge optional pagination values into a plain string filter map. */
function withPagination(filters?: Filters, pagination?: Pagination): Filters {
  const merged: Filters = { ...(filters ?? {}) };
  if (pagination?.limit !== undefined) merged.limit = String(pagination.limit);
  if (pagination?.offset !== undefined) merged.offset = String(pagination.offset);
  return merged;
}

// ===== Status =====

export async function getStatus() {
  return api.get<SCStatus>("/source-comparison/status");
}

// ===== Rejected records =====

export async function getRejected() {
  return api.get<{ data: SCRejectedRecord[]; total_count: number }>(
    "/source-comparison/rejected"
  );
}

// ===== Aligned groups =====

export async function listGroups(filters?: Filters) {
  return api.get<{ data: SCAlignedGroup[]; total_count: number }>(
    `/source-comparison/groups${buildQuery(filters)}`
  );
}

export async function getGroup(id: string) {
  return api.get<SCAlignedGroup>(`/source-comparison/groups/${id}`);
}

// ===== Review =====

export async function getReviewQueue(params?: Pagination) {
  return api.get<Paginated<SCDiscrepancy>>(
    `/source-comparison/review/queue${buildQuery(withPagination(undefined, params))}`
  );
}

/**
 * Grouped review queue: pending discrepancies bucketed by part/lot GROUP.
 * `total_count` on the response is the number of GROUPS, and pagination
 * (limit/offset) is applied at the GROUP level. Backend default limit 50,
 * max 200.
 */
export async function getReviewQueueGrouped(params?: Pagination) {
  return api.get<Paginated<SCGroup>>(
    `/source-comparison/review/queue-grouped${buildQuery(
      withPagination(undefined, params)
    )}`
  );
}

export async function getDiscrepancy(id: string) {
  return api.get<SCDiscrepancy>(`/source-comparison/review/${id}`);
}

export async function decideDiscrepancy(
  id: string,
  payload: { decision: "confirmed" | "dismissed"; reviewer: string; note?: string }
) {
  return api.post<SCDiscrepancy>(`/source-comparison/review/${id}/decide`, payload);
}

export async function decideBulk(payload: {
  discrepancy_ids: string[];
  decision: "confirmed" | "dismissed";
  reviewer: string;
  note?: string;
}) {
  return api.post<{ updated: number; not_found: string[]; decision: string }>(
    "/source-comparison/review/decide-bulk",
    payload
  );
}

/**
 * Return a decided (confirmed or dismissed) discrepancy to `pending`. The
 * backend reuses the decide request shape but ignores `decision` — reopen
 * always sets the discrepancy back to pending and writes a "reopened" audit
 * row. Callers should invalidate the ["sc","report"] and ["sc","review"]
 * queries afterwards so the report and pending queue refresh.
 */
export async function reopenDiscrepancy(
  id: string,
  payload: { reviewer: string; note?: string }
) {
  return api.post<SCDiscrepancy>(`/source-comparison/review/${id}/reopen`, payload);
}

// ===== Ingestion simulator control =====

export async function startSimulator() {
  return api.post<{ running: boolean }>("/source-comparison/simulator/start");
}

export async function stopSimulator() {
  return api.post<{ running: boolean }>("/source-comparison/simulator/stop");
}

// ===== Report =====

/**
 * Fetch a page of the discrepancy report. `filters` is a plain string map and
 * supports `part_number`, `lot_number`, `source`, `field`, `provenance`,
 * `review_state`, and `supplier` (the part's supplier, joined from the parts
 * table and matched case-insensitively on the backend).
 */
export async function getReport(filters?: Filters, pagination?: Pagination) {
  return api.get<Paginated<SCReportRow>>(
    `/source-comparison/report${buildQuery(withPagination(filters, pagination))}`
  );
}

export async function getReportHeader() {
  return api.get<SCReportHeader>("/source-comparison/report/header");
}

/**
 * Fetch the confirmed-only discrepancy rollup grouped by supplier. Accepts the
 * same optional filters as `getReport` (part_number, lot_number, source, field,
 * provenance) — a `supplier` filter is intentionally ignored by the backend
 * since the rollup surfaces every supplier. Returns rows sorted by
 * discrepancy_count descending.
 */
export async function getSupplierSummary(filters?: Filters) {
  return api.get<{ data: SCSupplierSummaryRow[]; total_count: number }>(
    `/source-comparison/report/supplier-summary${buildQuery(filters)}`
  );
}

export function exportReportUrl(filters?: Filters): string {
  const params = new URLSearchParams({ format: "csv", ...(filters ?? {}) });
  return `/api/v1/source-comparison/report/export?${params.toString()}`;
}

// ===== Threshold configuration =====

/** Fetch the per-field comparison configuration (defaults + scope). */
export async function getComparisonConfig() {
  return api.get<SCComparisonConfig>("/source-comparison/config");
}

/** Update a field's default threshold and/or in-scope flag. */
export async function updateFieldDefault(
  fieldName: string,
  body: { threshold?: number; in_scope?: boolean; changed_by: string; note?: string }
) {
  return api.put<SCFieldConfig>(
    `/source-comparison/config/field/${encodeURIComponent(fieldName)}`,
    body
  );
}

/** List part-number threshold overrides, optionally filtered by part number. */
export async function listOverrides(partNumber?: string): Promise<SCThresholdOverride[]> {
  const filters: Filters | undefined =
    partNumber !== undefined ? { part_number: partNumber } : undefined;
  const res = await api.get<{ data: SCThresholdOverride[]; total_count: number }>(
    `/source-comparison/config/overrides${buildQuery(filters)}`
  );
  return res.data;
}

/** Create or update a part-number threshold override. */
export async function setOverride(body: {
  part_number: string;
  field_name: string;
  threshold: number;
  changed_by: string;
  note?: string;
}) {
  return api.post<SCThresholdOverride>("/source-comparison/config/overrides", body);
}

/** Delete a part-number threshold override. */
export async function deleteOverride(params: {
  part_number: string;
  field_name: string;
  changed_by: string;
  note?: string;
}) {
  const filters: Filters = {
    part_number: params.part_number,
    field_name: params.field_name,
    changed_by: params.changed_by,
  };
  if (params.note !== undefined) filters.note = params.note;
  return api.delete<{ deleted: boolean }>(
    `/source-comparison/config/overrides${buildQuery(filters)}`
  );
}

/** Fetch the paginated configuration audit log. */
export async function getConfigAudit(limit?: number, offset?: number) {
  return api.get<SCConfigAuditPage>(
    `/source-comparison/config/audit${buildQuery(
      withPagination(undefined, { limit, offset })
    )}`
  );
}
