# AVIP Proof-of-Concept — Design

## 1. Architecture Overview

The PoC is a self-contained, Docker-deployable application with three layers: a Python backend (AI inference + API), a React frontend (operator kiosk + IQA workbench + dashboards), and a local SQLite database with filesystem-based image storage. No external services are required at runtime.

```
┌──────────────────────────────────────────────────────────────────┐
│                        Browser (React SPA)                        │
│  ┌─────────────┐  ┌─────────────────┐  ┌──────────────────────┐ │
│  │ Operator    │  │ IQA Review      │  │ Dashboards &         │ │
│  │ Kiosk       │  │ Workbench       │  │ Analytics            │ │
│  └─────────────┘  └─────────────────┘  └──────────────────────┘ │
└───────────────────────────────┬──────────────────────────────────┘
                                │ REST API (JSON)
┌───────────────────────────────┼──────────────────────────────────┐
│                        FastAPI Backend                            │
│  ┌──────────┐  ┌───────────┐  ┌──────────┐  ┌───────────────┐  │
│  │ Inspection│  │ AI        │  │ Parts &  │  │ Certificate   │  │
│  │ Service   │  │ Pipeline  │  │ Rules    │  │ Generator     │  │
│  └──────────┘  └───────────┘  └──────────┘  └───────────────┘  │
│  ┌──────────────────────────────────────────────────────────┐   │
│  │              AI Models (ONNX Runtime)                      │   │
│  │  PatchCore (anomaly) │ YOLOv8 (detection) │ Comparator   │   │
│  └──────────────────────────────────────────────────────────┘   │
└───────────────────────────────┬──────────────────────────────────┘
                                │
┌───────────────────────────────┼──────────────────────────────────┐
│                        Data Layer                                 │
│  ┌──────────┐  ┌───────────────────┐  ┌───────────────────────┐ │
│  │ SQLite   │  │ Image Store       │  │ Demo Data             │ │
│  │ (records)│  │ (filesystem)      │  │ (MVTec + synthetic)   │ │
│  └──────────┘  └───────────────────┘  └───────────────────────┘ │
└──────────────────────────────────────────────────────────────────┘
```

## 2. Project Structure

