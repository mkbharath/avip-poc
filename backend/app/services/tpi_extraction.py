"""Extraction services for the PCBA TPI Generation feature.

Turns each ingested input into structured content the mapping stage can consume.
Text procedures (testing / operating) go through :func:`extract_text` (Req 2.1);
visual inputs (circuit diagrams / drawings) go through :func:`extract_visual`,
which uses the pluggable multimodal LLM provider to produce a structured
description (Req 2.2, 2.3). The LLM path is used **only** for visual inputs —
:func:`extract_input` dispatches on ``input_type`` so a text procedure never
touches the provider (Property 3).

On provider error, :func:`extract_visual` returns an ``Extraction`` with status
``flagged_for_manual_annotation`` and **no fabricated content** — the failure is
surfaced cleanly rather than swallowed into invented output (Req 2.4, 8.4;
Property 2). Every extraction persists exactly one ``tpi_extractions`` row.

Conventions mirror the source-comparison services (``sc_review.py`` /
``ingestion.py``): ``get_db()`` singleton connection, ``uuid4`` string ids,
JSON-in-TEXT ``content_json``, and ISO-8601 timestamps where needed.
"""

from __future__ import annotations

import json
import logging
import re
import uuid
from dataclasses import dataclass

from app.db.database import get_db
from app.services.tpi_ingestion import TpiInput, _VISUAL_TYPES
from app.services.tpi_llm_provider import MultimodalLLMProvider
from app.services.tpi_types import InputStatus, InputType

logger = logging.getLogger("app.tpi.extraction")


# ── Extraction model ─────────────────────────────────────────────────────────


@dataclass
class Extraction:
    """A persisted extraction row (mirrors ``tpi_extractions``, design Data Models).

    ``content`` is the structured extracted content (persisted as JSON-in-TEXT in
    ``content_json``). ``status`` reflects success (``ingested``) or a
    manual-annotation flag (``flagged_for_manual_annotation``) — the latter is
    used when a provider errors, and in that case ``content`` carries **no
    fabricated extracted content**, only a note recording the failure reason
    (Req 2.4, 8.4). ``provider`` records who produced it: ``"text"`` for text
    extraction (which never calls the LLM) or the provider's ``name`` (e.g.
    ``"mock"`` / ``"openai"``) for visual extraction.
    """

    input_id: str
    input_type: InputType
    content: dict
    status: InputStatus
    provider: str


# Text extraction does not use the multimodal LLM, so its provider tag is a
# literal marker rather than an LLM provider name (Property 3 / Req 2.1).
_TEXT_PROVIDER = "text"


# Matches HTML comments, including multi-line ones. The sample fixtures carry a
# ``<!-- FIXTURE PENDING REAL CLIENT SAMPLES ... -->`` header; stripping it here
# keeps the disclaimer out of the structured extraction (and thus the mapped /
# drafted TPI body) while leaving the real procedure text intact. Dependency-free.
_HTML_COMMENT_RE = re.compile(r"<!--.*?-->", re.DOTALL)


def _strip_html_comments(text: str) -> str:
    """Remove HTML comments (multi-line included) from procedure text and trim."""
    return _HTML_COMMENT_RE.sub("", text).strip()


# ── Persistence helper ───────────────────────────────────────────────────────


async def _persist_extraction(
    input_id: str,
    input_type: InputType,
    content: dict,
    status: InputStatus,
    provider: str,
) -> Extraction:
    """Persist one ``tpi_extractions`` row and return the :class:`Extraction`.

    ``content`` is serialized to JSON-in-TEXT ``content_json`` (matching the
    JSON-in-TEXT convention used across the AVIP services). A new uuid id is
    assigned per extraction row.
    """
    extraction_id = str(uuid.uuid4())
    db = await get_db()
    await db.execute(
        """INSERT INTO tpi_extractions (id, input_id, content_json, status, provider)
           VALUES (?, ?, ?, ?, ?)""",
        (
            extraction_id,
            input_id,
            json.dumps(content),
            status.value,
            provider,
        ),
    )
    await db.commit()
    return Extraction(
        input_id=input_id,
        input_type=input_type,
        content=content,
        status=status,
        provider=provider,
    )


# ── Text extraction (Req 2.1) ────────────────────────────────────────────────


