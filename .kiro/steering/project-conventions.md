---
inclusion: always
---

# AVIP PoC — Project Conventions & Context

## Project Overview

This is the **AI Vision Inspection Platform (AVIP) Proof of Concept** for Lam Research. It demonstrates automated cosmetic inspection of semiconductor manufacturing parts using AI/computer vision.

The PoC validates the full workflow: part identification → multi-angle image capture → AI inspection (three approaches) → decision fusion → IQA review → certificate generation.

## Architecture

- **Backend:** Python 3.12, FastAPI, ONNX Runtime, OpenCV, SQLite (single file DB at `backend/data/avip.db`)
- **Frontend:** React 18, TypeScript (strict), Tailwind CSS v3, React Query v5, Vite
- **AI Models:** PatchCore (anomaly detection) + YOLOv8 (defect detection) as ONNX files in `backend/ai_models/`
- **Dev ports:** Backend on 8001, Frontend on 3000 (Vite proxies `/api` and `/static` to backend)

## Code Style

### Backend (Python)
- Use type hints everywhere
- Pydantic models for all request/response schemas
- Async handlers (FastAPI async def)
- Line length: 100 chars (ruff/black)
- Import order: stdlib → third-party → app modules
- Service classes in `app/services/`, route handlers in `app/routers/`
- All DB access through `app/db/database.py` (aiosqlite)

### Frontend (TypeScript/React)
- Strict TypeScript — avoid `any`
- Functional components only (no class components)
- React Query for all server state
- Tailwind for styling — no CSS modules or styled-components
- File naming: PascalCase for components, camelCase for utilities
- Custom colors use the `avip-` prefix (pass/fail/review/info)
- All API calls go through `src/api/client.ts`

## Key Design Decisions

1. **Three-approach fusion:** Every inspection runs rules + golden comparison + AI detection, results are fused via `FusionEngine` with rules F-01 through F-06
2. **Idempotent endpoints:** Both `/capture` and `/inspect` are safe to call multiple times (guard against React StrictMode double-renders)
3. **Demo scenarios vs real inference:** Demo panel uses scripted results (`SCENARIO_RESULTS` dict); kiosk flow uses actual ONNX model inference
4. **Image serving:** Demo images at `/static/demo-images/{family}/{angle}.jpg`; runtime data at `/static/` (from `backend/data/`)
5. **Part family mapping:** Each part belongs to a family that determines inspection rules, thresholds, capture profile, and which demo images to use

## Part Families → Image Folders

| Family Display Name | Image Folder |
|---|---|
| Machined Aluminum Plate | metal_plate |
| Precision Screw Assembly | screw |
| PCB Sub-Assembly | pcb |
| Welded Stainless Component | weldment |
| Anodized Housing | metal_plate |
| Cable Assembly | cable |

## API Conventions

- All endpoints prefixed with `/api/v1/`
- List endpoints return `{ data: [...], total_count: N }`
- Errors use FastAPI HTTPException with detail (string or object)
- Decision values: `"PASS"`, `"FAIL"`, `"REVIEW"` (uppercase)
- Status values: `"identified"`, `"capturing"`, `"inspecting"`, `"passed"`, `"in_review"`, `"overridden"`

## Running Locally

```bash
# Backend (from backend/ dir, with .venv activated)
.venv/bin/uvicorn app.main:app --reload --host 0.0.0.0 --port 8001

# Frontend (from frontend/ dir)
npm run dev
```

## Important Notes

- The vite proxy in `frontend/vite.config.ts` points to port **8001** (not 8000)
- ONNX models must be regenerated locally (not committed to git due to size) — use the dummy model creation pattern from the codebase
- `backend/data/` is gitignored (SQLite DB created at runtime)
- Reset demo data: `POST /api/v1/demo/reset`