```
avip-poc/
├── .kiro/specs/avip-poc/          # SDD specs
│   ├── requirements.md
│   ├── design.md
│   └── tasks.md
├── backend/
│   ├── app/
│   │   ├── __init__.py
│   │   ├── main.py                # FastAPI app entry point
│   │   ├── config.py              # Settings / env vars
│   │   ├── models/                # Pydantic models
│   │   │   ├── __init__.py
│   │   │   ├── inspection.py      # Inspection, Finding, Decision
│   │   │   ├── part.py            # Part, PartFamily, PartRevision
│   │   │   └── certificate.py     # Certificate model
│   │   ├── routers/
│   │   │   ├── __init__.py
│   │   │   ├── inspections.py     # Inspection CRUD + workflow
│   │   │   ├── parts.py           # Part master lookup
│   │   │   ├── review.py          # IQA review queue + overrides
│   │   │   ├── dashboard.py       # Dashboard data endpoints
│   │   │   ├── certificates.py    # Certificate gen + verify
│   │   │   └── demo.py            # Demo scenario orchestration
│   │   ├── services/
│   │   │   ├── __init__.py
│   │   │   ├── ai_pipeline.py     # Orchestrates 3 approaches
│   │   │   ├── anomaly_detector.py # PatchCore inference
│   │   │   ├── defect_detector.py  # YOLO inference
│   │   │   ├── golden_comparator.py # Image registration + diff
│   │   │   ├── rule_engine.py      # Drawing-based rule evaluation
│   │   │   ├── fusion_engine.py    # Decision fusion logic
│   │   │   └── certificate_gen.py  # PDF generation
│   │   ├── db/
│   │   │   ├── __init__.py
│   │   │   ├── database.py        # SQLite async setup
│   │   │   └── schema.py          # Table definitions
│   │   └── utils/
│   │       ├── __init__.py
│   │       ├── image_processing.py # Resize, heatmap overlay, etc.
│   │       └── xai.py             # Heatmap generation utilities
│   ├── ai_models/                  # Pre-trained ONNX model files
│   │   ├── patchcore/
│   │   │   └── (model files per texture class)
│   │   └── yolov8/
│   │       └── defect_detector.onnx
│   ├── demo_data/
│   │   ├── parts/                  # Part master JSON seeds
│   │   ├── images/                 # Pre-staged inspection images
│   │   │   ├── metal_plate/
│   │   │   ├── screw/
│   │   │   ├── weldment/
│   │   │   ├── cable/
│   │   │   └── pcb/
│   │   ├── golden_samples/         # Golden reference images
│   │   ├── drawings/               # Simulated engineering drawings
│   │   └── scenarios/              # Pre-built demo scenario configs
│   ├── tests/
│   ├── requirements.txt
│   ├── Dockerfile
│   └── pyproject.toml
├── frontend/
│   ├── src/
│   │   ├── main.tsx
│   │   ├── App.tsx
│   │   ├── router.tsx              # React Router config
│   │   ├── api/                    # API client (React Query)
│   │   │   ├── client.ts
│   │   │   ├── inspections.ts
│   │   │   ├── parts.ts
│   │   │   ├── review.ts
│   │   │   ├── dashboard.ts
│   │   │   └── demo.ts
│   │   ├── components/
│   │   │   ├── common/             # Shared: Button, Badge, Modal, KPITile
│   │   │   ├── kiosk/             # Operator station screens
│   │   │   │   ├── ScanScreen.tsx
│   │   │   │   ├── CaptureScreen.tsx
│   │   │   │   ├── ResultScreen.tsx
│   │   │   │   └── KioskLayout.tsx
│   │   │   ├── review/            # IQA workbench
│   │   │   │   ├── ReviewQueue.tsx
│   │   │   │   ├── ReviewWorkbench.tsx
│   │   │   │   ├── ImageViewer.tsx
│   │   │   │   ├── FindingsList.tsx
│   │   │   │   ├── OverrideModal.tsx
│   │   │   │   └── GoldenCompare.tsx
│   │   │   ├── dashboard/         # Analytics dashboards
│   │   │   │   ├── InspectionDashboard.tsx
│   │   │   │   ├── DefectDashboard.tsx
│   │   │   │   ├── SupplierDashboard.tsx
│   │   │   │   ├── AIPerformanceDashboard.tsx
│   │   │   │   └── DashboardLayout.tsx
│   │   │   ├── certificate/
│   │   │   │   └── CertificateViewer.tsx
│   │   │   └── demo/
│   │   │       ├── PresenterPanel.tsx
│   │   │       └── ScenarioSelector.tsx
│   │   ├── hooks/                  # Custom React hooks
│   │   ├── types/                  # TypeScript type definitions
│   │   ├── utils/                  # Helpers
│   │   └── styles/                 # Tailwind config + globals
│   ├── public/
│   │   └── audio/                  # PASS/FAIL/REVIEW audio cues
│   ├── index.html
│   ├── package.json
│   ├── tsconfig.json
│   ├── vite.config.ts
│   ├── tailwind.config.ts
│   └── Dockerfile
├── docker-compose.yml
├── Makefile
└── README.md
```

## 3. Component Design

### 3.1 AI Pipeline Service (`backend/app/services/ai_pipeline.py`)

Orchestrates the three inspection approaches and produces a fused decision.

```python
# Pseudocode interface
class AIPipeline:
    async def inspect(self, inspection_id: str, images: list[InspectionImage], 
                      part: PartRevision, rules: InspectionRuleset,
                      golden_set: GoldenSet | None) -> InspectionResult:
        # Run all three approaches in parallel
        rule_findings = await self.rule_engine.evaluate(images, rules)
        golden_findings = await self.golden_comparator.compare(images, golden_set)
        ai_findings = await self.ai_detector.detect(images, part.family)
        
        # Fuse into unified decision
        all_findings = rule_findings + golden_findings + ai_findings
        decision = self.fusion_engine.decide(all_findings, part.family.thresholds)
        
        return InspectionResult(findings=all_findings, decision=decision)
```

**Approach 1 — Rule Engine** (`rule_engine.py`):
- Loads rules per part family (JSON-defined: expected features, counts, zones)
- Evaluates presence/absence using pre-computed detections from YOLO
- Produces deterministic rule findings with PASS/FAIL per rule
- Demo rules cover: screw count verification, label presence, orientation check