def _split_sections(raw_text: str) -> tuple[str | None, list[dict]]:
    """Split procedure text into a title + heading-delimited sections.

    Simple, dependency-free structuring: Markdown-style headings (lines starting
    with ``#``) open a new section; a top-level ``# `` heading (or the first
    heading seen) becomes the document title. Non-heading lines accumulate into
    the current section's body, split on blank lines into paragraphs. Text
    before the first heading is kept as a ``preamble`` section so nothing is
    dropped. Returns ``(title, sections)`` where each section is
    ``{"heading": str, "body": str}``.
    """
    title: str | None = None
    sections: list[dict] = []
    current_heading = "preamble"
    current_lines: list[str] = []

    def _flush() -> None:
        body = "\n".join(current_lines).strip()
        if body or current_heading != "preamble":
            sections.append({"heading": current_heading, "body": body})

    for line in raw_text.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            heading_text = stripped.lstrip("#").strip()
            # The first H1 (single '#') — or the first heading of any level if
            # no H1 appears — names the document.
            is_h1 = stripped.startswith("# ") or stripped == "#"
            if title is None and (is_h1 or not sections):
                title = heading_text
            _flush()
            current_heading = heading_text or "section"
            current_lines = []
        else:
            current_lines.append(line)
    _flush()

    return title, sections


async def extract_text(inp: TpiInput) -> Extraction:
    """Structured text extraction for testing / operating procedures (Req 2.1).

    Reads the procedure text from ``inp.raw_ref`` (the stored file path) and
    produces a simple structured extraction — a title, heading-delimited
    sections, and the full ``raw_text`` for provenance. Text extraction does not
    use the multimodal LLM (Property 3), so the persisted ``provider`` is the
    literal ``"text"`` marker.

    On a read failure the input is flagged for manual annotation with no
    fabricated content (mirroring the provider-failure contract), rather than
    crashing the pipeline.
    """
    try:
        with open(inp.raw_ref, "r", encoding="utf-8", errors="replace") as fh:
            raw_text = fh.read()
    except OSError as exc:
        logger.warning(
            "Text extraction could not read input id=%s raw_ref=%s: %s; "
            "flagging for manual annotation",
            inp.id,
            inp.raw_ref,
            exc,
        )
        return await _persist_extraction(
            input_id=inp.id,
            input_type=inp.input_type,
            content={
                "error": "text_read_failed",
                "reason": str(exc),
                "raw_ref": inp.raw_ref,
            },
            status=InputStatus.flagged_for_manual_annotation,
            provider=_TEXT_PROVIDER,
        )

    # Strip HTML comments (e.g. the fixture disclaimer header) before
    # structuring so the disclaimer never flows into the mapped / drafted TPI
    # body. Real procedure text and its newlines are preserved.
    raw_text = _strip_html_comments(raw_text)

    title, sections = _split_sections(raw_text)
    content = {
        "input_type": inp.input_type.value,
        "title": title or inp.filename,
        "sections": sections,
        "raw_text": raw_text,
    }
    logger.info(
        "Text extraction complete input id=%s type=%s sections=%d",
        inp.id,
        inp.input_type.value,
        len(sections),
    )
    return await _persist_extraction(
        input_id=inp.id,
        input_type=inp.input_type,
        content=content,
        status=InputStatus.ingested,
        provider=_TEXT_PROVIDER,
    )


# ── Visual extraction via the multimodal LLM (Req 2.2, 2.3, 2.4) ─────────────


