import { api } from "./client";
import type {
  DraftTpi,
  TpiAuditRow,
  TpiInput,
  TpiInputRef,
  TpiPcbaDetail,
  TpiPcbaRow,
  TpiSection,
  TpiStatus,
} from "../types";

type Filters = Record<string, string>;

function buildQuery(params?: Filters): string {
  if (!params) return "";
  const query = new URLSearchParams(params).toString();
  return query ? `?${query}` : "";
}

// ===== Ingestion + processing =====

/**
 * Persist a PCBA's inputs. The backend returns the persisted inputs plus a
 * summary; callers typically only need the inputs, so the envelope's `data`
 * array is unwrapped.
 */
export async function ingestInputs(
  pcbaId: string,
  inputs: TpiInputRef[]
): Promise<TpiInput[]> {
  const res = await api.post<{
    data: TpiInput[];
    total_count: number;
    summary: Record<string, unknown>;
  }>(`/tpi/pcbas/${pcbaId}/inputs`, { inputs });
  return res.data;
}

/**
 * Upload a PCBA's own input files from the browser (real multipart intake).
 *
 * Distinct from {@link ingestInputs}, which references on-disk sample fixtures
 * by path: this posts the user's actual files as `multipart/form-data` to
 * `/tpi/pcbas/{id}/inputs/upload`. Each present file is appended under its
 * input-type field name so the backend can pair it with the right type.
 *
 * The shared `api` client forces a JSON `Content-Type`, which would break the
 * multipart boundary, so this uses `fetch` directly against the same `/api/v1`
 * base and deliberately does NOT set `Content-Type` — the browser sets the
 * multipart boundary itself. Returns the same `{data, total_count, summary}`
 * envelope as the JSON endpoint, unwrapped to the persisted inputs.
 */
export async function uploadInputs(
  pcbaId: string,
  files: {
    testing_procedure?: File;
    operating_procedure?: File;
    circuit_diagram?: File;
    drawing?: File;
  }
): Promise<TpiInput[]> {
  const form = new FormData();
  for (const [field, file] of Object.entries(files)) {
    if (file) form.append(field, file, file.name);
  }

  const response = await fetch(`/api/v1/tpi/pcbas/${pcbaId}/inputs/upload`, {
    method: "POST",
    body: form, // No Content-Type header: the browser sets the multipart boundary.
  });

  if (!response.ok) {
    const error = await response
      .json()
      .catch(() => ({ detail: "Unknown error" }));
    throw new Error(error.detail || `HTTP ${response.status}`);
  }

  const res = (await response.json()) as {
    data: TpiInput[];
    total_count: number;
    summary: Record<string, unknown>;
  };
  return res.data;
}

/**
 * Run extraction → mapping → generation for a PCBA, returning the draft.
 *
 * `provider` optionally overrides the run's multimodal provider for this call
 * only (`"mock"` | `"openai"`); when omitted the backend uses its configured
 * default. Appended as a `?provider=` query param when given.
 */
export async function processPcba(
  pcbaId: string,
  provider?: "mock" | "openai"
): Promise<DraftTpi> {
  const query = provider ? `?provider=${encodeURIComponent(provider)}` : "";
  return api.post<DraftTpi>(`/tpi/pcbas/${pcbaId}/process${query}`);
}

// ===== Reads =====

/** List all PCBAs for the monitor view (unwraps the `{data}` envelope). */
export async function listPcbas(): Promise<TpiPcbaRow[]> {
  const res = await api.get<{ data: TpiPcbaRow[]; total_count: number }>(
    "/tpi/pcbas"
  );
  return res.data;
}

/** Fetch a single PCBA with its inputs and current draft. */
export async function getPcbaDetail(pcbaId: string): Promise<TpiPcbaDetail> {
  return api.get<TpiPcbaDetail>(`/tpi/pcbas/${pcbaId}`);
}

/** List drafts, optionally filtered by review state (unwraps `{data}`). */
export async function listDrafts(status?: string): Promise<DraftTpi[]> {
  const filters: Filters | undefined =
    status !== undefined ? { status } : undefined;
  const res = await api.get<{ data: DraftTpi[]; total_count: number }>(
    `/tpi/drafts${buildQuery(filters)}`
  );
  return res.data;
}

/** Fetch a single PCBA's draft (backend returns 404 when none exists). */
export async function getDraft(pcbaId: string): Promise<DraftTpi> {
  return api.get<DraftTpi>(`/tpi/drafts/${pcbaId}`);
}

/** List finalized TPIs only (unwraps the `{data}` envelope). */
export async function listFinal(): Promise<DraftTpi[]> {
  const res = await api.get<{ data: DraftTpi[]; total_count: number }>(
    "/tpi/final"
  );
  return res.data;
}

/** Fetch the review-audit trail for a PCBA (unwraps the `{data}` envelope). */
export async function getAudit(pcbaId: string): Promise<TpiAuditRow[]> {
  const res = await api.get<{ data: TpiAuditRow[]; total_count: number }>(
    `/tpi/audit/${pcbaId}`
  );
  return res.data;
}

// ===== Finalize =====

/**
 * Finalize a draft: persist the reviewer's corrected sections as the final TPI
 * and write one audit row. Returns the finalized draft.
 */
export async function finalizeDraft(
  pcbaId: string,
  body: { reviewer: string; note?: string; corrected_sections: TpiSection[] }
): Promise<DraftTpi> {
  return api.post<DraftTpi>(`/tpi/drafts/${pcbaId}/finalize`, body);
}

// ===== Status =====

/** Pipeline/config status plus any unresolved `[CONFIRM]` items for the banner. */
export async function getStatus(): Promise<TpiStatus> {
  return api.get<TpiStatus>("/tpi/status");
}

// ===== Export =====

/**
 * URL for the finalized-TPI PDF export. Mirrors the source-comparison CSV
 * export (`exportReportUrl`): return the absolute `/api/v1` URL so the UI can
 * link or download it directly rather than fetching a blob.
 */
export function exportFinalUrl(pcbaId: string): string {
  return `/api/v1/tpi/final/${pcbaId}/export`;
}
