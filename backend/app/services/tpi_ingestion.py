"""Ingestion service for the PCBA TPI Generation feature.

Loads the four inputs for a PCBA (testing procedure, operating procedure,
circuit diagram, drawing) and persists each as a source-input row in
``tpi_inputs`` with a per-input status (Req 1.1, 1.4). A parse failure flags
that input ``flagged_for_manual_annotation`` and the run continues — an input is
never silently skipped and a single failure never fails the whole PCBA
(Req 1.2). For visual inputs, the detected file format is recorded on the row;
the visual-input format is a ``[CONFIRM]`` item, so ingestion attempts
extraction and reports the detected format rather than assuming one (Req 1.3).

Contract: every submitted input yields exactly one persisted ``TpiInput`` row;
none is dropped; failures are represented as status, not exceptions.

Task 1 provides this module docstring only; ``ingest_pcba`` and format detection
are implemented in task 3.
"""
import logging
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path

from app.config import settings
from app.db.database import get_db

logger = logging.getLogger("app.tpi.ingestion")


# ── Input type / status enums ────────────────────────────────────────────────
#
# A parallel task (2.1) may introduce ``app/services/tpi_types.py`` with the
# canonical ``InputType`` / ``InputStatus`` enums. To avoid a duplicate-source
# clash we prefer that module when it exists and only define the enums locally
# as a fallback. Either way the enum VALUES are identical to the design so both
# definitions agree (a persisted "circuit_diagram" / "ingested" string round-
# trips regardless of which definition produced it).
try:  # pragma: no cover - exercised by whichever module wins the race
    from app.services.tpi_types import InputStatus, InputType
except ImportError:
    from enum import Enum

    class InputType(str, Enum):
        """The four confirmed source documents per PCBA (FR2-1)."""

        testing_procedure = "testing_procedure"
        operating_procedure = "operating_procedure"
        circuit_diagram = "circuit_diagram"
        drawing = "drawing"

    class InputStatus(str, Enum):
        """Per-input ingestion status surfaced by the review UI (Req 1.4)."""

        ingested = "ingested"
        flagged_for_manual_annotation = "flagged_for_manual_annotation"


# ── Input models ─────────────────────────────────────────────────────────────


@dataclass
class TpiInput:
    """A persisted source-input row (mirrors ``tpi_inputs``, design Data Models).

    ``detected_format`` is populated for visual inputs by :func:`detect_format`
    (Req 1.3) and left ``None`` for text inputs; detection reports the format
    rather than assuming one and never blocks ingestion.
    """

    id: str
    pcba_id: str
    input_type: InputType
    filename: str
    detected_format: str | None
    status: InputStatus
    raw_ref: str


@dataclass
class UploadedFile:
    """A single submitted input for a PCBA.

    Kept deliberately simple and consistent with how other services accept
    inputs: an ``input_type`` (which of the four confirmed types this is), a
    ``filename``, and the content either as an on-disk ``path`` or in-memory
    ``data`` bytes. ``raw_ref`` is stored as the path when present, otherwise a
    generated in-memory reference.
    """

    input_type: InputType
    filename: str
    path: str | None = None
    data: bytes | None = None


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _coerce_input_type(value: object) -> InputType:
    """Coerce a submitted input-type (enum or str) into an ``InputType``.

    Raises ``ValueError`` for an unrecognized type so a malformed submission is
    surfaced rather than silently coerced.
    """
    if isinstance(value, InputType):
        return value
    return InputType(str(value))


def _uploads_dir() -> Path:
    """Directory where uploaded (in-memory) inputs are spilled to disk.

    Uploaded files arrive as raw bytes (the real browser multipart path) with no
    on-disk path. Downstream stages — text extraction (``open(raw_ref)``) and
    visual extraction (``Path(image_ref).read_bytes()``) — read the input from
    its ``raw_ref`` as a file path, so the bytes are persisted here and the
    stored file path becomes the ``raw_ref``. Lives under the app data dir
    alongside the SQLite DB so uploads survive for the whole pipeline run.
    """
    return settings.data_dir / "tpi_uploads"


