"""PCBA TPI Generation router.

FastAPI router for the PCBA TPI Generation feature, registered in ``main.py`` as::

    app.include_router(tpi.router, prefix="/api/v1", tags=["TPI Generation"])

This module owns a single ``router = APIRouter()`` that later tasks append their
endpoints to (design: "API endpoints" section). The full endpoint surface — all
mounted under the ``/api/v1`` prefix — is:

  * ``POST /tpi/pcbas/{pcba_id}/inputs``    — ingest the four inputs (task 8.1)
  * ``POST /tpi/pcbas/{pcba_id}/process``   — extract -> map -> generate (task 8.1)
  * ``GET  /tpi/pcbas``                      — list PCBAs + pipeline status (task 8.2)
  * ``GET  /tpi/pcbas/{pcba_id}``            — PCBA detail (task 8.2)
  * ``GET  /tpi/drafts``                     — drafts for review (task 8.2)
  * ``GET  /tpi/drafts/{pcba_id}``           — single draft + provenance (task 8.2)
  * ``POST /tpi/drafts/{pcba_id}/finalize``  — record corrections + audit (task 8.3)
  * ``GET  /tpi/final``                      — finalized TPIs only (task 8.2)
  * ``GET  /tpi/final/{pcba_id}/export``     — download TPI document (task 8.3)
  * ``GET  /tpi/audit/{pcba_id}``            — review audit trail (task 8.2)
  * ``GET  /tpi/status``                     — pipeline/config status + [CONFIRM] banner (task 8.3)

Conventions mirror ``routers/source_comparison.py``: a single shared
``router = APIRouter()`` that every endpoint hangs off; list endpoints return the
``{data, total_count}`` envelope; ``JSONResponse`` carries explicit status codes
(``404`` for a missing draft/PCBA, ``400`` for a service ``ValueError``); binary
downloads use ``Response`` with the appropriate ``media_type`` and a
``Content-Disposition`` header; and services are called directly (no business
logic in the router). Request bodies are typed Pydantic models so the schema is
documented and validated, matching how ``source_comparison`` uses
``DecideRequest`` / ``BulkDecideRequest``.
"""

from __future__ import annotations

import logging
import re
from pathlib import Path

from fastapi import APIRouter, File, Query, Request, UploadFile
from fastapi.responses import JSONResponse, Response
from pydantic import BaseModel, Field

from app.config import settings
from app.db.database import get_db
from app.services import tpi_review
from app.services.tpi_document import render_tpi_document
from app.services.tpi_extraction import extract_input, get_extractions
from app.services.tpi_generation import get_draft, process_pcba
from app.services.tpi_ingestion import UploadedFile, get_inputs, ingest_pcba
from app.services.tpi_llm_provider import (
    get_multimodal_provider,
    get_multimodal_provider_by_name,
)
from app.services.tpi_mapping import TpiSection
from app.services.tpi_types import InputStatus, InputType

logger = logging.getLogger("app.tpi.router")

# On-disk root for the bundled sample fixtures (backend/sample_data/tpi). Kept
# in sync with the static mount in main.py so previewable sample images resolve
# to /static/tpi-samples/<relpath>. tpi.py lives at app/routers/tpi.py, so the
# backend root is three parents up.
_SAMPLE_TPI_DIR = Path(__file__).resolve().parents[2] / "sample_data" / "tpi"

# Single shared router; every endpoint below hangs off this same instance (the
# source-comparison router uses the same single-router convention). Do not create
# additional routers in this file.
router = APIRouter()


# ── Request / body models (Pydantic, mirroring source_comparison) ────────────


class TpiInputRef(BaseModel):
    """One submitted input for a PCBA, referencing a sample fixture on disk.

    For the prototype the four inputs are described by a JSON body pointing at
    the ``sample_data/tpi`` fixture paths (the simpler, fully testable approach
    versus multipart uploads). ``input_type`` is one of the four confirmed types
    (testing_procedure / operating_procedure / circuit_diagram / drawing);
    ``path`` is the on-disk fixture reference. ``input_type`` is loosely typed
    (``str``) so an unrecognized value reaches the ingestion service, which
    persists it as a flagged row rather than being rejected by body validation
    (Req 1.2 — no input silently dropped).
    """

    input_type: str
    filename: str
    path: str | None = None


