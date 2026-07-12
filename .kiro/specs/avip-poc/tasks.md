# AVIP Proof-of-Concept — Tasks

## Phase 1: Foundation & AI Pipeline (Week 1)

### Task 1.1: Project Scaffolding
- [ ] Initialize backend Python project with pyproject.toml (Python 3.12, FastAPI, uvicorn, pydantic v2, onnxruntime, opencv-python, pillow, reportlab, qrcode, aiosqlite)
- [ ] Initialize frontend React project with Vite + TypeScript strict + Tailwind CSS v3 + React Router v6 + React Query v5 + Recharts
- [ ] Create docker-compose.yml with backend and frontend services
- [ ] Create Makefile with targets: setup, dev, build, run, clean
- [ ] Create README.md with setup instructions

**Implements:** Req 10 (Deployment)

### Task 1.2: Data Models & Database
- [ ] Define Pydantic models: Part, PartFamily, PartRevision, Inspection, Finding, Decision, Override, Certificate
- [ ] Define TypeScript types mirroring backend models (shared types file)
- [ ] Create SQLite schema (inspections, parts, images, findings, overrides, certificates)
- [ ] Create database initialization with seed data (5 part families, demo parts)
- [ ] Create demo part master JSON with realistic attributes for each family

**Implements:** Req 1 (Part ID), Req 9 (Demo Data)

### Task 1.3: AI Model Preparation
- [ ] Download MVTec AD dataset (metal_nut, screw, grid categories — good images only for anomaly training)
- [ ] Train PatchCore model on MVTec metal_nut/screw/grid using anomalib; export to ONNX
- [ ] Obtain/train YOLOv8n defect detector (NEU surface defects or pre-annotated industrial set); export to ONNX
- [ ] Validate both models run via ONNX Runtime on CPU within latency budget
- [ ] Package models into backend/ai_models/ directory

**Implements:** Req 3 (AI Detection)

### Task 1.4: Anomaly Detection Service
- [ ] Implement `anomaly_detector.py`: load PatchCore ONNX model, preprocess image (resize, normalize), run inference, produce anomaly score map
- [ ] Implement anomaly score map → heatmap image conversion (colormap overlay)
- [ ] Implement thresholding: score map → binary anomaly mask → bounding regions
- [ ] Implement finding generation: regions → Finding objects with confidence, bbox, heatmap_url
- [ ] Write unit test with sample MVTec image (good vs. defective)

**Implements:** Req 3 (AI Detection), Req 4 (Approach 3)

### Task 1.5: Object Detection Service
- [ ] Implement `defect_detector.py`: load YOLOv8 ONNX model, preprocess, run inference, post-process (NMS)
- [ ] Map detection classes to AVIP defect taxonomy (scratch, dent, contamination, missing_component, crack)
- [ ] Generate Finding objects with bounding boxes, class, confidence
- [ ] Write unit test verifying detection on known defective image

**Implements:** Req 3 (AI Detection), Req 4 (Approach 3)

### Task 1.6: Golden Sample Comparator
- [ ] Implement `golden_comparator.py`: load golden reference image for part family
- [ ] Implement image registration using ORB feature matching + homography transform
- [ ] Implement SSIM computation + absolute difference calculation
- [ ] Implement tolerance-band thresholding (configurable per family)
- [ ] Generate difference heatmap image + Finding objects for regions exceeding tolerance
- [ ] Write unit test with matched pair (golden vs. test with simulated deviation)

**Implements:** Req 4 (Approach 2 - Golden Comparison)

### Task 1.7: Rule Engine
- [ ] Implement `rule_engine.py`: load rule definitions (JSON) per part family
- [ ] Implement presence/absence evaluation (using YOLO detections as evidence: count screws, verify label, check orientation)
- [ ] Implement zone-based severity mapping
- [ ] Generate rule findings (deterministic PASS/FAIL per rule)
- [ ] Create demo rule sets for each family (screw count, label presence, orientation)
- [ ] Write unit test for rule evaluation

**Implements:** Req 4 (Approach 1 - Drawing Rules)

### Task 1.8: Fusion Engine & AI Pipeline Orchestrator
- [ ] Implement `fusion_engine.py` with rules F-01 through F-07 (hard-fail rules → FAIL; high-confidence → FAIL; review band → REVIEW; corroboration escalation; no findings → PASS)
- [ ] Implement per-family threshold configuration (confidence high/low, severity threshold)
- [ ] Implement `ai_pipeline.py` orchestrator: runs all 3 approaches, collects findings, calls fusion engine
- [ ] Return unified InspectionResult with all findings + decision + per-finding approach attribution
- [ ] Write integration test: pipeline produces correct decision for known inputs

