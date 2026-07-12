# AVIP Proof-of-Concept — Requirements

## Overview

This PoC demonstrates the AI Vision Inspection Platform (AVIP) concept to Lam Research decision-makers. It showcases real AI defect detection on industrial surfaces, the three-approach inspection fusion, the operator kiosk workflow, the IQA review workbench, dashboards, and certificate generation — all running on demo data without Lam-specific hardware or system access.

**Goal:** Transform the specification into a working demonstration that proves technical feasibility and UX quality, earning confidence to proceed with Phase 0/1.

**Demo audience:** VP Global Quality, Corporate Quality Manager, Site Quality Manager, IQA leads, IT/Architecture representatives.

---

## Requirement 1: Part Identification & Session Initiation

### User Story
As a demo operator, I want to simulate scanning a part barcode so that the system identifies the part and loads its inspection configuration automatically.

### Acceptance Criteria
- Given a simulated barcode scan (click or keyboard entry), when the part number is entered, then the system resolves it against a demo part master within 1 second.
- Given a valid part number, when identified, then the system displays: part number, revision, material, surface finish, part family, and a placement guide image.
- Given an unknown part number, when entered, then the system displays an "unidentified part" exception state with routing to IQA.
- The demo part master contains at least 5 part families with realistic attributes (machined aluminum, welded stainless, anodized plate, PCB assembly, cable assembly).

---

## Requirement 2: Multi-Angle Image Capture Simulation

### User Story
As a demo operator, I want to see simulated multi-angle image capture with quality validation so that the client understands the capture workflow.

### Acceptance Criteria
- Given a part is identified, when capture is triggered, then the system displays a simulated multi-camera grid (top, N, S, E, W views) loading pre-stored images with per-camera status indicators.
- Given all cameras capture successfully, then each view shows a green checkmark and the system auto-advances to inspection.
- Given a simulated quality failure (one image with glare/blur), then that camera view shows a red indicator with the failure reason and a "Recapture" button.
- Capture simulation completes within 3 seconds.

---

## Requirement 3: AI Defect Detection (Real Inference)

### User Story
As a demo presenter, I want to run real AI inference on industrial defect images so that the client sees actual AI capability, not mock data.

### Acceptance Criteria
- Given a captured image set, when AI inspection runs, then a real anomaly detection model (PatchCore or equivalent trained on MVTec AD) produces pixel-level anomaly heatmaps.
- Given a captured image set, when AI inspection runs, then a defect detection model produces bounding boxes with defect class labels and confidence scores.
- The system detects at least 5 defect classes: scratches, dents, contamination, missing components, surface anomalies.
- Inference completes within 5 seconds for a full part (all angles).
- Confidence scores are displayed per finding (0–100%).
- XAI heatmaps (anomaly score maps) are generated and overlayable on the source image.

---

## Requirement 4: Three-Approach Inspection Fusion

### User Story
As a demo presenter, I want to show all three inspection approaches working together so that the client sees the differentiated multi-approach strategy.

### Acceptance Criteria
- Given a part inspection, the system demonstrates Approach 1 (Drawing-Based Rules): displays a simulated drawing with zone highlights, verifies feature presence/absence (e.g., "4/4 screws present" or "1 screw missing"), and produces rule-based findings.
- Given a part inspection, the system demonstrates Approach 2 (Golden Sample Comparison): displays a registered side-by-side of the test image vs. golden reference with a difference heatmap overlay and tolerance bands.
- Given a part inspection, the system demonstrates Approach 3 (AI Detection): displays bounding boxes, segmentation masks, and anomaly heatmaps from real model inference.
- The system fuses results from all three approaches into a unified decision (PASS / FAIL / REVIEW) with per-finding attribution showing which approach produced each finding.
- Decision thresholds are configurable per part family via the UI.

---

## Requirement 5: Decision Display (Operator Result Screen)

### User Story
As a demo operator, I want to see a full-screen PASS/FAIL decision with clear routing instructions so that the client experiences the glanceable UX.

### Acceptance Criteria
- Given a PASS decision, the system displays a full-screen green banner with part number, staging location, and certificate ID in large (72pt+) text, auto-dismissing after 5 seconds.
- Given a FAIL decision, the system displays a full-screen red banner with quarantine routing instruction, findings count, and a "View Findings" shortcut.
- Given a REVIEW decision, the system displays an amber banner indicating the part is routed to the IQA queue.
- Audio cues (distinct tones) accompany each decision state.
- The decision screen is readable from 3 meters (high contrast, oversized typography).