class IngestInputsRequest(BaseModel):
    """Body for ``POST /tpi/pcbas/{pcba_id}/inputs`` — the four inputs to ingest."""

    inputs: list[TpiInputRef] = Field(default_factory=list)


class TpiSectionBody(BaseModel):
    """One corrected TPI section submitted at finalize time.

    Mirrors :class:`app.services.tpi_mapping.TpiSection`: a stable ``key``, a
    human ``title``, the corrected ``content``, the ``source_input_ids``
    provenance list (Req 3.3), and the ``incomplete`` flag (Req 3.4). Reconstructed
    into a ``TpiSection`` by the finalize endpoint before handing it to the
    review service.
    """

    key: str
    title: str
    content: str
    source_input_ids: list[str] = Field(default_factory=list)
    incomplete: bool = False


class FinalizeRequest(BaseModel):
    """Body for ``POST /tpi/drafts/{pcba_id}/finalize`` (Req 4.3, 4.4).

    ``reviewer`` and optional ``note`` are recorded on the audit row (who / what,
    Req 4.4); ``corrected_sections`` is the reviewer-approved section list that
    becomes the final TPI (Req 4.3).
    """

    reviewer: str
    note: str | None = None
    corrected_sections: list[TpiSectionBody] = Field(default_factory=list)


# ── Serialization helpers ────────────────────────────────────────────────────


# Visual input types whose stored image file can be previewed in the workbench.
_VISUAL_INPUT_TYPES = frozenset({InputType.circuit_diagram, InputType.drawing})

# Formats that can be shown directly in an <img> tag. A .txt stand-in or a PDF
# is intentionally excluded (a PDF is not simply <img>-previewable).
_PREVIEWABLE_IMAGE_FORMATS = frozenset(
    {"png", "jpeg", "jpg", "gif", "bmp", "tiff"}
)

# Text input types whose stored procedure file can be shown as a readable text
# excerpt in the workbench (contrasted with the visual types, which preview an
# image). Only these two get a ``text_excerpt``.
_TEXT_INPUT_TYPES = frozenset(
    {InputType.testing_procedure, InputType.operating_procedure}
)

# HTML-comment stripper reusing the same approach as tpi_extraction: the sample
# fixtures carry a ``<!-- FIXTURE PENDING ... -->`` header we don't want to show
# to the reviewer. Dependency-free.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", flags=re.DOTALL)

# Collapse runs of 3+ blank lines down to a single blank line so the excerpt
# reads cleanly without huge vertical gaps.
_EXCESS_BLANK_LINES_RE = re.compile(r"\n{3,}")

# Rough character budget for a readable excerpt; longer content is truncated
# with an ellipsis so the panel stays compact.
_TEXT_EXCERPT_MAX_CHARS = 800


def _text_excerpt_for(inp) -> str | None:
    """Compute a cleaned, truncated text excerpt for a TEXT input, or None.

    Emits an excerpt only for text inputs (``testing_procedure`` /
    ``operating_procedure``) whose ``raw_ref`` is an on-disk path to a readable
    file, and never raises. Visual inputs, in-memory refs (``inmem://…``), and
    missing/unreadable files all yield ``None`` (visual inputs use
    ``preview_url`` instead).

    The file is read as utf-8 (``errors="replace"``), HTML comments are stripped
    using the same ``<!--...-->`` regex approach as
    :mod:`app.services.tpi_extraction` (so the ``<!-- FIXTURE PENDING … -->``
    header never surfaces), excessive blank lines are collapsed, the result is
    trimmed, and truncated to ~800 chars (an ``…`` is appended when truncated).
    Dependency-free.
    """
    input_type = getattr(inp, "input_type", None)
    if input_type not in _TEXT_INPUT_TYPES:
        return None

    raw_ref = getattr(inp, "raw_ref", None)
    if not raw_ref or not isinstance(raw_ref, str):
        return None
    # Skip non-path refs (e.g. the in-memory fallback "inmem://…").
    if "://" in raw_ref:
        return None

    try:
        path = Path(raw_ref)
        if not path.is_file():
            return None
        text = path.read_text(encoding="utf-8", errors="replace")
    except (OSError, RuntimeError, ValueError):
        return None

    # Strip HTML comments (fixture header), collapse blank-line runs, trim.
    text = _HTML_COMMENT_RE.sub("", text)
    text = _EXCESS_BLANK_LINES_RE.sub("\n\n", text).strip()
    if not text:
        return None

    if len(text) > _TEXT_EXCERPT_MAX_CHARS:
        text = text[:_TEXT_EXCERPT_MAX_CHARS].rstrip() + "…"

    return text