**Implements:** Req 4 (Three-Approach Fusion)

---

## Phase 2: API & Backend Services (Week 1–2)

### Task 2.1: FastAPI App Setup
- [ ] Create main.py with FastAPI app, CORS middleware, lifespan (DB init, model loading)
- [ ] Create config.py with settings (data dir, model dir, demo data dir)
- [ ] Set up static file serving for generated images/heatmaps/certificates
- [ ] Create health check endpoint

**Implements:** Req 10 (Deployment)

### Task 2.2: Parts Router
- [ ] GET `/api/v1/parts/{part_number}` — look up part with family, rules, golden set info
- [ ] GET `/api/v1/parts` — list all demo parts (for presenter panel)
- [ ] Return capture profile, drawing reference, and placement guide per part

**Implements:** Req 1 (Part ID)

### Task 2.3: Inspections Router
- [ ] POST `/api/v1/inspections` — create new inspection (part identified)
- [ ] POST `/api/v1/inspections/{id}/capture` — simulate capture (load pre-staged images, apply quality simulation, store image records)
- [ ] POST `/api/v1/inspections/{id}/inspect` — trigger AI pipeline, store findings + decision, update status
- [ ] GET `/api/v1/inspections/{id}` — full record with images, findings, decision, override
- [ ] GET `/api/v1/inspections` — list with filters (status, family, decision, date range)

**Implements:** Req 1, 2, 3, 4

### Task 2.4: Review Router
- [ ] GET `/api/v1/review/queue` — return pending inspections (FAIL + REVIEW status) sorted by priority
- [ ] POST `/api/v1/review/{id}/override` — validate reason code + comment, update decision, create override record
- [ ] POST `/api/v1/review/{id}/confirm` — confirm AI decision, update status to confirmed-FAIL

**Implements:** Req 6 (Review Workbench)

### Task 2.5: Dashboard Router
- [ ] GET `/api/v1/dashboard/inspection` — today's stats: count, pass rate, avg cycle time, queue depth, recent decisions
- [ ] GET `/api/v1/dashboard/defects` — defect Pareto by class, trends (last 7 days simulated), severity mix
- [ ] GET `/api/v1/dashboard/suppliers` — supplier DPPM table, defect mix per supplier
- [ ] GET `/api/v1/dashboard/ai-performance` — accuracy, FP/FN rates, confidence histogram, override rate

**Implements:** Req 7 (Dashboards)

### Task 2.6: Certificate Router & Generator
- [ ] Implement certificate PDF generation (reportlab): part info, decision badge, findings table, image thumbnails, QR code, timestamps
- [ ] POST auto-generate certificate on PASS or Override-PASS decision
- [ ] GET `/api/v1/certificates/{id}` — metadata + PDF URL
- [ ] GET `/api/v1/certificates/{id}/pdf` — serve PDF file
- [ ] GET `/api/v1/certificates/verify/{token}` — public verification (returns validity, part, decision, date)

**Implements:** Req 8 (Certificate)

### Task 2.7: Demo Orchestration Router
- [ ] GET `/api/v1/demo/scenarios` — list all 10 scenarios with name, family, expected outcome, description
- [ ] POST `/api/v1/demo/scenarios/{id}/run` — execute scenario (create inspection, load scenario images, run pipeline with scenario-appropriate results)
- [ ] POST `/api/v1/demo/reset` — drop all inspection data, reinitialize
- [ ] Implement auto-cycle mode (returns next scenario on repeated calls)

**Implements:** Req 9 (Demo Scenarios)

---

## Phase 3: Frontend — Operator Kiosk (Week 2)

### Task 3.1: Frontend Scaffolding
- [ ] Set up React Router with all routes (kiosk, review, dashboard, demo, certificates)
- [ ] Set up React Query client with API base URL
- [ ] Create Tailwind config with AVIP design tokens (colors, fonts, spacing)
- [ ] Create shared component library: Button, Badge, Modal, KPITile, StatusBadge, LoadingSpinner
- [ ] Set up audio assets (PASS tone, FAIL tone, REVIEW tone)

**Implements:** Req 10 (Deployment), Req 5 (Decision Display)

