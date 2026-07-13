---
inclusion: fileMatch
fileMatchPattern: "**/{ai_pipeline,anomaly_detector,defect_detector,golden_comparator,fusion_engine,rule_engine}*"
---

# AI/ML Model Context

## Model Architecture

### PatchCore (Anomaly Detection)
- **Input:** (1, 3, 224, 224) normalized RGB image
- **Output:** (1, 1, 224, 224) anomaly score map (0.0=normal, 1.0=anomalous)
- **Location:** `backend/ai_models/patchcore/model.onnx`
- **Service:** `app/services/anomaly_detector.py`
- Generates heatmap images saved to `data/heatmaps/`
- Falls back to simulated results if model file is missing

### YOLOv8 (Defect Detection)
- **Input:** (1, 3, 640, 640) normalized RGB image
- **Output:** (1, 8400, 14) — each row: [x_center, y_center, width, height, 10 class scores]
- **Location:** `backend/ai_models/yolov8/defect_detector.onnx`
- **Service:** `app/services/defect_detector.py`
- 10 defect classes: scratch, dent, contamination, missing_component, crack, chip, rust, wrong_label, missing_label, surface_anomaly
- NMS applied post-inference

### Golden Sample Comparison
- **No ML model** — pure OpenCV (ORB registration + SSIM + absolute difference)
- **Service:** `app/services/golden_comparator.py`
- Produces difference heatmaps comparing test image against reference

### Rule Engine
- **Deterministic** — no model, just logic rules per part family
- **Service:** `app/services/rule_engine.py`
- Rules defined in `FAMILY_RULES` dict (presence checks, count checks)

## Fusion Engine (Decision Logic)

Rules in priority order:
- **F-01:** Critical rule failure → FAIL
- **F-02:** High-confidence severe model/anomaly finding → FAIL
- **F-03:** Findings in review band (between thresholds) → REVIEW
- **F-04:** Golden-diff corroborated by another approach → FAIL
- **F-05:** No findings above threshold → PASS
- **F-06:** Rule passes but model says FAIL at high confidence → REVIEW (conflict)

## Thresholds (per family)
- `confidence_high`: Upper threshold for auto-FAIL (default: 0.85)
- `confidence_low`: Lower threshold, below = ignore (default: 0.55)
- `severity_threshold`: Minimum severity for FAIL (default: "major")
- `max_findings_pass`: Max findings allowed for PASS (default: 0)

## confidence_summary Schema
The `Decision.confidence_summary` field is `dict[str, float]`:
- `overall`: max confidence across all findings
- `max_finding`: same as overall
- `approaches_triggered`: count of unique approaches (as float, NOT a list)