def _preview_url_for(inp) -> str | None:
    """Compute a web-servable ``/static`` URL for a VISUAL input's image, or None.

    Emits a URL only when ALL of the following hold, and never raises:
      * the input is a visual type (circuit_diagram / drawing),
      * its ``detected_format`` is a directly-previewable raster image
        (png/jpeg/jpg/gif/bmp/tiff — a ``.txt`` stand-in or PDF yields ``None``),
      * its ``raw_ref`` is an on-disk path located under one of the mounted
        static roots:
          - ``settings.data_dir`` (uploaded files spill here; served at
            ``/static/<relpath>``), or
          - ``<backend>/sample_data/tpi`` (sample fixtures; served at
            ``/static/tpi-samples/<relpath>`` — mounted in main.py).

    Text inputs, non-image formats, in-memory refs (``inmem://…``), and files
    outside those roots all yield ``None``. Paths are emitted with posix
    separators so they work as URLs on any OS.
    """
    # Only visual inputs are previewable.
    input_type = getattr(inp, "input_type", None)
    if input_type not in _VISUAL_INPUT_TYPES:
        return None

    # Only directly <img>-previewable raster formats.
    fmt = (getattr(inp, "detected_format", None) or "").strip().lower()
    if fmt not in _PREVIEWABLE_IMAGE_FORMATS:
        return None

    raw_ref = getattr(inp, "raw_ref", None)
    if not raw_ref or not isinstance(raw_ref, str):
        return None
    # Skip non-path refs (e.g. the in-memory fallback "inmem://…").
    if "://" in raw_ref:
        return None

    try:
        path = Path(raw_ref).resolve()
    except (OSError, RuntimeError, ValueError):
        return None

    # 1) Uploaded files under the data dir → /static/<relpath>.
    try:
        data_root = settings.data_dir.resolve()
        rel = path.relative_to(data_root)
        return "/static/" + rel.as_posix()
    except (ValueError, OSError):
        pass

    # 2) Sample fixtures under sample_data/tpi → /static/tpi-samples/<relpath>.
    try:
        samples_root = _SAMPLE_TPI_DIR.resolve()
        rel = path.relative_to(samples_root)
        return "/static/tpi-samples/" + rel.as_posix()
    except (ValueError, OSError):
        pass

    return None


def _input_to_dict(inp) -> dict:
    """Serialize a :class:`TpiInput` to a JSON-friendly dict (enum values as str).

    ``preview_url`` is a web-servable ``/static`` URL for a visual input whose
    stored file is a previewable image under a mounted static root (see
    :func:`_preview_url_for`); ``None`` for text inputs, non-image formats, or
    files not under a static root. ``text_excerpt`` is the mirror for TEXT inputs
    — a cleaned, truncated excerpt of the stored procedure file (see
    :func:`_text_excerpt_for`); ``None`` for visual inputs (which use
    ``preview_url`` instead), in-memory refs, or unreadable files.
    """
    return {
        "id": inp.id,
        "pcba_id": inp.pcba_id,
        "input_type": inp.input_type.value,
        "filename": inp.filename,
        "detected_format": inp.detected_format,
        "status": inp.status.value,
        "raw_ref": inp.raw_ref,
        "preview_url": _preview_url_for(inp),
        "text_excerpt": _text_excerpt_for(inp),
    }