async def extract_visual(inp: TpiInput, llm: MultimodalLLMProvider) -> Extraction:
    """Multimodal-LLM description of a circuit diagram / drawing (Req 2.2, 2.3).

    Calls ``llm.describe_visual(inp.raw_ref, inp.input_type)`` to obtain the
    structured description and persists it (status ``ingested``, provider =
    ``llm.name``). The multimodal path is used **only** for visual inputs
    (Property 3) — the dispatcher :func:`extract_input` guarantees this.

    On any provider error (``describe_visual`` raises — auth, transport,
    malformed reply, unreadable image) the failure is surfaced cleanly: the
    input is persisted with status ``flagged_for_manual_annotation`` and **no
    fabricated content** (only a note recording the failure reason), a warning
    is logged, and the flagged :class:`Extraction` is returned. The provider
    error never propagates out of this function and never crashes the pipeline
    (Req 2.4, 8.4; Property 2).
    """
    provider_name = getattr(llm, "name", "unknown")
    try:
        description = await llm.describe_visual(inp.raw_ref, inp.input_type)
    except Exception as exc:  # noqa: BLE001 - any provider error flags, never fabricates
        logger.warning(
            "Visual extraction provider error input id=%s type=%s provider=%s: %s; "
            "flagging for manual annotation (no fabricated content)",
            inp.id,
            inp.input_type.value,
            provider_name,
            exc,
        )
        return await _persist_extraction(
            input_id=inp.id,
            input_type=inp.input_type,
            # No fabricated description — only the failure reason (Req 2.4, 8.4).
            content={
                "error": "provider_error",
                "reason": str(exc),
                "raw_ref": inp.raw_ref,
            },
            status=InputStatus.flagged_for_manual_annotation,
            provider=provider_name,
        )

    # Defensive: a provider that returns a non-dict is treated as a failure
    # rather than persisting malformed content.
    if not isinstance(description, dict):
        logger.warning(
            "Visual extraction provider returned non-dict input id=%s provider=%s; "
            "flagging for manual annotation",
            inp.id,
            provider_name,
        )
        return await _persist_extraction(
            input_id=inp.id,
            input_type=inp.input_type,
            content={
                "error": "provider_bad_output",
                "reason": f"expected dict, got {type(description).__name__}",
                "raw_ref": inp.raw_ref,
            },
            status=InputStatus.flagged_for_manual_annotation,
            provider=provider_name,
        )

    logger.info(
        "Visual extraction complete input id=%s type=%s provider=%s keys=%d",
        inp.id,
        inp.input_type.value,
        provider_name,
        len(description),
    )
    return await _persist_extraction(
        input_id=inp.id,
        input_type=inp.input_type,
        content=description,
        status=InputStatus.ingested,
        provider=provider_name,
    )


# ── Dispatch: text-vs-visual routing (Property 3, Req 2.1/2.2/2.3) ───────────


async def extract_input(inp: TpiInput, llm: MultimodalLLMProvider) -> Extraction:
    """Route one input to the correct extraction path (Property 3).

    Visual inputs (``circuit_diagram`` / ``drawing`` — the members of
    ``_VISUAL_TYPES``) go through :func:`extract_visual` and therefore use the
    multimodal LLM; text procedures (``testing_procedure`` /
    ``operating_procedure``) go through :func:`extract_text` and never touch the
    provider. The LLM path is invoked **if and only if** the input is visual
    (Req 2.1, 2.2, 2.3; Property 3).
    """
    if inp.input_type in _VISUAL_TYPES:
        return await extract_visual(inp, llm)
    return await extract_text(inp)


# ── Read-back helper (for later tasks/tests) ─────────────────────────────────


def _row_to_extraction(row) -> Extraction:
    """Build an :class:`Extraction` from a joined ``tpi_extractions`` row.

    ``content_json`` is JSON-in-TEXT and is parsed back into a dict; a malformed
    or empty value yields ``{}`` so the read never crashes on a bad row.
    """
    raw = row["content_json"]
    try:
        content = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        content = {}
    return Extraction(
        input_id=row["input_id"],
        input_type=InputType(row["input_type"]),
        content=content,
        status=InputStatus(row["status"]),
        provider=row["provider"],
    )


async def get_extractions(pcba_id: str) -> list[Extraction]:
    """Read back all extractions for a PCBA (joins ``tpi_extractions`` to inputs).

    Joins ``tpi_extractions`` to ``tpi_inputs`` on ``input_id`` so the caller
    gets each extraction alongside its input's type, scoped to one PCBA. Ordered
    by the extraction row's ``rowid`` for a stable, insertion-ordered read that
    the mapping/generation stage and tests can rely on.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT e.input_id AS input_id,
                  i.input_type AS input_type,
                  e.content_json AS content_json,
                  e.status AS status,
                  e.provider AS provider
             FROM tpi_extractions e
             JOIN tpi_inputs i ON i.id = e.input_id
            WHERE i.pcba_id = ?
            ORDER BY e.rowid ASC""",
        (pcba_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_extraction(r) for r in rows]