def _read_input(inp: UploadedFile) -> tuple[str, str]:
    """Attempt to read/parse a submitted input.

    Returns ``(raw_ref, _content_preview)`` on success. Raises on any failure so
    the caller can flag the input for manual annotation and continue.

    Two intake shapes are supported. A fixture ``path`` is touched (an
    unreadable/missing path fails here and is flagged) and used directly as the
    ``raw_ref``. Uploaded ``data`` bytes (the real browser multipart path) have
    no on-disk path, so they are spilled to a per-input file under
    :func:`_uploads_dir` and that stored file path becomes the ``raw_ref`` —
    which is what the extraction stage reads from. This keeps both intake paths
    identical downstream.
    """
    if inp.path is not None:
        # Touch the file so an unreadable/missing path fails here and is flagged.
        with open(inp.path, "rb") as fh:
            content = fh.read()
        return inp.path, content[:64].decode("utf-8", errors="replace")
    if inp.data is not None:
        # Spill the uploaded bytes to disk so raw_ref is a real, readable path
        # the extraction stage can open (it reads inputs from raw_ref).
        uploads = _uploads_dir()
        uploads.mkdir(parents=True, exist_ok=True)
        safe_name = Path(inp.filename or "upload").name or "upload"
        stored = uploads / f"{uuid.uuid4().hex}_{safe_name}"
        stored.write_bytes(inp.data)
        return str(stored), inp.data[:64].decode("utf-8", errors="replace")
    # Neither a path nor bytes: nothing to ingest — treat as a parse failure.
    raise ValueError("input has neither a path nor data")


# ── Visual-input format detection (Req 1.3, task 3.2) ────────────────────────
#
# The circuit-diagram / drawing file format is a ``[CONFIRM]`` open item (CAD
# export, PDF, or image). Per Req 1.3 the system MUST *attempt* extraction and
# *report* the detected format rather than assuming one. Detection is therefore
# honest and non-committal: sniff the actual leading bytes where possible
# (magic numbers), fall back to the filename extension, and only ever return
# "unknown" — never raise, never invent a format. It is dependency-free and
# reads only the leading bytes already reachable via the input's path/data.

# Visual input types whose ``detected_format`` we record (text inputs stay None).
_VISUAL_TYPES = frozenset({InputType.circuit_diagram, InputType.drawing})


def _leading_bytes(inp: "UploadedFile", n: int = 16) -> bytes | None:
    """Read up to ``n`` leading bytes from the input's data or path.

    Returns ``None`` if the bytes can't be read for any reason — detection then
    falls back to the filename extension. Never raises.
    """
    if inp.data is not None:
        return bytes(inp.data[:n])
    if inp.path is not None:
        try:
            with open(inp.path, "rb") as fh:
                return fh.read(n)
        except OSError:
            return None
    return None


def _sniff_magic(head: bytes) -> str | None:
    """Identify a format from magic bytes, or ``None`` if unrecognized.

    Covers the plausible visual-input formats named in the ``[CONFIRM]`` item —
    common images and PDF — plus a couple of text-based vector/CAD hints (SVG,
    DXF). Anything else returns ``None`` so the caller falls back to extension.
    """
    if head.startswith(b"\x89PNG\r\n\x1a\n") or head.startswith(b"\x89PNG"):
        return "png"
    if head.startswith(b"\xff\xd8\xff") or head.startswith(b"\xff\xd8"):
        return "jpeg"
    if head.startswith(b"%PDF"):
        return "pdf"
    if head.startswith(b"GIF87a") or head.startswith(b"GIF89a"):
        return "gif"
    if head.startswith(b"BM"):
        return "bmp"
    if head[:4] == b"II*\x00" or head[:4] == b"MM\x00*":
        return "tiff"
    # Text-based vector / CAD hints (best-effort content sniff, dependency-free).
    try:
        text_head = head.decode("utf-8", errors="ignore").lstrip().lower()
    except Exception:  # noqa: BLE001 - decoding never fails with errors="ignore"
        text_head = ""
    if text_head.startswith("<svg") or (text_head.startswith("<?xml") and "svg" in text_head):
        return "svg"
    # DXF ASCII files conventionally begin with a "0\nSECTION" group; the leading
    # token is enough of a hint without pulling in a CAD parser.
    if text_head.startswith("0") and "section" in text_head:
        return "dxf"
    return None


def _extension(filename: str) -> str | None:
    """Lowercased file extension without the dot, or ``None`` if there is none."""
    if not filename or "." not in filename:
        return None
    ext = filename.rsplit(".", 1)[-1].strip().lower()
    return ext or None