def _section_to_dict(section: TpiSection) -> dict:
    """Serialize a :class:`TpiSection` (provenance + incomplete preserved)."""
    return {
        "key": section.key,
        "title": section.title,
        "content": section.content,
        "source_input_ids": list(section.source_input_ids),
        "incomplete": section.incomplete,
    }


def _draft_to_dict(draft) -> dict:
    """Serialize a :class:`DraftTpi` with its sections (provenance visible)."""
    return {
        "pcba_id": draft.pcba_id,
        "template_kind": draft.template_kind,
        "provider": draft.provider,
        "review_state": draft.review_state,
        "sections": [_section_to_dict(s) for s in draft.sections],
    }


def _body_to_section(body: TpiSectionBody) -> TpiSection:
    """Reconstruct a :class:`TpiSection` from a submitted :class:`TpiSectionBody`.

    Copies the provenance list defensively and coerces ``incomplete`` to a bool
    so the review service persists exactly what the reviewer submitted (Req 3.3,
    3.4).
    """
    return TpiSection(
        key=body.key,
        title=body.title,
        content=body.content,
        source_input_ids=[str(x) for x in body.source_input_ids],
        incomplete=bool(body.incomplete),
    )


# ── Ingestion + processing endpoints (task 8.1) ──────────────────────────────


@router.post("/tpi/pcbas/{pcba_id}/inputs")
async def ingest_pcba_inputs(pcba_id: str, request: IngestInputsRequest):
    """Ingest the four inputs for a PCBA (Req 1.1, 1.2, 1.3, 1.4).

    Accepts a JSON body describing the inputs (each referencing a
    ``sample_data/tpi`` fixture ``path``) and hands them to
    :func:`tpi_ingestion.ingest_pcba`, which persists exactly one ``tpi_inputs``
    row per submitted input — ``ingested`` on success or
    ``flagged_for_manual_annotation`` on a parse failure (Req 1.2), never dropping
    one. Returns the persisted inputs (as dicts) plus a summary of how many were
    ingested vs flagged, using the ``{data, total_count}`` envelope like the
    other list-bearing endpoints.
    """
    files = [
        UploadedFile(
            input_type=ref.input_type,
            filename=ref.filename,
            path=ref.path,
        )
        for ref in request.inputs
    ]
    inputs = await ingest_pcba(pcba_id, files)
    data = [_input_to_dict(i) for i in inputs]
    ingested = sum(1 for i in inputs if i.status == InputStatus.ingested)
    flagged = sum(
        1 for i in inputs if i.status == InputStatus.flagged_for_manual_annotation
    )
    return {
        "data": data,
        "total_count": len(data),
        "summary": {
            "pcba_id": pcba_id,
            "submitted": len(files),
            "ingested": ingested,
            "flagged_for_manual_annotation": flagged,
        },
    }


