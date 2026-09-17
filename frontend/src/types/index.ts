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
// ===== Source Comparison (LAIR / FAIR / SHQ) =====

export type SCSource = "LAIR" | "FAIR" | "SHQ";

export type SCFieldType = "numeric" | "categorical" | "identifier" | "free_text";

export type SCProvenance = "exact-match" | "numeric-threshold" | "llm" | "llm-unavailable";

export type SCReviewState = "pending" | "confirmed" | "dismissed";

// Human-readable context for a part number, resolved from the parts table by
// the backend. Null when the part number is not present in that table; any
// individual field can also be null when unknown.
export interface SCPartContext {
  description: string | null;
  revision: string | null;
  material: string | null;
  supplier: string | null;
}

// Helper type for a single source's value. The backend returns `values` as an
// object keyed by source (see SCValues below), not an array of these; this type
// is retained for convenience when iterating a source/value pair.
export interface SCSourceValue {
  source: SCSource;
  value: string | number | null;
}

// The actual backend JSON shape: `values` is an object keyed by source name.
export type SCValues = Record<string, string | number | null>;

export interface SCDiscrepancy {
  id: string;
  group_id: string;
  part_number: string;
  lot_number: string;
  field_name: string;
  field_type: SCFieldType;
  values: SCValues;
  provenance: SCProvenance;
  review_state: SCReviewState;
  reviewer: string | null;
  reviewer_note: string | null;
  decided_at: string | null;
  // Human-readable part context resolved from the parts table; null when the
  // part number is not in that table.
  part_context?: SCPartContext | null;
}

// A part/lot GROUP of pending discrepancies, as returned by the grouped review
// queue endpoint. `count` is the number of discrepancies in the group and
// `provenance_counts` tallies them by provenance type.
export interface SCGroup {
  part_number: string;
  lot_number: string;
  count: number;
  provenance_counts: Record<string, number>;
  discrepancies: SCDiscrepancy[];
}

export type SCAlignmentState = "partial" | "complete" | "unmatched";

export interface SCAlignedGroup {
  id: string;
  part_number: string;
  lot_number: string;
  present_sources: SCSource[];
  alignment_state: SCAlignmentState;
  records: SCSourceRecord[];
}

export interface SCSourceRecord {
  id: string;
  source: SCSource;
  part_number: string;
  lot_number: string;
  fields: Record<string, string | number | null>;
}

export interface SCReportRow {
  id: string;
  group_id: string;
  part_number: string;
  lot_number: string;
  field_name: string;
  field_type: SCFieldType;
  values: SCValues;
  provenance: SCProvenance;
  // Present when the report is viewed with an explicit review_state filter
  // (opt-in). Omitted on the default confirmed-only report.
  review_state?: SCReviewState;
  // Human-readable part context resolved from the parts table; null when the
  // part number is not in that table.
  part_context?: SCPartContext | null;
}

// A single supplier rollup row from the confirmed-only discrepancy report,
// grouped by the supplier joined from the parts table (via part_context).
// Rows whose part has no supplier are grouped under "(unknown)".
export interface SCSupplierSummaryRow {
  supplier: string;
  discrepancy_count: number;
  part_count: number;
  provenance_counts: Record<string, number>;
}

export interface SCReportHeader {
  assumptions: SCAssumption[];
  total_count: number;
}

export interface SCAssumption {
  key: string;
  label: string;
  status: "assumed" | "confirmed" | "unresolved";
  value: string | null;
}

export interface SCStatus {
  ingested: number;
  rejected: number;
  groups_partial: number;
  groups_complete: number;
  simulator_running: boolean;
  assumptions: SCAssumption[];
}

export interface SCRejectedRecord {
  id: string;
  source: SCSource;
  external_record_id: string | null;
  raw_payload: unknown;
  reason: string;
  created_at: string;
}

// ===== Source Comparison: Threshold Configuration =====

// Per-field default configuration: whether the field is in scope for
// comparison and the numeric threshold used for numeric fields (null when not
// applicable, e.g. non-numeric fields or when no threshold is set).
export interface SCFieldConfig {
  field_name: string;
  type: SCFieldType;
  in_scope: boolean;
  threshold: number | null;
}

// A part-number-specific override of a field's numeric threshold.
export interface SCThresholdOverride {
  id?: string;
  part_number: string;
  field_name: string;
  threshold: number;
  updated_at?: string;
}