def detect_format(inp: "UploadedFile") -> str | None:
    """Detect and *report* a visual input's file format (Req 1.3).

    Strategy, in order of confidence:
      1. Magic-number sniff of the leading bytes (PNG, JPEG, PDF, GIF, BMP,
         TIFF, and best-effort SVG/DXF) — trusts the actual content.
      2. Filename extension fallback (e.g. ``.dxf`` / ``.dwg`` / ``.svg`` and the
         current ``.txt`` stand-ins) when the bytes aren't conclusive.
      3. ``"unknown"`` when nothing is conclusive.

    The ``[CONFIRM]`` visual-input format is *not* assumed or required: a ``.txt``
    stand-in honestly reports ``"txt"`` rather than being coerced into a CAD/PDF
    format. Never raises — detection failure yields ``"unknown"``, so it can
    never fail the PCBA or change the status logic.
    """
    head = _leading_bytes(inp)
    if head:
        sniffed = _sniff_magic(head)
        if sniffed is not None:
            return sniffed
    ext = _extension(getattr(inp, "filename", "") or "")
    if ext is not None:
        return ext
    return "unknown"


async def _upsert_pcba(pcba_id: str, status: str = "ingesting") -> None:
    """Upsert the ``tpi_pcbas`` row for a PCBA (Req 1.1).

    ``pcba_id`` is UNIQUE; re-ingesting the same PCBA keeps the existing row's
    id and refreshes its status, so ingestion is idempotent at the PCBA level.
    """
    db = await get_db()
    await db.execute(
        """INSERT INTO tpi_pcbas (id, pcba_id, status, created_at)
           VALUES (?, ?, ?, ?)
           ON CONFLICT(pcba_id) DO UPDATE SET status = excluded.status""",
        (str(uuid.uuid4()), pcba_id, status, _now_iso()),
    )
    await db.commit()


