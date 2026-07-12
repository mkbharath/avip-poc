import { api } from "./client";
import type {
  InspectionDashboardData,
  DefectDashboardData,
  SupplierDashboardData,
  AIPerformanceDashboardData,
} from "../types";

export async function getInspectionDashboard() {
  return api.get<InspectionDashboardData>("/dashboard/inspection");
}

export async function getDefectDashboard() {
  return api.get<DefectDashboardData>("/dashboard/defects");
}

export async function getSupplierDashboard() {
  return api.get<SupplierDashboardData>("/dashboard/suppliers");
}

export async function getAIPerformanceDashboard() {
  return api.get<AIPerformanceDashboardData>("/dashboard/ai-performance");
}