@router.post("/tpi/pcbas/{pcba_id}/inputs/upload")
async def upload_pcba_inputs(
    pcba_id: str,
    testing_procedure: UploadFile | None = File(None),
    operating_procedure: UploadFile | None = File(None),
    circuit_diagram: UploadFile | None = File(None),
    drawing: UploadFile | None = File(None),
):
    """Ingest a PCBA's four inputs from a REAL browser multipart file upload.

    This is the real upload intake path, contrasted with the sibling JSON
    endpoint ``POST /tpi/pcbas/{pcba_id}/inputs``: that one references
    ``sample_data/tpi`` fixtures already on disk (the demo-seeding path), whereas
    this one accepts the user's own files submitted from the browser as
    ``multipart/form-data``. It follows the established AVIP upload pattern
    (``routers/ai.py`` / ``routers/parts.py``): ``from fastapi import UploadFile,
    File`` and ``await file.read()``.

    Each of the four confirmed input types is an optional ``UploadFile`` form
    field named for its type (``testing_procedure`` / ``operating_procedure`` /
    ``circuit_diagram`` / ``drawing``). For each provided file the raw bytes are
    read and handed to :func:`tpi_ingestion.ingest_pcba` as an
    :class:`UploadedFile` carrying in-memory ``data`` (no disk write — ingestion
    reads bytes directly and detects the visual-input format from the leading
    bytes). The response mirrors the JSON endpoint exactly (the ``{data,
    total_count, summary}`` envelope) so both intake paths are interchangeable
    downstream.

    At least one file must be provided; a request with no files returns ``400``
    (there is nothing to ingest) rather than persisting an empty PCBA.
    """
    # Pair each provided UploadFile with its input type, skipping absent fields.
    provided = [
        (InputType.testing_procedure, testing_procedure),
        (InputType.operating_procedure, operating_procedure),
        (InputType.circuit_diagram, circuit_diagram),
        (InputType.drawing, drawing),
    ]
    files: list[UploadedFile] = []
    for input_type, upload in provided:
        if upload is None:
            continue
        data = await upload.read()
        files.append(
            UploadedFile(
                input_type=input_type,
                filename=upload.filename or input_type.value,
                data=data,
            )
        )

    if not files:
        return JSONResponse(
            status_code=400,
            content={
                "detail": (
                    "No files provided; upload at least one of "
                    "testing_procedure / operating_procedure / circuit_diagram / drawing."
                )
            },
        )

    inputs = await ingest_pcba(pcba_id, files)
    data = [_input_to_dict(i) for i in inputs]
    ingested = sum(1 for i in inputs if i.status == InputStatus.ingested)
    flagged = sum(
        1 for i in inputs if i.status == InputStatus.flagged_for_manual_annotation
    )
    return {
        "data": data,
        "total_count": len(data),
        "summary": {
            "pcba_id": pcba_id,
            "submitted": len(files),
            "ingested": ingested,
            "flagged_for_manual_annotation": flagged,
        },
    }


@router.post("/tpi/pcbas/{pcba_id}/process")
async def process_pcba_pipeline(
    pcba_id: str,
    provider: str | None = Query(
        default=None,
        description="mock | openai; overrides the configured default for this run",
    ),
):
    """Run extraction over the PCBA's inputs then map + generate a draft (Req 2.x, 3.1).

    Extraction must run before generation: for every ingested input
    (:func:`tpi_ingestion.get_inputs`) this calls
    :func:`tpi_extraction.extract_input` with a multimodal provider so text
    inputs go through text extraction and visual inputs through the LLM path
    (Property 3). It then calls :func:`tpi_generation.process_pcba`, which reads
    the extractions, maps them into TPI sections, and generates the draft
    (extract → map → generate). Returns the generated draft (sections with
    provenance + incomplete markers).

    Provider selection: the optional ``provider`` query param overrides the run's
    provider (``get_multimodal_provider_by_name(provider)``, ``mock`` | ``openai``);
    when omitted the configured default is used (``get_multimodal_provider(settings)``
    — the deterministic mock unless ``AVIP_TPI_LLM_PROVIDER`` selects otherwise,
    Req 8.1). The generated draft records the provider name so the response
    reflects which was used.

    Responds ``404`` when the PCBA has no ingested inputs (nothing to process) so
    the caller can distinguish "not ingested yet" from an empty draft. Responds
    ``400`` when ``provider=openai`` is selected but no ``OPENAI_API_KEY`` is
    configured — the OpenAI provider's lazy client raises ``RuntimeError`` on
    first use, which is caught here and returned as a clear ``400`` rather than
    surfacing as a ``500``.
    """
    inputs = await get_inputs(pcba_id)
    if not inputs:
        return JSONResponse(
            status_code=404,
            content={
                "detail": (
                    f"No ingested inputs for pcba_id={pcba_id!r}; "
                    "ingest inputs before processing."
                )
            },
        )

    # Pick the provider: an explicit per-request override wins, else the
    # configured default from settings (AVIP_TPI_LLM_PROVIDER).
    selected_provider = (
        get_multimodal_provider_by_name(provider)
        if provider is not None
        else get_multimodal_provider(settings)
    )

    try:
        # Fail fast on a misconfigured OpenAI provider. The extraction/generation
        # stages deliberately CATCH provider errors (flagging inputs / marking
        # sections incomplete, never fabricating content — Req 8.4), so a missing
        # OPENAI_API_KEY would otherwise silently yield a degraded draft instead
        # of a clear error. Building the client here (via the provider's lazy
        # _ensure_client) surfaces that misconfiguration as a RuntimeError up
        # front, which we map to a clean 400 below.
        ensure_client = getattr(selected_provider, "_ensure_client", None)
        if callable(ensure_client):
            ensure_client()

        # 1) Extraction — run over each ingested input with the selected provider.
        #    process_pcba (below) assumes extractions exist, so extract first.
        for inp in inputs:
            await extract_input(inp, selected_provider)

        # 2) Map + generate — process_pcba reads the extractions, maps them into
        #    TPI sections, and generates the draft (extract already done above).
        draft = await process_pcba(pcba_id, llm=selected_provider)
    except RuntimeError as exc:
        # The OpenAI provider's lazy _ensure_client raises RuntimeError when
        # OPENAI_API_KEY is missing (or the openai package is absent). Map that
        # misconfiguration to a clear 400 rather than a 500.
        logger.warning(
            "Provider error processing pcba_id=%s (provider=%s): %s",
            pcba_id,
            provider or getattr(selected_provider, "name", "?"),
            exc,
        )
        detail = str(exc)
        if "OPENAI_API_KEY" in detail or "openai" in detail.lower():
            detail = (
                "OpenAI provider selected but OPENAI_API_KEY is not configured. "
                "Set OPENAI_API_KEY (and restart the backend) or run with "
                "provider=mock."
            )
        return JSONResponse(status_code=400, content={"detail": detail})

    return _draft_to_dict(draft)