async def _persist_input(
    pcba_id: str,
    input_type: InputType,
    filename: str,
    status: InputStatus,
    raw_ref: str,
    detected_format: str | None = None,
) -> TpiInput:
    """Persist one ``tpi_inputs`` row and return the ``TpiInput`` (Req 1.4).

    ``detected_format`` is supplied by the caller: ``ingest_pcba`` fills it for
    visual inputs via :func:`detect_format` (Req 1.3) and leaves it ``None`` for
    text inputs. A new uuid id is assigned so every submitted input is its own
    row (Property 1 foundation).
    """
    input_id = str(uuid.uuid4())
    db = await get_db()
    await db.execute(
        """INSERT INTO tpi_inputs
               (id, pcba_id, input_type, filename, detected_format, status, raw_ref)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            input_id,
            pcba_id,
            input_type.value,
            filename,
            detected_format,
            status.value,
            raw_ref,
        ),
    )
    await db.commit()
    return TpiInput(
        id=input_id,
        pcba_id=pcba_id,
        input_type=input_type,
        filename=filename,
        detected_format=detected_format,
        status=status,
        raw_ref=raw_ref,
    )


def _row_to_input(row) -> TpiInput:
    """Build a :class:`TpiInput` from a ``tpi_inputs`` aiosqlite Row."""
    return TpiInput(
        id=row["id"],
        pcba_id=row["pcba_id"],
        input_type=InputType(row["input_type"]),
        filename=row["filename"],
        detected_format=row["detected_format"],
        status=InputStatus(row["status"]),
        raw_ref=row["raw_ref"],
    )


async def ingest_pcba(pcba_id: str, files: list) -> list[TpiInput]:
    """Persist every submitted input for a PCBA with a per-input status.

    Upserts the ``tpi_pcbas`` row (status ``ingesting``), then for each submitted
    input attempts to read/parse it and persists exactly one ``tpi_inputs`` row:
    ``ingested`` on success, ``flagged_for_manual_annotation`` on a parse failure
    (Req 1.2). A single failure never fails the whole PCBA and no input is ever
    dropped — every submitted input yields exactly one persisted row (Req 1.1,
    1.4; Property 1 foundation).

    ``files`` is a list of :class:`UploadedFile` (or objects/dicts carrying
    ``input_type`` + ``filename`` + ``path``/``data``). ``raw_ref`` is stored as
    the file path when present, else a generated in-memory reference. For visual
    inputs (circuit_diagram / drawing) ``detected_format`` records the format
    reported by :func:`detect_format` (Req 1.3); text inputs keep it ``None``.
    """
    await _upsert_pcba(pcba_id, status="ingesting")

    persisted: list[TpiInput] = []
    for raw in files:
        inp = _normalize_file(raw)
        # Coerce the input type up front; an unrecognized type is a parse
        # failure that still persists a flagged row rather than dropping it.
        try:
            input_type = _coerce_input_type(inp.input_type)
        except (ValueError, TypeError) as exc:
            logger.warning(
                "Unrecognized input_type for pcba_id=%s filename=%s: %s; "
                "flagging for manual annotation",
                pcba_id,
                getattr(inp, "filename", "?"),
                exc,
            )
            row = await _persist_input(
                pcba_id=pcba_id,
                input_type=_fallback_type(inp),
                filename=getattr(inp, "filename", "unknown"),
                status=InputStatus.flagged_for_manual_annotation,
                raw_ref=str(getattr(inp, "path", None) or f"inmem://{getattr(inp, 'filename', 'unknown')}"),
            )
            persisted.append(row)
            continue

        try:
            raw_ref, _preview = _read_input(inp)
        except Exception as exc:  # noqa: BLE001 - any read/parse failure flags, never fails the PCBA
            raw_ref = inp.path or f"inmem://{inp.filename}"
            logger.warning(
                "Failed to parse input pcba_id=%s type=%s filename=%s: %s; "
                "flagging for manual annotation",
                pcba_id,
                input_type.value,
                inp.filename,
                exc,
            )
            row = await _persist_input(
                pcba_id=pcba_id,
                input_type=input_type,
                filename=inp.filename,
                status=InputStatus.flagged_for_manual_annotation,
                raw_ref=raw_ref,
            )
            persisted.append(row)
            continue

        # For visual inputs (circuit_diagram / drawing) detect and RECORD the
        # file format (Req 1.3). The format is a [CONFIRM] item, so we report
        # what we detect rather than assuming one; detection never raises and an
        # inconclusive result is "unknown", so it can't change the status logic
        # or fail the PCBA. Text inputs keep detected_format = None (task 3.2
        # scope is visual inputs only).
        detected_format: str | None = None
        if input_type in _VISUAL_TYPES:
            detected_format = detect_format(inp)

        row = await _persist_input(
            pcba_id=pcba_id,
            input_type=input_type,
            filename=inp.filename,
            status=InputStatus.ingested,
            raw_ref=raw_ref,
            detected_format=detected_format,
        )
        persisted.append(row)
        logger.info(
            "Ingested input id=%s pcba_id=%s type=%s filename=%s detected_format=%s",
            row.id,
            pcba_id,
            input_type.value,
            inp.filename,
            detected_format,
        )

    logger.info(
        "Ingestion complete for pcba_id=%s: %d input(s) persisted (%d ingested, %d flagged)",
        pcba_id,
        len(persisted),
        sum(1 for r in persisted if r.status == InputStatus.ingested),
        sum(
            1
            for r in persisted
            if r.status == InputStatus.flagged_for_manual_annotation
        ),
    )
    return persisted


def _fallback_type(inp: object) -> InputType:
    """Best-effort input type for a submission whose type couldn't be coerced.

    Used only to keep a flagged row well-formed; defaults to ``drawing`` (a
    visual input) since an unknown submission most resembles an unparseable
    binary. The row is flagged regardless, so this only affects the stored tag.
    """
    return InputType.drawing


def _normalize_file(raw: object) -> UploadedFile:
    """Normalize a submitted input into an :class:`UploadedFile`.

    Accepts an :class:`UploadedFile` directly, a mapping with
    ``input_type`` / ``filename`` / ``path`` / ``data`` keys, or an arbitrary
    object exposing those attributes — so callers (router, tests) can pass the
    simplest thing that fits.
    """
    if isinstance(raw, UploadedFile):
        return raw
    if isinstance(raw, dict):
        return UploadedFile(
            input_type=raw.get("input_type"),
            filename=raw.get("filename", "unknown"),
            path=raw.get("path"),
            data=raw.get("data"),
        )
    return UploadedFile(
        input_type=getattr(raw, "input_type", None),
        filename=getattr(raw, "filename", "unknown"),
        path=getattr(raw, "path", None),
        data=getattr(raw, "data", None),
    )


async def get_inputs(pcba_id: str) -> list[TpiInput]:
    """Read back all persisted inputs for a PCBA (for later tasks/tests).

    Ordered by ``rowid`` so the read reflects insertion order. Lets task 3.2,
    the extraction stage, and tests verify persistence (Property 1).
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, pcba_id, input_type, filename, detected_format, status, raw_ref
             FROM tpi_inputs
            WHERE pcba_id = ?
            ORDER BY rowid ASC""",
        (pcba_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_input(r) for r in rows]