**Approach 2 — Golden Sample Comparator** (`golden_comparator.py`):
- Loads golden reference images for the part family
- Performs image registration (feature-based alignment using ORB/SIFT)
- Computes structural similarity (SSIM) + absolute difference
- Produces difference heatmap with configurable tolerance bands
- Findings: regions exceeding tolerance threshold

**Approach 3 — AI Defect Detection** (`anomaly_detector.py` + `defect_detector.py`):
- **Anomaly Detection (PatchCore):** Pre-trained on MVTec AD textures (metal, grid, screw, wood). Produces pixel-level anomaly score maps. Thresholded to produce anomaly findings.
- **Object Detection (YOLOv8):** Fine-tuned or pre-trained on industrial defect datasets. Produces bounding boxes with class labels (scratch, dent, contamination, missing_component, crack). Confidence scores per detection.
- Both run via ONNX Runtime (CPU mode for portability; GPU optional).

**Fusion Engine** (`fusion_engine.py`):
- Implements fusion rules F-01 through F-07 from Spec 03:
  - Hard-fail rules → FAIL regardless
  - High-confidence model findings above threshold → FAIL
  - REVIEW band (between thresholds) → REVIEW
  - Golden-diff corroboration escalates severity
  - No findings above floor → PASS
- Thresholds are per-family, loaded from config

### 3.2 Data Models (`backend/app/models/`)

```python
# Core domain models (Pydantic v2)

class PartFamily(BaseModel):
    id: str
    name: str  # e.g., "machined-aluminum-plate"
    display_name: str
    material: str
    surface_finish: str
    thresholds: FamilyThresholds
    capture_profile: CaptureProfile

class InspectionStatus(str, Enum):
    IDENTIFIED = "identified"
    CAPTURING = "capturing"
    INSPECTING = "inspecting"
    PASSED = "passed"
    FAILED = "failed"
    IN_REVIEW = "in_review"
    OVERRIDDEN = "overridden"

class Finding(BaseModel):
    id: str
    defect_class: str
    approach: Literal["rule", "golden", "model", "anomaly"]
    confidence: float  # 0.0 - 1.0
    severity: Literal["minor", "major", "critical"]
    bbox: BoundingBox | None
    mask_url: str | None
    heatmap_url: str | None
    description: str

class Decision(BaseModel):
    result: Literal["PASS", "FAIL", "REVIEW"]
    fusion_rule: str  # Which fusion rule triggered
    findings_count: int
    confidence_summary: dict

class Override(BaseModel):
    new_decision: Literal["PASS", "FAIL"]
    reason_code: str  # OR-01 through OR-07
    comment: str
    reviewer: str
    timestamp: datetime
```

### 3.3 API Design (`backend/app/routers/`)

| Endpoint | Method | Purpose | Response |
|---|---|---|---|
| `/api/v1/parts/{part_number}` | GET | Look up part by number | Part + family + rules |
| `/api/v1/inspections` | POST | Create new inspection session | Inspection record |
| `/api/v1/inspections/{id}/capture` | POST | Trigger simulated capture | Image set with quality results |
| `/api/v1/inspections/{id}/inspect` | POST | Run AI pipeline | Findings + decision |
| `/api/v1/inspections/{id}` | GET | Get full inspection record | Full record with images + findings |
| `/api/v1/inspections` | GET | List/search inspections | Paginated list |
| `/api/v1/review/queue` | GET | Get IQA review queue | Prioritized queue |
| `/api/v1/review/{id}/override` | POST | Submit override | Updated record |
| `/api/v1/review/{id}/confirm` | POST | Confirm AI decision | Updated record |
| `/api/v1/dashboard/inspection` | GET | Inspection dashboard data | KPIs + charts |
| `/api/v1/dashboard/defects` | GET | Defect analytics | Pareto + trends |
| `/api/v1/dashboard/suppliers` | GET | Supplier quality data | Supplier league table |
| `/api/v1/dashboard/ai-performance` | GET | Model performance | Accuracy + FP/FN |
| `/api/v1/certificates/{id}` | GET | Get certificate metadata | Certificate + PDF URL |
| `/api/v1/certificates/{id}/pdf` | GET | Download PDF | PDF file |
| `/api/v1/certificates/verify/{token}` | GET | QR verification | Validity + summary |
| `/api/v1/demo/scenarios` | GET | List demo scenarios | Scenario list |
| `/api/v1/demo/scenarios/{id}/run` | POST | Execute a demo scenario | Inspection ID |
| `/api/v1/demo/reset` | POST | Reset all data | Confirmation |

