"""Mapping service for the PCBA TPI Generation feature.

Places extracted content into the sections of a TPI structure (test steps,
expected results, referenced equipment) via :func:`map_to_structure` (Req 3.1).
Each resulting :class:`TpiSection` carries provenance back to the source input
id(s) it was derived from (Req 3.3) and an ``incomplete`` flag set when a
contributing input was flagged for manual annotation (Req 3.4).

Client TPI template availability is a ``[CONFIRM]`` item: when the client's own
template is unavailable, mapping uses the documented placeholder structure
(Req 3.2, 5.3). The template is kept swappable — :class:`TpiTemplate` carries an
ordered ``sections`` list of ``(key, title)`` pairs and a ``kind`` marker
(``"placeholder"`` | ``"client"``) — so it can be replaced WITHOUT touching the
extraction stage (Req 5.3). :func:`placeholder_template` returns the documented
placeholder structure used until the client template is confirmed.

Design boundary: this stage MAPS extracted content into sections and composes an
initial ``content`` string per section from real extracted content — it does not
call the LLM. The generation stage (task 5.2) later enriches/replaces that
content via ``draft_section``. Keeping the mapping pure (no DB) makes it easy to
property-test; :func:`save_sections` / :func:`get_sections` handle persistence
to ``tpi_sections`` separately.

Conventions mirror the source-comparison services (``sc_review.py``): the
``get_db()`` singleton connection, ``uuid4`` string ids, JSON-in-TEXT for the
``source_input_ids`` list, and ``0/1`` integers for the ``incomplete`` flag.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field

from app.db.database import get_db
from app.services.tpi_extraction import Extraction
from app.services.tpi_types import InputStatus, InputType

logger = logging.getLogger("app.tpi.mapping")


# ── TPI structure models ─────────────────────────────────────────────────────


@dataclass
class TpiSection:
    """One section of a TPI structure (mirrors ``tpi_sections``, design Data Models).

    ``key`` is a stable machine identifier (e.g. ``"test_steps"``); ``title`` is
    its human label. ``content`` is the composed section text — mapping produces
    an initial value from real extracted content that generation (task 5.2) may
    later enrich or replace. ``source_input_ids`` records provenance back to the
    input id(s) whose extractions fed this section (Req 3.3). ``incomplete`` is
    ``True`` when ANY contributing extraction was flagged for manual annotation
    (Req 3.4) — the section is still produced and never omitted, just marked.

    The persisted row's ``id`` is assigned at save time (:func:`save_sections`)
    rather than carried on the dataclass, so :func:`map_to_structure` can stay a
    pure, DB-free function.
    """

    key: str
    title: str
    content: str
    source_input_ids: list[str] = field(default_factory=list)
    incomplete: bool = False


@dataclass(frozen=True)
class TpiTemplate:
    """A swappable TPI structure — an ordered set of ``(key, title)`` sections.

    ``kind`` marks the template's origin: ``"placeholder"`` for the documented
    stand-in used while the client's own template is a ``[CONFIRM]`` item
    (Req 3.2, 5.3), or ``"client"`` once the real template is confirmed and
    provided (Req 5.2). ``sections`` is the ordered list of ``(key, title)``
    pairs. Because the template is a plain data structure consumed only by
    :func:`map_to_structure`, swapping it in requires no change to the extraction
    stage (Req 5.3).
    """

    kind: str
    sections: tuple[tuple[str, str], ...]


# ── Placeholder template (Req 3.2, 5.3) ──────────────────────────────────────
#
# The client's real TPI template is a [CONFIRM] open item. Until it is provided,
# mapping uses this documented placeholder structure consistently across all
# sample PCBAs (Req 5.3). The three sections named by Req 3.1 — test steps,
# expected results, referenced equipment — are always present; overview and
# references bracket them so the draft reads like a recognizable procedure. When
# the client template is confirmed, construct a TpiTemplate(kind="client", ...)
# with the real sections and pass it to map_to_structure — no other change is
# needed (Req 5.3).

# Ordered placeholder sections: (key, title). Order is the order they appear in
# the drafted TPI.
_PLACEHOLDER_SECTIONS: tuple[tuple[str, str], ...] = (
    ("overview", "Overview"),
    ("test_steps", "Test Steps"),
    ("expected_results", "Expected Results"),
    ("equipment", "Referenced Equipment"),
    ("references", "References"),
)


def placeholder_template() -> TpiTemplate:
    """Return the documented placeholder TPI template (Req 3.2, 5.3).

    Used whenever the client's own template is unavailable — which is the current
    ``[CONFIRM]`` state. The structure is intentionally simple and stable so it
    reads as a recognizable Test Procedure Instruction and stays consistent
    across all sample PCBAs. Swap in a ``TpiTemplate(kind="client", ...)`` once
    the real template is confirmed; no extraction change is required (Req 5.3).
    """
    return TpiTemplate(kind="placeholder", sections=_PLACEHOLDER_SECTIONS)


# ── Extraction accessors (small, defensive helpers) ──────────────────────────


def _content_text(extraction: Extraction) -> str:
    """Best-effort human-readable text from a text extraction's structured content.

    Text extractions (``extract_text``) carry ``{"title", "sections":[{heading,
    body}], "raw_text"}``. Prefer the heading/body sections (they are the
    structured view mapping is meant to compose from); fall back to ``raw_text``
    and finally to an empty string. Never raises.
    """
    content = extraction.content or {}
    sections = content.get("sections")
    if isinstance(sections, list) and sections:
        parts: list[str] = []
        for sec in sections:
            if not isinstance(sec, dict):
                continue
            heading = str(sec.get("heading", "")).strip()
            body = str(sec.get("body", "")).strip()
            if heading and heading != "preamble":
                parts.append(f"{heading}\n{body}".strip())
            elif body:
                parts.append(body)
        joined = "\n\n".join(p for p in parts if p).strip()
        if joined:
            return joined
    raw_text = content.get("raw_text")
    if isinstance(raw_text, str) and raw_text.strip():
        return raw_text.strip()
    return ""


def _visual_summary(extraction: Extraction) -> str:
    """Best-effort human-readable summary from a visual extraction's content.

    Visual extractions (``extract_visual``) carry ``{"summary", "components":
    [...], "notes"?}``. Compose the summary plus a components/notes line. Never
    raises.
    """
    content = extraction.content or {}
    parts: list[str] = []
    summary = content.get("summary")
    if isinstance(summary, str) and summary.strip():
        parts.append(summary.strip())
    components = content.get("components")
    if isinstance(components, list) and components:
        names = ", ".join(str(c) for c in components if str(c).strip())
        if names:
            parts.append(f"Identified elements: {names}.")
    notes = content.get("notes")
    if isinstance(notes, str) and notes.strip():
        parts.append(f"Notes: {notes.strip()}")
    return "\n".join(parts).strip()


def _components(extraction: Extraction) -> list[str]:
    """Extract the component/test-point list from a visual extraction, if any."""
    components = (extraction.content or {}).get("components")
    if isinstance(components, list):
        return [str(c).strip() for c in components if str(c).strip()]
    return []


# ── Section composition rules ────────────────────────────────────────────────
#
# The mapping is deliberately simple and documented (not over-engineered): each
# placeholder section draws from a sensible subset of the extractions.
#
#   overview          <- operating_procedure text + visual summaries
#   test_steps        <- testing_procedure text
#   expected_results  <- testing_procedure + operating_procedure text
#   equipment         <- equipment referenced in procedures + visual components
#   references        <- operating_procedure + visual descriptions
#
# A "contributing" extraction is one whose content fed the section; its input_id
# is recorded as provenance (Req 3.3) and, if it was flagged, the section is
# marked incomplete (Req 3.4). Generation (task 5.2) later enriches this content.

_TEXT_TYPES = frozenset({InputType.testing_procedure, InputType.operating_procedure})
_VISUAL_TYPES = frozenset({InputType.circuit_diagram, InputType.drawing})

# Keywords used to pull equipment-relevant lines out of procedure text. Kept
# small and documented; this is a heuristic, not an ontology.
_EQUIPMENT_KEYWORDS = (
    "equipment",
    "instrument",
    "meter",
    "multimeter",
    "oscilloscope",
    "power supply",
    "fixture",
    "probe",
    "tester",
    "gauge",
    "analyzer",
    "tool",
)


def _equipment_lines(text: str) -> list[str]:
    """Pull equipment-referencing lines out of procedure text (heuristic).

    Scans lines for the documented equipment keywords. Returns the matching
    lines, de-duplicated, preserving order. This is intentionally a light
    heuristic — generation (task 5.2) produces the polished narrative.
    """
    seen: set[str] = set()
    out: list[str] = []
    for line in text.splitlines():
        stripped = line.strip(" \t-*•")
        if not stripped:
            continue
        low = stripped.lower()
        if any(kw in low for kw in _EQUIPMENT_KEYWORDS):
            if stripped not in seen:
                seen.add(stripped)
                out.append(stripped)
    return out


def _compose(header: str, blocks: list[str]) -> str:
    """Join non-empty content blocks under an optional italic header line."""
    body = "\n\n".join(b for b in blocks if b and b.strip()).strip()
    return body


def map_to_structure(
    extractions: list[Extraction],
    template: TpiTemplate | None = None,
) -> list[TpiSection]:
    """Map extracted content into an ordered list of :class:`TpiSection` (Req 3.1).

    For each section in ``template`` (defaulting to :func:`placeholder_template`
    when none is passed — Req 3.2, 5.3), gather the relevant extracted content,
    compose an initial ``content`` string, record provenance
    (``source_input_ids``, Req 3.3), and set ``incomplete=True`` if ANY
    contributing extraction was flagged for manual annotation (Req 3.4). Every
    template section is ALWAYS produced — a section with no contributing content
    is emitted with a documented placeholder note, never omitted.

    Pure and DB-free so it is easy to property-test; persistence is handled by
    :func:`save_sections`.

    Mapping rules (documented, deliberately simple):

    * ``overview``          — operating-procedure text + visual summaries.
    * ``test_steps``        — testing-procedure text.
    * ``expected_results``  — testing- and operating-procedure text.
    * ``equipment``         — equipment referenced in procedures + visual components.
    * ``references``        — operating-procedure text + visual descriptions.

    Any section ``key`` not listed above (e.g. a future client-template section)
    receives a generic composition of all available extracted content so a
    swapped-in client template still produces populated sections.
    """
    tmpl = template or placeholder_template()

    # Partition extractions by role once, preserving input order.
    testing = [e for e in extractions if e.input_type == InputType.testing_procedure]
    operating = [
        e for e in extractions if e.input_type == InputType.operating_procedure
    ]
    visual = [e for e in extractions if e.input_type in _VISUAL_TYPES]

    def _section(key: str, title: str) -> TpiSection:
        """Compose one section from the relevant extractions per the rules above."""
        contributors: list[Extraction] = []
        blocks: list[str] = []

        if key == "test_steps":
            for e in testing:
                contributors.append(e)
                text = _content_text(e)
                if text:
                    blocks.append(text)
        elif key == "expected_results":
            for e in (*testing, *operating):
                contributors.append(e)
                text = _content_text(e)
                if text:
                    blocks.append(text)
        elif key == "equipment":
            for e in (*testing, *operating):
                lines = _equipment_lines(_content_text(e))
                if lines or e in testing or e in operating:
                    contributors.append(e)
                if lines:
                    blocks.append("\n".join(f"- {ln}" for ln in lines))
            for e in visual:
                comps = _components(e)
                if comps:
                    contributors.append(e)
                    blocks.append(
                        "Elements from "
                        f"{e.input_type.value}: " + ", ".join(comps) + "."
                    )
        elif key == "overview":
            for e in operating:
                contributors.append(e)
                text = _content_text(e)
                if text:
                    blocks.append(text)
            for e in visual:
                summary = _visual_summary(e)
                if summary or True:
                    contributors.append(e)
                if summary:
                    blocks.append(summary)
        elif key == "references":
            for e in operating:
                contributors.append(e)
                text = _content_text(e)
                if text:
                    blocks.append(text)
            for e in visual:
                summary = _visual_summary(e)
                contributors.append(e)
                if summary:
                    blocks.append(summary)
        else:
            # Unknown / future client-template section: draw from everything so
            # a swapped-in client template still yields populated sections.
            for e in extractions:
                contributors.append(e)
                text = _content_text(e) or _visual_summary(e)
                if text:
                    blocks.append(text)

        # De-duplicate contributors by input_id while preserving order.
        seen_ids: set[str] = set()
        unique_contributors: list[Extraction] = []
        for e in contributors:
            if e.input_id not in seen_ids:
                seen_ids.add(e.input_id)
                unique_contributors.append(e)

        source_input_ids = [e.input_id for e in unique_contributors]
        incomplete = any(
            e.status == InputStatus.flagged_for_manual_annotation
            for e in unique_contributors
        )

        content = _compose(title, blocks)
        if not content:
            # Never omit a section — emit a documented placeholder note so the
            # draft still covers every required section (Req 3.1, 3.4).
            if incomplete:
                content = (
                    f"[Incomplete] No usable extracted content for '{title}'. "
                    "One or more source inputs were flagged for manual "
                    "annotation; complete this section during review."
                )
            else:
                content = (
                    f"[Placeholder] No extracted content mapped to '{title}' yet. "
                    "This section will be drafted during generation/review."
                )

        return TpiSection(
            key=key,
            title=title,
            content=content,
            source_input_ids=source_input_ids,
            incomplete=incomplete,
        )

    sections = [_section(key, title) for key, title in tmpl.sections]
    logger.info(
        "Mapped %d extraction(s) into %d section(s) using template kind=%s "
        "(%d incomplete)",
        len(extractions),
        len(sections),
        tmpl.kind,
        sum(1 for s in sections if s.incomplete),
    )
    return sections


# ── Persistence (Req 3.3, 3.4; JSON-in-TEXT + 0/1 flag) ──────────────────────


async def save_sections(pcba_id: str, sections: list[TpiSection]) -> None:
    """Persist a PCBA's mapped sections to ``tpi_sections``, replacing prior rows.

    Deletes any existing sections for ``pcba_id`` first so re-mapping is
    idempotent (one set of sections per PCBA), then inserts each section with a
    fresh uuid id. ``source_input_ids`` is stored as a JSON list (provenance,
    Req 3.3) and ``incomplete`` as a ``0/1`` integer (Req 3.4), matching the
    schema and the JSON-in-TEXT convention used across the AVIP services.
    """
    db = await get_db()
    await db.execute("DELETE FROM tpi_sections WHERE pcba_id = ?", (pcba_id,))
    for section in sections:
        await db.execute(
            """INSERT INTO tpi_sections
                   (id, pcba_id, key, title, content, source_input_ids, incomplete)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                pcba_id,
                section.key,
                section.title,
                section.content,
                json.dumps(section.source_input_ids),
                1 if section.incomplete else 0,
            ),
        )
    await db.commit()
    logger.info(
        "Saved %d section(s) for pcba_id=%s (replaced prior rows)",
        len(sections),
        pcba_id,
    )


