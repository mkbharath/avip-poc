"""AVIP PoC — FastAPI Application Entry Point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.db.database import close_db, init_db
from app.routers import ai, certificates, dashboard, demo, inspections, parts, review


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application startup and shutdown."""
    # Startup
    settings.ensure_dirs()
    await init_db()
    yield
    # Shutdown
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

# Serve demo label images for OCR feature (must mount before broader /static)
labels_dir = settings.demo_data_dir / "labels"
if labels_dir.exists():
    app.mount("/static/labels", StaticFiles(directory=str(labels_dir)), name="labels")

# Serve demo part images
demo_images_dir = settings.demo_data_dir / "images"
if demo_images_dir.exists():
    app.mount("/static/demo-images", StaticFiles(directory=str(demo_images_dir)), name="demo-images")

# Static files for images, heatmaps, certificates
settings.data_dir.mkdir(parents=True, exist_ok=True)
app.mount("/static", StaticFiles(directory=str(settings.data_dir)), name="static")


@app.get("/api/v1/health")
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy", "service": "avip-poc", "version": "0.1.0"}
