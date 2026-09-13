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

function buildQuery(params?: Filters): string {
  if (!params) return "";
  const query = new URLSearchParams(params).toString();
  return query ? `?${query}` : "";
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

export async function getReviewQueue() {
  return api.get<{ data: SCDiscrepancy[]; total_count: number }>(
    "/source-comparison/review/queue"
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

// ===== Report =====

export async function getReport(filters?: Filters) {
  return api.get<{ data: SCReportRow[]; total_count: number }>(
    `/source-comparison/report${buildQuery(filters)}`
  );
}

export async function getReportHeader() {
  return api.get<SCReportHeader>("/source-comparison/report/header");
}

export function exportReportUrl(filters?: Filters): string {
  const params = new URLSearchParams({ format: "csv", ...(filters ?? {}) });
  return `/api/v1/source-comparison/report/export?${params.toString()}`;
}
