import { api } from "./client";
import type { DemoScenario } from "../types";

export async function getScenarios() {
  return api.get<{ data: DemoScenario[]; total_count: number }>("/demo/scenarios");
}

export async function runScenario(scenarioId: string) {
  return api.post<{
    scenario: DemoScenario;
    inspection_id: string;
    result: {
      inspection_id: string;
      status: string;
      decision: { result: string; fusion_rule: string; findings_count: number };
      findings_count: number;
    };
  }>(`/demo/scenarios/${scenarioId}/run`);
}

export async function resetDemo() {
  return api.post<{ status: string; message: string }>("/demo/reset");
}
