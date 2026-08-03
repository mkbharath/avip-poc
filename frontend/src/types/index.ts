// ===== Part Models =====

export interface PartFamily {
  id: string;
  name: string;
  display_name: string;
  material: string;
  surface_finish: string;
  thresholds: FamilyThresholds;
}

export interface FamilyThresholds {
  confidence_high: number;
  confidence_low: number;
  severity_threshold: string;
  max_findings_pass: number;
}

export interface Part {
  id: string;
  part_number: string;
  revision: string;
  family_id: string;
  family: PartFamily;
  description: string;
  material: string;
  surface_finish: string;
  supplier: string;
  drawing_url: string | null;
  placement_guide_url: string | null;
}

// ===== Inspection Models =====

export type InspectionStatus =
  | "identified"
  | "capturing"
  | "inspecting"
  | "passed"
  | "failed"
  | "in_review"
  | "overridden";

export type DecisionResult = "PASS" | "FAIL" | "REVIEW";

export type Approach = "rule" | "golden" | "model" | "anomaly";

export type Severity = "minor" | "major" | "critical";

export interface BoundingBox {
  x: number;
  y: number;
  width: number;
  height: number;
}

export interface Finding {
  id: string;
  defect_class: string;
  approach: Approach;
  confidence: number;
  severity: Severity;
  bbox: BoundingBox | null;
  mask_url: string | null;
  heatmap_url: string | null;
  description: string;
  image_id: string | null;
}

export interface Decision {
  result: DecisionResult;
  fusion_rule: string;
  findings_count: number;
  confidence_summary: Record<string, number>;
}

export interface InspectionImage {
  id: string;
  camera_angle: string;
  file_url: string;
  thumbnail_url: string;
  quality_result: ImageQualityResult;
}

export interface ImageQualityResult {
  passed: boolean;
  checks: Record<string, boolean>;
  failure_reason: string | null;
}

export interface Override {
  id: string;
  old_decision: DecisionResult;
  new_decision: DecisionResult;
  reason_code: string;
  comment: string;
  reviewer: string;
  created_at: string;
}

export interface Inspection {
  id: string;
  part: Part;
  status: InspectionStatus;
  decision: Decision | null;
  images: InspectionImage[];
  findings: Finding[];
  override: Override | null;
  certificate_id: string | null;
  started_at: string;
  decided_at: string | null;
  scenario_id: string | null;
}

// ===== Review Queue =====

export interface ReviewQueueItem {
  id: string;
  part_number: string;
  family_name: string;
  supplier: string;
  decision: DecisionResult;
  defect_classes: string[];
  confidence_band: string;
  age_seconds: number;
  priority: number;
  started_at: string;
}

// ===== Dashboard Models =====

export interface CycleTimeBucket {
  range: string;
  count: number;
}

export interface InspectionDashboardData {
  today_count: number;
  pass_rate: number;
  avg_cycle_time_seconds: number;
  queue_depth: number;
  cycle_time_distribution?: CycleTimeBucket[];
  stations: StationStatus[];
  recent_decisions: RecentDecision[];
}

export interface StationStatus {
  id: string;
  name: string;
  status: "active" | "idle" | "offline";
  current_part: string | null;
  parts_per_hour: number;
}

export interface RecentDecision {
  inspection_id: string;
  part_number: string;
  decision: DecisionResult;
  timestamp: string;
}

export interface DefectDashboardData {
  pareto: DefectCount[];
  trends: DefectTrend[];
  severity_distribution: SeverityCount[];
  family_heatmap: FamilyDefectDensity[];
}

export interface DefectCount {
  defect_class: string;
  count: number;
}

export interface DefectTrend {
  date: string;
  defect_class: string;
  count: number;
}

export interface SeverityCount {
  severity: Severity;
  count: number;
}

export interface FamilyDefectDensity {
  family: string;
  density: number;
  top_defect: string;
}

export interface SupplierDashboardData {
  suppliers: SupplierQuality[];
}

export interface SupplierQuality {
  name: string;
  dppm: number;
  trend: "up" | "down" | "stable";
  volume: number;
  top_defect: string;
  threshold_breached: boolean;
}

export interface AIPerformanceDashboardData {
  accuracy: number;
  fpr: number;
  fnr: number;
  fpr_trend: TrendPoint[];
  fnr_trend: TrendPoint[];
  confidence_histogram: ConfidenceBucket[];
  override_by_class: OverrideRate[];
  model_info: ModelInfo;
}

export interface TrendPoint {
  date: string;
  value: number;
}

export interface ConfidenceBucket {
  range: string;
  count: number;
}

export interface OverrideRate {
  defect_class: string;
  override_rate: number;
}

export interface ModelInfo {
  anomaly_model: string;
  detection_model: string;
  version: string;
  last_updated: string;
}

// ===== Certificate =====

export interface Certificate {
  id: string;
  inspection_id: string;
  token: string;
  pdf_url: string;
  created_at: string;
}

export interface CertificateVerification {
  valid: boolean;
  part_number: string;
  decision: DecisionResult;
  decided_at: string;
}

// ===== Demo =====

export interface DemoScenario {
  id: string;
  name: string;
  family: string;
  expected_decision: DecisionResult;
  description: string;
  demonstrates: string;
}

// ===== API Response Envelope =====

export interface ApiResponse<T> {
  data: T;
}

export interface ApiListResponse<T> {
  data: T[];
  total_count: number;
}

// ===== Override Reason Codes =====

export const OVERRIDE_REASONS = [
  { code: "OR-01", label: "Within cosmetic acceptance criteria per drawing note" },
  { code: "OR-02", label: "Artifact of lighting/reflection, not a defect" },
  { code: "OR-03", label: "Acceptable supplier finish variation" },
  { code: "OR-04", label: "Defect present but outside critical zone" },
  { code: "OR-05", label: "Defect confirmed — AI severity understated" },
  { code: "OR-06", label: "Wrong part-family model applied" },
  { code: "OR-07", label: "Other (comment mandatory)" },
] as const;