# ── Read endpoints (task 8.2) ────────────────────────────────────────────────
#
# List endpoints use the {data, total_count} envelope like source_comparison.


@router.get("/tpi/pcbas")
async def list_pcbas():
    """List PCBAs with their pipeline status + draft review state (Req 6.9, 10.2).

    Reads ``tpi_pcbas`` (one row per sample PCBA) and left-joins the draft's
    ``review_state`` so the monitor UI can show each PCBA's pipeline status badge
    at a glance. Returns the ``{data, total_count}`` envelope, most recently
    created first.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT p.pcba_id AS pcba_id,
                  p.status AS status,
                  p.created_at AS created_at,
                  d.review_state AS review_state,
                  d.template_kind AS template_kind
             FROM tpi_pcbas p
             LEFT JOIN tpi_drafts d ON d.pcba_id = p.pcba_id
            ORDER BY p.created_at DESC, p.pcba_id ASC"""
    )
    rows = await cursor.fetchall()
    data = [
        {
            "pcba_id": row["pcba_id"],
            "status": row["status"],
            "created_at": row["created_at"],
            "review_state": row["review_state"],
            "template_kind": row["template_kind"],
        }
        for row in rows
    ]
    return {"data": data, "total_count": len(data)}


@router.get("/tpi/pcbas/{pcba_id}")
async def get_pcba_detail(pcba_id: str):
    """Return a PCBA's detail: the PCBA row, its inputs, and its draft (Req 1.4, 2.4, 6.5).

    Reads the ``tpi_pcbas`` row (``404`` if the PCBA was never ingested), its
    inputs via :func:`tpi_ingestion.get_inputs` (each carrying ``status`` and
    ``detected_format`` so the review UI can surface per-input state), and its
    draft via :func:`tpi_generation.get_draft` (``None`` when not yet generated).
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT pcba_id, status, created_at FROM tpi_pcbas WHERE pcba_id = ?",
        (pcba_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"PCBA not found: {pcba_id}"},
        )

    inputs = await get_inputs(pcba_id)
    draft = await get_draft(pcba_id)
    return {
        "pcba_id": row["pcba_id"],
        "status": row["status"],
        "created_at": row["created_at"],
        "inputs": [_input_to_dict(i) for i in inputs],
        "draft": _draft_to_dict(draft) if draft is not None else None,
    }


@router.get("/tpi/drafts")
async def list_drafts(
    status: str | None = Query(
        default=None,
        description="Filter by review_state (drafted | in_review | finalized)",
    ),
):
    """List drafts for the review queue, optionally filtered by state (Req 4.1).

    Delegates to :func:`tpi_review.list_drafts` (which hydrates each draft with
    its sections, provenance, and incomplete flags). When ``status`` is omitted
    every draft is returned; supplying ``drafted`` / ``in_review`` / ``finalized``
    filters by ``tpi_drafts.review_state``. Returns the ``{data, total_count}``
    envelope.
    """
    drafts = await tpi_review.list_drafts(status=status)
    data = [_draft_to_dict(d) for d in drafts]
    return {"data": data, "total_count": len(data)}


@router.get("/tpi/drafts/{pcba_id}")
async def get_draft_detail(pcba_id: str):
    """Return a single draft with section-by-section provenance (Req 3.3, 6.5).

    Delegates to :func:`tpi_generation.get_draft`; responds ``404`` when there is
    no draft for the PCBA so the workbench can render a clear not-found state.
    Each section carries its ``source_input_ids`` provenance and ``incomplete``
    marker.
    """
    draft = await get_draft(pcba_id)
    if draft is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Draft not found: {pcba_id}"},
        )
    return _draft_to_dict(draft)


@router.get("/tpi/final")
async def list_final():
    """List ONLY finalized TPIs (Req 4.2, 5.x; Property 5).

    Delegates to :func:`tpi_review.list_final`, which filters to
    ``review_state = 'finalized'`` so unreviewed drafts never appear in the final
    set. Returns the ``{data, total_count}`` envelope.
    """
    drafts = await tpi_review.list_final()
    data = [_draft_to_dict(d) for d in drafts]
    return {"data": data, "total_count": len(data)}


@router.get("/tpi/audit/{pcba_id}")
async def get_audit_trail(pcba_id: str):
    """Return a PCBA's review audit trail, oldest first (Req 4.4).

    Delegates to :func:`tpi_review.get_audit`. Returns the ``{data, total_count}``
    envelope; a PCBA with no audit rows yields an empty ``data`` list (not a 404)
    since the absence of audit history is a valid state.
    """
    audit = await tpi_review.get_audit(pcba_id)
    return {"data": audit, "total_count": len(audit)}


# ── Finalize + export + status endpoints (task 8.3) ──────────────────────────


@router.post("/tpi/drafts/{pcba_id}/finalize")
async def finalize_draft(pcba_id: str, request: FinalizeRequest):
    """Record a reviewer's corrections as the final TPI + write an audit row (Req 4.3, 4.4).

    Reconstructs the submitted ``corrected_sections`` into :class:`TpiSection`
    objects (provenance + incomplete preserved), builds a
    :class:`tpi_review.TpiReviewDecision`, and calls :func:`tpi_review.finalize`,
    which records the corrected sections as the final TPI, advances the draft to
    ``finalized``, and writes exactly one audit row. Returns the finalized draft.

    Error mapping (finalize raises ``ValueError`` when no draft exists):
      * no draft for the PCBA → ``404`` naming the id (nothing to finalize).
    """
    decision = tpi_review.TpiReviewDecision(
        pcba_id=pcba_id,
        reviewer=request.reviewer,
        corrected_sections=[_body_to_section(s) for s in request.corrected_sections],
        note=request.note,
    )
    try:
        finalized = await tpi_review.finalize(decision)
    except ValueError as exc:
        # finalize raises ValueError only when there is no draft to finalize —
        # that is a missing-resource condition, so map it to 404 (a malformed
        # request would have been caught by body validation → 422).
        logger.warning("Finalize failed for pcba_id=%s: %s", pcba_id, exc)
        return JSONResponse(
            status_code=404,
            content={"detail": str(exc)},
        )
    return _draft_to_dict(finalized)


@router.get("/tpi/final/{pcba_id}/export")
async def export_final_tpi(pcba_id: str):
    """Export a finalized TPI as a downloadable PDF document (Req 5.1).

    Reads the draft via :func:`tpi_generation.get_draft` (``404`` when there is
    no draft for the PCBA). Only a ``finalized`` draft is exportable — a draft
    still in ``drafted`` / ``in_review`` yields ``400`` so an unreviewed AI draft
    is never handed out as a finished TPI (Req 4.1, 4.2). When finalized, renders
    the document via :func:`tpi_document.render_tpi_document` and returns the PDF
    bytes as a ``Response`` with ``media_type='application/pdf'`` and a
    ``Content-Disposition: attachment`` header naming the file ``TPI-{pcba_id}.pdf``.
    """
    draft = await get_draft(pcba_id)
    if draft is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Draft not found: {pcba_id}"},
        )
    if draft.review_state != "finalized":
        return JSONResponse(
            status_code=400,
            content={
                "detail": (
                    f"TPI for pcba_id={pcba_id!r} is not finalized "
                    f"(review_state={draft.review_state!r}); finalize it before export."
                )
            },
        )

    pdf_bytes = render_tpi_document(draft)
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f"attachment; filename=TPI-{pcba_id}.pdf",
        },
    )


# The unresolved [CONFIRM] open items carried into implementation (design: "Open
# Items Carried Into Implementation" / requirements: "Open Items"). Surfaced on
# /tpi/status so the UI can render a banner naming each open item rather than
# hiding a default (Req 6.9, error handling / [CONFIRM] handling).
_CONFIRM_ITEMS: tuple[dict, ...] = (
    {
        "key": "visual_input_format",
        "label": "Visual-input file format",
        "detail": (
            "The file format of circuit diagrams and drawings (CAD export, PDF, "
            "or image) is not yet confirmed; ingestion detects and reports the "
            "format rather than assuming one."
        ),
    },
    {
        "key": "client_tpi_template",
        "label": "Client TPI template availability",
        "detail": (
            "The client's own TPI template is not yet available; generation uses "
            "the documented placeholder structure until it is provided."
        ),
    },
    {
        "key": "human_authored_tpi",
        "label": "Human-authored TPI availability",
        "detail": (
            "An existing human-authored TPI for a sample PCBA is not yet "
            "available; the side-by-side comparison is conditional on it."
        ),
    },
    {
        "key": "catalog_size",
        "label": "Full PCBA catalog size",
        "detail": (
            "The size of the full PCBA catalog is not yet confirmed; this release "
            "operates over the small sample set."
        ),
    },
)


@router.get("/tpi/status")
async def get_status():
    """Return pipeline/config status + the ``[CONFIRM]`` banner data (Req 6.9).

    Surfaces, as a simple JSON dict for the UI:

      * ``pcba_status_counts`` — a count of PCBAs by their ``tpi_pcbas.status``
        (ingesting / drafted / in_review / finalized) so the monitor shows
        pipeline progress at a glance.
      * ``total_pcbas`` — the total number of PCBAs.
      * ``llm_provider`` — the active multimodal provider's ``name`` (the
        deterministic ``mock`` by default, Req 8.1), so the UI can show which
        provider produced drafts.
      * ``confirm_items`` — the list of unresolved ``[CONFIRM]`` open items
        (visual-input format, client TPI template, human-authored TPI, catalog
        size) so the UI surfaces each open item rather than a hidden default.

    Consistent with the source-comparison report header, this is a plain status
    payload (not the ``{data, total_count}`` list envelope).
    """
    db = await get_db()
    cursor = await db.execute("SELECT status, COUNT(*) AS n FROM tpi_pcbas GROUP BY status")
    rows = await cursor.fetchall()
    status_counts = {row["status"]: row["n"] for row in rows}
    total = sum(status_counts.values())

    provider = get_multimodal_provider(settings)
    provider_name = getattr(provider, "name", "unknown")

    return {
        "pcba_status_counts": status_counts,
        "total_pcbas": total,
        "llm_provider": provider_name,
        "confirm_items": [dict(item) for item in _CONFIRM_ITEMS],
    }