def _row_to_section(row) -> TpiSection:
    """Build a :class:`TpiSection` from a ``tpi_sections`` aiosqlite Row.

    ``source_input_ids`` is JSON-in-TEXT and parsed back into a list; a malformed
    value yields ``[]`` so the read never crashes. ``incomplete`` (``0/1``) is
    coerced back to a bool.
    """
    raw = row["source_input_ids"]
    try:
        source_input_ids = json.loads(raw) if raw else []
    except (json.JSONDecodeError, TypeError):
        source_input_ids = []
    if not isinstance(source_input_ids, list):
        source_input_ids = []
    return TpiSection(
        key=row["key"],
        title=row["title"],
        content=row["content"],
        source_input_ids=[str(x) for x in source_input_ids],
        incomplete=bool(row["incomplete"]),
    )


async def get_sections(pcba_id: str) -> list[TpiSection]:
    """Read back all persisted sections for a PCBA, in insertion order.

    Ordered by ``rowid`` so the read reflects the template's section order as
    written by :func:`save_sections`. Lets the generation/review stages and
    tests round-trip the mapped structure.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT key, title, content, source_input_ids, incomplete
             FROM tpi_sections
            WHERE pcba_id = ?
            ORDER BY rowid ASC""",
        (pcba_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_section(r) for r in rows]
