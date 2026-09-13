import { api } from "./client";
import type {
  SCAlignedGroup,
  SCDiscrepancy,
  SCRejectedRecord,
  SCReportHeader,
  SCReportRow,
  SCStatus,
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

// ===== Ingestion simulator control =====

export async function startSimulator() {
  return api.post<{ running: boolean }>("/source-comparison/simulator/start");
}

export async function stopSimulator() {
  return api.post<{ running: boolean }>("/source-comparison/simulator/stop");
}

// ===== Report =====

export async function getReport(filters?: Filters, pagination?: Pagination) {
  return api.get<Paginated<SCReportRow>>(
    `/source-comparison/report${buildQuery(withPagination(filters, pagination))}`
  );
}

export async function getReportHeader() {
  return api.get<SCReportHeader>("/source-comparison/report/header");
}

export function exportReportUrl(filters?: Filters): string {
  const params = new URLSearchParams({ format: "csv", ...(filters ?? {}) });
  return `/api/v1/source-comparison/report/export?${params.toString()}`;
}