### Task 3.2: Scan Screen (Kiosk)
- [ ] Full-screen layout with pulsing "Scan Part Barcode" prompt
- [ ] Keyboard input field (simulates barcode scanner) — auto-submits on Enter
- [ ] On valid part: display part card (number, rev, material, family) for 2 seconds, then auto-advance to capture
- [ ] On invalid part: "Unidentified Part" error state with "Route to IQA" button
- [ ] Station status bar: connectivity badge, calibration status pill

**Implements:** Req 1 (Part ID)

### Task 3.3: Capture Screen (Kiosk)
- [ ] Left 70%: camera grid (5 views) with animated capture sequence (gray → loading → image + green check)
- [ ] Simulated quality failure on one camera (configurable): red indicator + "Glare detected" chip + Recapture button
- [ ] Right 30%: part card + placement guide illustration + progress stepper (Identify ✓ → Capture → Inspect → Result)
- [ ] Auto-advance to inspection on all-cameras-pass
- [ ] Loading state during AI inference with "Inspecting..." animation

**Implements:** Req 2 (Capture Simulation)

### Task 3.4: Result Screen (Kiosk)
- [ ] Full-screen PASS state: green background, "PASS" in 72pt+, part number, staging location, certificate ID, auto-dismiss after 5s countdown
- [ ] Full-screen FAIL state: red background, "FAIL" in 72pt+, quarantine instruction, findings count badge, "View Findings" link
- [ ] Full-screen REVIEW state: amber background, "REVIEW" text, "Routed to IQA Queue" message
- [ ] Audio cue plays on each decision state
- [ ] "Next Part" button returns to Scan screen

**Implements:** Req 5 (Decision Display)

---

## Phase 4: Frontend — Review Workbench (Week 2)

### Task 4.1: Review Queue
- [ ] Table view: priority flag (color), age, part number, family, supplier, defect classes (as badges), confidence band, decision
- [ ] Sort by priority (default), age, confidence
- [ ] Filter sidebar: family, defect class, decision (FAIL/REVIEW)
- [ ] Click row → navigate to Review Workbench for that inspection
- [ ] Show queue depth count in header

**Implements:** Req 6 (Review Workbench)

### Task 4.2: Image Viewer Component
- [ ] Filmstrip (horizontal) showing all angle thumbnails; click to select main view
- [ ] Main canvas with pan (drag) and zoom (scroll wheel / pinch / buttons)
- [ ] Overlay toggle buttons: Bounding Boxes, Segmentation Masks, XAI Heatmap, Golden Diff
- [ ] Each overlay renders as semi-transparent layer on canvas
- [ ] Fit / 1:1 zoom presets
- [ ] Clicking a finding in the findings list auto-frames the relevant region

**Implements:** Req 6 (Review Workbench)

### Task 4.3: Review Workbench Layout
- [ ] Three-pane layout: left (image viewer, 55% width), center-bottom (findings list, 25%), right (context panel, 20%)
- [ ] Findings list: table of findings with columns: class icon, severity badge, confidence %, approach badge (RULE/GOLD/MODEL/ANOM), description
- [ ] Context panel: drawing viewer (static image), part metadata (material, finish, notes), part history sparkline
- [ ] Action bar (fixed bottom): "Confirm FAIL" button (red), "Override → PASS" button (green, opens modal)
- [ ] Navigation: back to queue, previous/next in queue

**Implements:** Req 6 (Review Workbench)

### Task 4.4: Golden Comparison Slider
- [ ] Side-by-side slider: left shows golden reference, right shows test image
- [ ] Drag slider to reveal/hide; synchronized zoom/pan
- [ ] Difference heatmap as additional overlay option
- [ ] Tolerance band visualization (green = within tolerance, yellow = marginal, red = exceeds)

**Implements:** Req 4 (Golden Comparison), Req 6 (Review Workbench)

### Task 4.5: Override Modal
- [ ] Modal with: reason code dropdown (OR-01 through OR-07 with descriptions), comment textarea (required, min 10 chars), reviewer name field
- [ ] Submit validation: all fields required
- [ ] On submit: call override API, update inspection status, show success confirmation
- [ ] Cancel returns to workbench without changes

**Implements:** Req 6 (Review Workbench)

---

## Phase 5: Frontend — Dashboards (Week 2–3)

### Task 5.1: Dashboard Layout & Navigation
- [ ] Dashboard home with tab navigation: Inspection, Defects, Supplier Quality, AI Performance
- [ ] Global filters bar: date range, part family selector
- [ ] Auto-refresh toggle (30s interval)
- [ ] Responsive layout (works on projector and 4K display)