// A single audit-log entry describing a configuration change.
export interface SCConfigAuditRow {
  id: string;
  change_type:
    | "field_default"
    | "part_override_set"
    | "part_override_delete"
    | "field_scope";
  field_name: string | null;
  part_number: string | null;
  old_value: string | null;
  new_value: string | null;
  changed_by: string;
  changed_at: string;
  note: string | null;
}

// The full comparison configuration: the set of per-field defaults.
export interface SCComparisonConfig {
  fields: SCFieldConfig[];
}

// Paginated envelope for the configuration audit log.
export interface SCConfigAuditPage {
  data: SCConfigAuditRow[];
  total_count: number;
  limit: number;
  offset: number;
}

// ===== PCBA TPI Generation =====

// Per-input ingestion status: successfully ingested, or flagged for manual
// annotation when a parse/extraction failure occurred (Req 1.2, 1.4).
export type TpiInputStatus = "ingested" | "flagged_for_manual_annotation";

// The four input kinds per PCBA. Text kinds (testing/operating procedure) use
// text extraction; visual kinds (circuit diagram/drawing) use the multimodal
// path.
export type TpiInputType =
  | "testing_procedure"
  | "operating_procedure"
  | "circuit_diagram"
  | "drawing";

// Review lifecycle of a generated draft (Req 4.x).
export type TpiReviewState = "drafted" | "in_review" | "finalized";

// Pipeline status of a PCBA that drives the status badge (Req 6.9).
export type TpiPcbaStatus = "ingesting" | "drafted" | "in_review" | "finalized";

// One persisted input row for a PCBA. `detected_format` is reported rather than
// assumed for visual inputs (Req 1.3, [CONFIRM]); `raw_ref` is the stored
// file/blob reference.
export interface TpiInput {
  id: string;
  pcba_id: string;
  input_type: TpiInputType;
  filename: string;
  detected_format: string | null;
  status: TpiInputStatus;
  raw_ref: string;
  // Web-servable `/static` URL for a previewable visual input image (circuit
  // diagram / drawing) whose stored file is a raster image under a mounted
  // static root; null for text inputs, non-image formats, or files not under a
  // static root (Part B — image preview in the review workbench).
  preview_url: string | null;
  // Cleaned, truncated text excerpt of a TEXT input's stored procedure file
  // (testing_procedure / operating_procedure) so the reviewer can see the
  // actual source content; null for visual inputs (which use `preview_url`
  // instead), in-memory refs, or unreadable files.
  text_excerpt: string | null;
}

// A mapped/generated TPI section carrying source-input provenance and an
// `incomplete` marker for sections derived from flagged inputs (Req 3.3, 3.4).
export interface TpiSection {
  key: string;
  title: string;
  content: string;
  source_input_ids: string[];
  incomplete: boolean;
}

// A generated draft TPI: the ordered sections plus the template/provider used.
// `template_kind` is the client template when confirmed, else the placeholder
// (Req 5.2 vs 5.3).
export interface DraftTpi {
  pcba_id: string;
  template_kind: string;
  provider: string;
  review_state: TpiReviewState;
  sections: TpiSection[];
}

// A PCBA summary row for the monitor list. `review_state`/`template_kind` are
// null until a draft has been generated.
export interface TpiPcbaRow {
  pcba_id: string;
  status: TpiPcbaStatus;
  created_at: string;
  review_state: TpiReviewState | null;
  template_kind: string | null;
}

// Full PCBA detail: its inputs and the current draft (null before processing).
export interface TpiPcbaDetail {
  pcba_id: string;
  status: TpiPcbaStatus;
  created_at: string;
  inputs: TpiInput[];
  draft: DraftTpi | null;
}

// A single review-audit entry: who finalized, when, and what changed (Req 4.4).
export interface TpiAuditRow {
  id: string;
  pcba_id: string;
  reviewer: string;
  action: string;
  changes: Record<string, unknown>;
  decided_at: string;
}

// A surfaced `[CONFIRM]` marker for the status banner (Req 6.9); never a hidden
// default.
export interface TpiConfirmItem {
  key: string;
  label: string;
  detail: string;
}

// Pipeline/config status: PCBA counts by status, the active LLM provider, and
// any unresolved `[CONFIRM]` items.
export interface TpiStatus {
  pcba_status_counts: Record<string, number>;
  total_pcbas: number;
  llm_provider: string;
  confirm_items: TpiConfirmItem[];
}

// Request shape for a single input in the ingest call (POST /tpi/pcbas/{id}/inputs).
export interface TpiInputRef {
  input_type: string;
  filename: string;
  path?: string | null;
}