### 3.4 Frontend Architecture

**Framework:** React 18 + TypeScript (strict) + Vite + Tailwind CSS v3 + React Query v5 + React Router v6 + Recharts

**Route Structure:**
```
/                        → Redirect to /kiosk
/kiosk                   → Operator kiosk (ScanScreen)
/kiosk/capture/:id       → Capture screen
/kiosk/result/:id        → Result screen (PASS/FAIL/REVIEW)
/review                  → IQA review queue
/review/:id              → Review workbench
/dashboard               → Dashboard home (tabs)
/dashboard/inspection    → Inspection dashboard
/dashboard/defects       → Defect dashboard
/dashboard/suppliers     → Supplier dashboard
/dashboard/ai            → AI Performance dashboard
/certificates/:id       → Certificate viewer
/demo                    → Presenter panel (hidden, keyboard shortcut Ctrl+Shift+D)
```

**Design System:**
- Colors: PASS `#1E8E3E`, FAIL `#C0392B`, REVIEW `#E67E22`, info `#156082` (from Spec 06)
- Typography: Inter font; kiosk min 18px body; decision states 72pt+
- Touch targets: ≥ 48px (gloves-first)
- Density: Kiosk mode (sparse, large); Review mode (analyst, denser)
- All status indicators use color + icon + label (never color-only)

**Key Components:**

| Component | Purpose | Key Behavior |
|---|---|---|
| `ScanScreen` | Part identification entry point | Keyboard input simulates barcode; auto-advances on valid part |
| `CaptureScreen` | Multi-camera capture simulation | Grid of camera views with animated capture + quality indicators |
| `ResultScreen` | Full-screen decision display | 72pt decision text; auto-dismiss on PASS; audio cue |
| `ReviewQueue` | Prioritized list of pending reviews | Sortable table; claim locking simulation; filters |
| `ReviewWorkbench` | Three-pane evidence review | Image canvas with overlay toggles; findings list; context panel |
| `ImageViewer` | Zoomable image with overlays | Pan/zoom; toggle layers (bbox, mask, heatmap, golden diff) |
| `OverrideModal` | Override form with reason codes | Required fields; validation; submit |
| `GoldenCompare` | Side-by-side slider comparison | Synchronized slider revealing test vs. golden |
| `InspectionDashboard` | Real-time ops view | KPI tiles + station status + decision stream |
| `DefectDashboard` | Defect analytics | Pareto (Recharts bar); trend lines; heatmap |
| `PresenterPanel` | Demo control (hidden) | Scenario list; run button; reset; auto-cycle toggle |

### 3.5 Image Viewer & Overlay Engine

The image viewer is the most complex UI component. Design:

```
┌─────────────────────────────────────────────┐
│ Filmstrip (all angles: top, N, S, E, W)     │
├─────────────────────────────────────────────┤
│                                             │
│           Main Canvas                       │
│   ┌─────────────────────────────────┐       │
│   │  Base image                     │       │
│   │  + Bounding boxes (toggle)      │       │
│   │  + Segmentation masks (toggle)  │       │
│   │  + XAI heatmap (toggle, alpha)  │       │
│   │  + Golden diff (toggle)         │       │
│   └─────────────────────────────────┘       │
│                                             │
├─────────────────────────────────────────────┤
│ Overlay controls: [□ Boxes] [□ Masks]       │
│                   [□ Heatmap] [□ Golden]    │
│ Zoom: [−] ──●── [+]  | Fit | 1:1           │
└─────────────────────────────────────────────┘
```

Implementation: HTML Canvas or a lightweight image library (e.g., OpenSeadragon for deep zoom, or custom Canvas with transform matrix for pan/zoom). Overlays rendered as semi-transparent layers composited on the base image.

### 3.6 Certificate Generator (`backend/app/services/certificate_gen.py`)

