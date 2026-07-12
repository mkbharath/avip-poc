# AVIP — AI Vision Inspection Platform (Proof of Concept)

A working demonstration of the AI Vision Inspection Platform for Lam Research. This PoC showcases real AI defect detection, the three-approach inspection fusion, operator kiosk workflow, IQA review workbench, and operational dashboards.

## Quick Start

```bash
# Development mode (requires Python 3.12+ and Node.js 20+)
make setup
# Then in two terminals:
make dev-backend
make dev-frontend
```

Or with Docker:
```bash
make build
make run
# Frontend: http://localhost:3000
# Backend API: http://localhost:8000
# API docs: http://localhost:8000/docs
```

## Architecture

```
Browser (React SPA) ──── REST API ──── FastAPI Backend
                                           │
                                    ┌──────┼──────┐
                                    │      │      │
                              AI Pipeline  DB   Static Files
                              (3 approaches) (SQLite) (images, certs)
```

**Three Inspection Approaches:**
1. **Drawing-Based Rules** — Deterministic feature verification (screw count, label presence, orientation)
2. **Golden Sample Comparison** — Registered image diff with tolerance heatmaps
3. **AI Defect Detection** — PatchCore anomaly detection + YOLOv8 object detection

## Demo Scenarios

The PoC includes 10 pre-built scenarios accessible from the Presenter Panel (`/demo` or Ctrl+Shift+D):

| # | Scenario | Expected | Demonstrates |
|---|---|---|---|
| 1 | Clean Machined Plate | PASS | Happy path, fast cycle |
| 2 | Scratched Plate | FAIL | AI scratch detection + XAI heatmap |
| 3 | Dented Housing | FAIL | Anomaly + golden comparison |
| 4 | Missing Screw | FAIL | Rule engine (8 expected, 7 found) |
| 5 | Surface Contamination | FAIL | Segmentation mask + severity |
| 6 | Unknown Anomaly | REVIEW | Anomaly-only, no class match |
| 7 | Golden Deviation | REVIEW | Golden comparison slider |
| 8 | Multi-Defect Critical | FAIL | Compound findings |
| 9 | Low-Confidence Edge | REVIEW | Near-threshold confidence |
| 10 | Override Scenario | FAIL→PASS | Full IQA review + override |

## Tech Stack

- **Backend:** Python 3.12, FastAPI, ONNX Runtime, OpenCV, SQLite
- **Frontend:** React 18, TypeScript (strict), Tailwind CSS v3, React Query v5, Recharts
- **AI:** PatchCore (anomaly detection), YOLOv8 (defect detection), OpenCV (golden comparison)
- **Deployment:** Docker Compose

## Project Structure

```
avip-poc/
├── backend/
│   ├── app/
│   │   ├── main.py           # FastAPI entry point
│   │   ├── models/           # Pydantic domain models
│   │   ├── routers/          # API endpoints
│   │   ├── services/         # AI pipeline, certificate gen
│   │   └── db/               # SQLite setup + seed data
│   ├── ai_models/            # ONNX model files
│   └── demo_data/            # Pre-staged images + scenarios
├── frontend/
│   └── src/
│       ├── components/
│       │   ├── kiosk/        # Operator station screens
│       │   ├── review/       # IQA workbench
│       │   ├── dashboard/    # Analytics dashboards
│       │   └── demo/         # Presenter controls
│       ├── types/            # TypeScript types
│       └── api/              # API client
├── docker-compose.yml
└── Makefile
```

## Useful Commands

```bash
make dev-backend     # Run backend in dev mode (hot reload)
make dev-frontend    # Run frontend in dev mode (hot reload)
make build           # Build Docker images
make run             # Start all services
make stop            # Stop all services
make reset           # Reset demo data
make test            # Run backend tests
```