---

## Requirement 6: IQA Review Workbench

### User Story
As a demo IQA inspector, I want to review AI findings with full evidence so that the client sees the power of the review experience.

### Acceptance Criteria
- The review queue displays pending inspections sorted by priority with columns: age, part number, family, supplier, defect classes, confidence band, station.
- Given a selected record, the workbench displays a three-pane layout: (left) image viewer with all angles as filmstrip + main canvas with zoom/pan, (center-bottom) findings list with class, severity, confidence, and approach badge, (right) context panel with drawing viewer and part metadata.
- Defect overlays (bounding boxes, segmentation masks, XAI heatmaps) are toggleable on/off per layer.
- Golden-sample comparison is available as a synchronized slider (test vs. golden).
- Override flow: "Override → PASS" opens a modal requiring reason code selection + comment; "Confirm FAIL" requires one click.
- Override reason codes match Spec 02 Appendix (OR-01 through OR-07).

---

## Requirement 7: Dashboards & Analytics

### User Story
As a demo supervisor/executive, I want to see operational dashboards so that the client understands the real-time visibility AVIP provides.

### Acceptance Criteria
- Inspection Dashboard: KPI strip (today's inspections, pass rate, avg cycle time, queue depth), live station tiles showing status, decision stream.
- Defect Dashboard: Pareto chart by defect class, trend lines, part-outline heatmap showing defect spatial density.
- Supplier Quality Dashboard: supplier league table with DPPM, defect mix per supplier, trend arrows.
- AI Performance Dashboard: per-model accuracy, FP/FN rates, confidence distribution histogram, override rate.
- All dashboards use demo data that tells a realistic story (not random — structured to show patterns).
- Dashboards refresh in real-time as new inspections are performed during the demo.

---

## Requirement 8: Inspection Certificate Generation

### User Story
As a demo presenter, I want to generate a PDF inspection certificate so that the client sees the audit-trail deliverable.

### Acceptance Criteria
- Given a completed inspection (PASS or overridden PASS), the system generates a PDF certificate containing: part number, revision, decision, findings summary (if any), thumbnail images, reviewer identity (if overridden), timestamps, and a QR code.
- The QR code links to a verification endpoint that displays: validity status, part number, decision, and timestamp.
- Certificates are downloadable from the inspection record.

---

## Requirement 9: Demo Data & Scenario Orchestration

### User Story
As a demo presenter, I want pre-built demo scenarios that tell a compelling story so that the demonstration flows naturally.

### Acceptance Criteria
- The PoC includes at least 10 pre-built inspection scenarios covering: clean PASS (multiple families), scratch detected, dent detected, missing fastener, contamination, surface anomaly (unknown class), golden-sample deviation, multi-defect FAIL, REVIEW-band case (low confidence), and an override scenario.
- Demo scenarios are selectable from a hidden presenter panel (not visible to audience).
- Each scenario includes pre-staged images (from MVTec AD or similar industrial datasets), pre-configured AI results, and a narrative description for the presenter.
- A "continuous demo mode" auto-cycles through scenarios to simulate live station operation.

---

## Requirement 10: Deployment & Presentation Readiness

### User Story
As a demo presenter, I want the PoC to run reliably in a presentation setting so that the demo is smooth and professional.

### Acceptance Criteria
- The entire PoC runs via `docker compose up` with no external dependencies beyond the container images.
- First load (cold start) completes within 30 seconds.
- The UI is responsive and works on a 1080p projector as well as a 4K display.
- No mock/placeholder text is visible — all data looks production-realistic.
- The system handles the full demo flow (10 scenarios × 3 approaches × dashboards) without crashes or visible errors.
- A README documents: setup instructions, demo script, and troubleshooting.

---

## Non-Functional Requirements

| NFR | Target |
|---|---|
| Inference latency | ≤ 5 seconds per part (CPU-only acceptable for demo; GPU optional for speed) |
| UI responsiveness | All interactions respond within 200 ms (excluding AI inference) |
| Browser support | Chrome 120+, Edge 120+ |
| Resolution | 1920×1080 minimum; scales to 4K |
| Accessibility | WCAG 2.2 AA color contrast; touch targets ≥ 44px |
| Offline capability | Fully offline after initial Docker build (no runtime internet required) |