**Implements:** Req 7 (Dashboards)

### Task 5.2: Inspection Dashboard
- [ ] KPI strip: total inspections (today), pass rate %, avg cycle time, queue depth
- [ ] Station status tiles (simulated 2 stations): current state, current part, parts/hour
- [ ] Decision stream: scrolling list of recent decisions with timestamp, part, result badge
- [ ] Cycle time histogram (Recharts)

**Implements:** Req 7 (Dashboards)

### Task 5.3: Defect Dashboard
- [ ] Defect Pareto: horizontal bar chart of defect classes by count (Recharts)
- [ ] Trend lines: daily defect counts by class (last 7 days, line chart)
- [ ] Severity distribution: donut chart (minor/major/critical)
- [ ] Part family heatmap: simple grid showing defect density per family (color-coded cells)

**Implements:** Req 7 (Dashboards)

### Task 5.4: Supplier Quality Dashboard
- [ ] Supplier league table: name, DPPM, trend arrow (↑↓→), volume, top defect class
- [ ] Defect mix per supplier: stacked bar chart
- [ ] Threshold breach banner for worst supplier

**Implements:** Req 7 (Dashboards)

### Task 5.5: AI Performance Dashboard
- [ ] Accuracy gauge: overall accuracy % with target line
- [ ] FP/FN rate trend: dual-line chart (last 7 days)
- [ ] Confidence distribution: histogram of all decision confidences
- [ ] Override rate: bar chart by defect class (shows where AI disagrees with humans)
- [ ] Model version info card

**Implements:** Req 7 (Dashboards)

---

## Phase 6: Demo Polish & Delivery (Week 3)

### Task 6.1: Demo Scenarios Implementation
- [ ] Create 10 scenario configuration files (JSON) with: images to use, expected findings, expected decision, narrative text
- [ ] Curate images for each scenario from MVTec/NEU/stock sources
- [ ] Create golden reference images for comparison scenarios
- [ ] Create simulated drawing images (annotated diagrams) for rule-engine scenarios
- [ ] Verify each scenario produces correct results end-to-end

**Implements:** Req 9 (Demo Scenarios)

### Task 6.2: Presenter Panel
- [ ] Hidden panel (Ctrl+Shift+D toggle): list of 10 scenarios with "Run" buttons
- [ ] Each scenario shows: name, family, expected decision, presenter notes
- [ ] "Auto-cycle" toggle: runs scenarios sequentially with configurable delay
- [ ] "Reset All Data" button with confirmation
- [ ] Current scenario indicator

**Implements:** Req 9 (Demo Scenarios)

### Task 6.3: Demo Data Seeding
- [ ] Seed database with 50+ historical inspection records (varied decisions, dates, families, suppliers) for dashboard realism
- [ ] Ensure dashboard data tells a coherent story: one supplier trending poorly, one defect class dominant, accuracy improving over time
- [ ] Seed review queue with 3–5 pending items for workbench demonstration

**Implements:** Req 7 (Dashboards), Req 9 (Demo Data)

### Task 6.4: Docker Build & Optimization
- [ ] Multi-stage Dockerfile for backend (slim Python image, copy only needed packages + models)
- [ ] Multi-stage Dockerfile for frontend (build stage → nginx serve)
- [ ] Verify cold start < 30 seconds (model loading is the bottleneck)
- [ ] Optimize model loading: load on startup, keep in memory
- [ ] Total Docker image size target: < 3 GB (models dominate)
- [ ] Test full docker-compose up → demo flow → docker-compose down cycle

**Implements:** Req 10 (Deployment)

### Task 6.5: README & Demo Script
- [ ] README: prerequisites (Docker), setup (one command), architecture overview, screenshot previews
- [ ] Demo script document: recommended sequence, talking points per screen, timing suggestions, FAQ preparation
- [ ] Troubleshooting section: common issues + solutions

**Implements:** Req 10 (Deployment)

### Task 6.6: Final QA & Polish
- [ ] Verify all 10 scenarios run without errors
- [ ] Verify all dashboards display correctly on 1080p and 4K
- [ ] Verify no placeholder text or Lorem ipsum visible anywhere
- [ ] Verify audio cues work in browser
- [ ] Verify certificate PDF generates correctly with QR code
- [ ] Verify full demo can run offline (no external network calls)
- [ ] Performance check: no screen takes > 5s to load
- [ ] Cross-browser check: Chrome + Edge

**Implements:** Req 10 (Deployment), all NFRs