- Uses `reportlab` or `weasyprint` for PDF generation
- Template: Lam-style header (simulated), part info, decision badge, findings table, thumbnail grid (4 images), QR code (generated with `qrcode` library)
- QR encodes a verification URL: `/api/v1/certificates/verify/{token}`
- Token is a short UUID stored with the certificate record

### 3.7 Demo Data Strategy

**Image Sources:**
- MVTec Anomaly Detection dataset: metal_nut, screw, grid, tile, leather textures — provides real anomaly detection targets
- Additional public industrial defect datasets: NEU surface defects (metal), Severstal steel defects
- Synthetic images: stock photos of machined parts, PCBs, cables annotated for the demo

**Part Families (5):**

| Family | Demo Source | Defect Demo |
|---|---|---|
| Machined Aluminum Plate | MVTec metal_nut + stock | Scratches, dents, contamination |
| Precision Screw Assembly | MVTec screw | Missing screws, wrong orientation |
| Welded Stainless Component | NEU surface defects | Cracks, surface anomalies |
| PCB Sub-assembly | Stock PCB images | Missing components, solder defects |
| Anodized Housing | MVTec grid/tile | Surface contamination, chips |

**Demo Scenarios (10):**

| # | Name | Family | Expected Decision | Demonstrates |
|---|---|---|---|---|
| 1 | Clean machined plate | Aluminum Plate | PASS | Happy path, fast cycle |
| 2 | Scratched plate | Aluminum Plate | FAIL | AI scratch detection + heatmap |
| 3 | Dented housing | Anodized Housing | FAIL | Anomaly detection + golden diff |
| 4 | Missing screw | Screw Assembly | FAIL | Rule engine (4/4 → 3/4) + detection |
| 5 | Surface contamination | Welded Component | FAIL | Segmentation mask + severity |
| 6 | Unknown anomaly | Aluminum Plate | REVIEW | Anomaly-only, no supervised class |
| 7 | Golden deviation (subtle) | Anodized Housing | REVIEW | Golden comparison focus |
| 8 | Multi-defect critical | PCB Assembly | FAIL | Multiple findings, high severity |
| 9 | Low-confidence edge case | Welded Component | REVIEW | Confidence near threshold |
| 10 | Override scenario | Aluminum Plate | FAIL → Override PASS | Full review + override flow |

### 3.8 Database Schema (SQLite)

```sql
-- Simplified for PoC (no migrations needed)
CREATE TABLE parts (
    id TEXT PRIMARY KEY,
    part_number TEXT UNIQUE NOT NULL,
    revision TEXT NOT NULL,
    family_id TEXT NOT NULL,
    description TEXT,
    material TEXT,
    surface_finish TEXT,
    supplier TEXT,
    metadata JSON
);

CREATE TABLE inspections (
    id TEXT PRIMARY KEY,
    part_id TEXT NOT NULL REFERENCES parts(id),
    status TEXT NOT NULL DEFAULT 'identified',
    decision TEXT,  -- PASS/FAIL/REVIEW
    decision_basis JSON,
    started_at TEXT NOT NULL,
    decided_at TEXT,
    scenario_id TEXT,
    FOREIGN KEY (part_id) REFERENCES parts(id)
);

CREATE TABLE images (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    camera_angle TEXT NOT NULL,  -- top, n, s, e, w
    file_path TEXT NOT NULL,
    quality_result JSON,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE findings (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    image_id TEXT,
    defect_class TEXT NOT NULL,
    approach TEXT NOT NULL,  -- rule, golden, model, anomaly
    confidence REAL,
    severity TEXT,
    bbox JSON,
    heatmap_path TEXT,
    mask_path TEXT,
    description TEXT,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE overrides (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL,
    old_decision TEXT NOT NULL,
    new_decision TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    comment TEXT NOT NULL,
    reviewer TEXT NOT NULL,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);

CREATE TABLE certificates (
    id TEXT PRIMARY KEY,
    inspection_id TEXT NOT NULL UNIQUE,
    token TEXT UNIQUE NOT NULL,
    pdf_path TEXT,
    created_at TEXT NOT NULL,
    FOREIGN KEY (inspection_id) REFERENCES inspections(id)
);
```

### 3.9 Docker Compose Configuration

