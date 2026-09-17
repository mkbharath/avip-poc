"""AVIP PoC — FastAPI Application Entry Point."""

import asyncio
import logging
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import close_db, init_db
from app.routers import (
    ai,
    certificates,
    dashboard,
    demo,
    inspections,
    parts,
    review,
    source_comparison,
    tpi,
)
from app.services import ingestion
from app.services.sc_config import comparison_config, validate_assumptions
from app.services.source_adapters import SimulatorAdapter
from app.services.worker import Worker

logger = logging.getLogger("app.main")


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown.

    Mirrors the existing ``ensure_dirs`` -> ``init_db`` -> yield -> ``close_db``
    structure, and additionally starts/stops the source-comparison background
    worker and (optionally) the simulator adapter as ``asyncio`` tasks
    (Req 1.5, 9.1). References are stored on ``app.state`` so the status
    endpoint and shutdown path can reach them.

    Startup is robust: a failure to start the worker or simulator is logged and
    does not crash application startup — the rest of AVIP keeps serving.
    Shutdown stops the simulator first (so no new work is enqueued), then the
    worker, then closes the DB last so no task touches a closed connection.
    """
    # Startup
    settings.ensure_dirs()
    await init_db()

    # Surface the assumption / [CONFIRM] items in structured logs at startup so
    # resolved-by-assumption decisions and any unresolved placeholder are
    # observable (Req 8.5, 9.4). Never crashes startup.
    try:
        validate_assumptions(comparison_config)
    except Exception:  # noqa: BLE001 — logging assumptions must not crash startup
        logger.exception("Failed to validate source-comparison assumptions")

    # Background worker: drains the ingest queue, aligns + compares records as
    # they stream in (Req 1.5, 9.1). Start it as a background task; a failure to
    # start is logged but does not crash startup.
    app.state.sc_worker = None
    app.state.sc_simulator = None
    app.state.sc_simulator_task = None
    try:
        worker = Worker()
        worker.start()
        app.state.sc_worker = worker
        logger.info("Source-comparison background worker started")
    except Exception:  # noqa: BLE001 — worker failure must not crash startup
        logger.exception("Failed to start source-comparison background worker")

    # Simulator adapter (optional, toggled by AVIP_SC_SIMULATOR, default on for
    # the demo). Pushes simulated LAIR/FAIR/SHQ records through the ingestion
    # path. A failure to start is logged but does not crash startup.
    if settings.sc_simulator_enabled:
        try:
            simulator = SimulatorAdapter()
            sim_task = asyncio.create_task(
                simulator.run_forever(push_fn=ingestion.ingest),
                name="sc-simulator",
            )
            app.state.sc_simulator = simulator
            app.state.sc_simulator_task = sim_task
            logger.info("Source-comparison simulator started")
        except Exception:  # noqa: BLE001 — simulator failure must not crash startup
            logger.exception("Failed to start source-comparison simulator")
    else:
        logger.info(
            "Source-comparison simulator disabled (AVIP_SC_SIMULATOR=false)"
        )

    try:
        yield
    finally:
        # Shutdown — stop the simulator first (no new work), then the worker,
        # then close the DB last. Each step is guarded so a failure in one does
        # not block the others or the DB close.
        simulator = getattr(app.state, "sc_simulator", None)
        sim_task = getattr(app.state, "sc_simulator_task", None)
        if simulator is not None:
            try:
                simulator.stop()
            except Exception:  # noqa: BLE001
                logger.exception("Failed to signal source-comparison simulator stop")
        if sim_task is not None:
            try:
                sim_task.cancel()
                await asyncio.gather(sim_task, return_exceptions=True)
                logger.info("Source-comparison simulator stopped")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to stop source-comparison simulator task")

        worker = getattr(app.state, "sc_worker", None)
        if worker is not None:
            try:
                await worker.stop()
                logger.info("Source-comparison background worker stopped")
            except Exception:  # noqa: BLE001
                logger.exception("Failed to stop source-comparison background worker")

        await close_db()


app = FastAPI(
    title="AVIP PoC API",
    description="AI Vision Inspection Platform — Proof of Concept",
    version="0.1.0",
    lifespan=lifespan,
)

# CORS — open for development/demo
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
app.include_router(parts.router, prefix="/api/v1", tags=["Parts"])
app.include_router(inspections.router, prefix="/api/v1", tags=["Inspections"])
app.include_router(review.router, prefix="/api/v1", tags=["Review"])
app.include_router(dashboard.router, prefix="/api/v1", tags=["Dashboard"])
app.include_router(certificates.router, prefix="/api/v1", tags=["Certificates"])
app.include_router(demo.router, prefix="/api/v1", tags=["Demo"])
app.include_router(ai.router, prefix="/api/v1", tags=["AI"])
app.include_router(source_comparison.router, prefix="/api/v1", tags=["Source Comparison"])
app.include_router(tpi.router, prefix="/api/v1", tags=["TPI Generation"])

# Serve demo label images for OCR feature (must mount before broader /static)
labels_dir = settings.demo_data_dir / "labels"
if labels_dir.exists():
    app.mount("/static/labels", StaticFiles(directory=str(labels_dir)), name="labels")

# Serve demo part images
demo_images_dir = settings.demo_data_dir / "images"
if demo_images_dir.exists():
    app.mount("/static/demo-images", StaticFiles(directory=str(demo_images_dir)), name="demo-images")

# Serve the PCBA TPI sample fixtures (circuit diagrams / drawings) so the review
# workbench can preview the SAMPLE PCBAs' images too. These live under
# backend/sample_data/tpi (NOT under data_dir), so they get their own mount;
# tpi.py's preview_url logic maps such refs to /static/tpi-samples/<relpath>.
# Must mount before the broader /static below (more specific path first).
tpi_samples_dir = Path(__file__).resolve().parents[1] / "sample_data" / "tpi"
if tpi_samples_dir.exists():
    app.mount(
        "/static/tpi-samples",
        StaticFiles(directory=str(tpi_samples_dir)),
        name="tpi-samples",
    )

# Static files for images, heatmaps, certificates
settings.data_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.data_dir)), name="static")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "avip-poc", "version": "0.1.0"}
