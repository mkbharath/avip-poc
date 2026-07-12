import { api } from "./client";
import type { Inspection, ReviewQueueItem } from "../types";

export async function lookupPart(partNumber: string) {
  return api.get<{
    id: string;
    part_number: string;
    revision: string;
    family_id: string;
    family: {
      id: string;
      name: string;
      display_name: string;
      material: string;
      surface_finish: string;
      capture_profile: { cameras: string[]; lighting: string };
    };
    description: string;
    material: string;
    surface_finish: string;
    supplier: string;
  }>(`/parts/${partNumber}`);
}

export async function createInspection(partNumber: string) {
  return api.post<{
    id: string;
    status: string;
    part_number: string;
    revision: string;
    family_id: string;
    started_at: string;
  }>("/inspections", { part_number: partNumber });
}

export async function simulateCapture(inspectionId: string) {
  return api.post<{
    inspection_id: string;
    status: string;
    images: Array<{
      id: string;
      camera_angle: string;
      file_url: string;
      thumbnail_url: string;
      quality_result: { passed: boolean; checks: Record<string, boolean>; failure_reason: string | null };
    }>;
    all_quality_passed: boolean;
  }>(`/inspections/${inspectionId}/capture`);
}

export async function runInspection(inspectionId: string) {
  return api.post<{
    inspection_id: string;
    status: string;
    decision: {
      result: "PASS" | "FAIL" | "REVIEW";
      fusion_rule: string;
      findings_count: number;
      confidence_summary: Record<string, unknown>;
    };
    findings: Array<{
      id: string;
      defect_class: string;
      approach: string;
      confidence: number;
      severity: string;
      bbox: { x: number; y: number; width: number; height: number } | null;
      heatmap_url: string | null;
      description: string;
    }>;
    findings_count: number;
  }>(`/inspections/${inspectionId}/inspect`);
}

export async function getInspection(inspectionId: string) {
  return api.get<Inspection>(`/inspections/${inspectionId}`);
}

export async function getReviewQueue() {
  return api.get<{ data: ReviewQueueItem[]; total_count: number }>("/review/queue");
}

export async function overrideDecision(
  inspectionId: string,
  payload: { new_decision: string; reason_code: string; comment: string; reviewer: string }
) {
  return api.post(`/review/${inspectionId}/override`, payload);
}

export async function confirmDecision(inspectionId: string) {
  return api.post(`/review/${inspectionId}/confirm`);
}