```yaml
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    volumes:
      - ./backend/demo_data:/app/demo_data
      - ./backend/ai_models:/app/ai_models
      - poc_data:/app/data  # SQLite + generated images/certs
    environment:
      - AVIP_ENV=demo
      - AVIP_DATA_DIR=/app/data
      - AVIP_MODELS_DIR=/app/ai_models
      - AVIP_DEMO_DATA_DIR=/app/demo_data

  frontend:
    build: ./frontend
    ports:
      - "3000:80"
    depends_on:
      - backend

volumes:
  poc_data:
```

## 4. AI Model Strategy (PoC-specific)

### 4.1 Anomaly Detection — PatchCore

- **Why:** Works with zero defect examples (only needs ~50 good images); perfect for cold-start PoC
- **Implementation:** Use `anomalib` library's PatchCore implementation, export to ONNX
- **Pre-training:** Train on MVTec AD categories (metal_nut, screw, grid) during build — include pre-trained weights in Docker image
- **Output:** Per-pixel anomaly score map (0.0–1.0); threshold to binary anomaly mask
- **XAI:** Anomaly score map IS the heatmap — direct visualization

### 4.2 Defect Detection — YOLOv8

- **Why:** Fast, accurate, well-supported; ONNX export straightforward
- **Implementation:** YOLOv8n or YOLOv8s (small model for CPU speed)
- **Pre-training:** Use a pre-trained model on industrial defect datasets (or train on NEU + synthetic for 5 classes)
- **Output:** Bounding boxes with class + confidence
- **Classes:** scratch, dent, contamination, missing_component, crack
- **Fallback:** If training is insufficient, use a general defect detector and map post-hoc; or simulate detections from pre-annotated demo images

### 4.3 Golden Comparison — Classical CV

- **No model needed:** Registration (ORB feature matching + homography) + SSIM + absolute difference
- **Implementation:** OpenCV-based; deterministic
- **Output:** Difference heatmap (per-pixel deviation from golden); regions above threshold become findings

### 4.4 Model Packaging

All models packaged as ONNX files in `backend/ai_models/`. ONNX Runtime (CPU) used for inference — no GPU driver dependency. Total model size target: < 500 MB (fits in Docker image without bloat).

## 5. Performance Budget

| Operation | Target | Approach |
|---|---|---|
| Part lookup | < 100 ms | SQLite indexed query |
| Capture simulation | < 3 s | Pre-loaded images + simulated delay |
| Anomaly detection (per image) | < 2 s | PatchCore ONNX on CPU (224×224 input) |
| Object detection (per image) | < 500 ms | YOLOv8n ONNX on CPU (640×640) |
| Golden comparison (per image) | < 1 s | OpenCV registration + SSIM |
| Full inspection (5 images × 3 approaches) | < 5 s | Parallel execution where possible |
| Certificate PDF generation | < 2 s | ReportLab template |
| Dashboard data load | < 500 ms | Pre-aggregated in SQLite |
| UI render (any screen) | < 200 ms | React with minimal re-renders |

## 6. Security (PoC Scope)

- No authentication required (demo mode)
- CORS open for localhost development
- No PII in demo data
- No external network calls at runtime
- All data resets on `docker compose down -v`

## 7. Traceability to Requirements

| Requirement | Design Components |
|---|---|
| Req 1 (Part ID) | Parts router, Part model, ScanScreen, demo part master |
| Req 2 (Capture) | Inspections router (capture), CaptureScreen, image quality simulation |
| Req 3 (AI Detection) | anomaly_detector, defect_detector, ONNX models, XAI heatmaps |
| Req 4 (Three-Approach Fusion) | ai_pipeline, rule_engine, golden_comparator, fusion_engine |
| Req 5 (Decision Display) | ResultScreen, audio cues, auto-dismiss logic |
| Req 6 (Review Workbench) | Review router, ReviewQueue, ReviewWorkbench, ImageViewer, OverrideModal |
| Req 7 (Dashboards) | Dashboard router, 4 dashboard components, Recharts, demo data |
| Req 8 (Certificate) | certificate_gen, Certificates router, CertificateViewer, QR code |
| Req 9 (Demo Scenarios) | Demo router, PresenterPanel, ScenarioSelector, scenario configs |
| Req 10 (Deployment) | docker-compose.yml, Dockerfiles, README, Makefile |
