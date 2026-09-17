"""Generation service for the PCBA TPI Generation feature.

Drafts each section's narrative via the multimodal provider against the mapped
structure, producing a :class:`DraftTpi` that covers, at minimum, test steps,
expected results, and referenced equipment (Req 3.1). Provenance and
``incomplete`` markers from the mapping stage are preserved: a section derived
from a flagged input stays marked ``incomplete`` and is never omitted silently
(Req 3.4). Drafts persist to ``tpi_drafts`` / ``tpi_sections``.

The generation stage ENRICHES the mapped content into a narrative draft
(Req 3.1): for each mapped :class:`TpiSection` it calls the multimodal
provider's ``draft_section`` with a context built from the section's mapped
content plus its provenance/incomplete state, and replaces the section's
``content`` with the returned narrative. It never invents sections and never
drops one — the required sections (``test_steps``, ``expected_results``,
``equipment``) are always present because mapping always produces them and this
stage drafts every section it is given.

Per-section failure is non-fatal (mirrors the no-fabrication / flag-not-fail
philosophy used across ingestion and extraction): if ``draft_section`` raises
for one section, that section keeps its mapped content as a fallback and is
marked ``incomplete=True`` so the reviewer knows generation didn't fully
succeed, a warning is logged, and drafting continues for the remaining
sections. A single provider hiccup never fails the whole draft.

Conventions mirror the source-comparison services (``sc_review.py``) and the
sibling ``tpi_*`` services: the ``get_db()`` singleton connection, the
``tpi_drafts`` schema (``pcba_id`` PK, ``template_kind``, ``provider``,
``review_state`` default ``'drafted'``), reuse of ``tpi_mapping.save_sections``
/ ``get_sections`` for the drafted sections (JSON-in-TEXT provenance + ``0/1``
incomplete flag), and the ``tpi_pcbas.status`` column for the pipeline badge.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

from app.config import settings
from app.db.database import get_db
from app.services.tpi_extraction import get_extractions
from app.services.tpi_llm_provider import (
    MultimodalLLMProvider,
    get_multimodal_provider,
)
from app.services.tpi_mapping import (
    TpiSection,
    get_sections,
    map_to_structure,
    save_sections,
)

logger = logging.getLogger("app.tpi.generation")


# ── Draft model ──────────────────────────────────────────────────────────────


@dataclass
class DraftTpi:
    """A generated draft TPI for a PCBA (mirrors ``tpi_drafts`` + its sections).

    ``sections`` are the drafted :class:`TpiSection` list — each carrying its
    provenance (``source_input_ids``, Req 3.3) and ``incomplete`` flag (Req 3.4)
    unchanged from mapping, with ``content`` enriched into a narrative by the
    provider (Req 3.1). ``template_kind`` (``"placeholder"`` | ``"client"``) and
    ``provider`` record how the draft was produced. ``review_state`` mirrors the
    ``tpi_drafts.review_state`` column (``drafted`` | ``in_review`` |
    ``finalized``); a freshly generated draft is ``"drafted"``.
    """

    pcba_id: str
    sections: list[TpiSection]
    template_kind: str
    provider: str
    review_state: str = "drafted"


# ── Context building ─────────────────────────────────────────────────────────


def _build_context(section: TpiSection) -> dict:
    """Build the ``draft_section`` context from a mapped section.

    Carries the section's human title, the mapped content the provider should
    enrich into a narrative, and the mapping's ``incomplete`` signal so the
    provider (and any downstream log) can see the section leans on a flagged
    input. Provenance count is included as a lightweight signal without leaking
    the raw ids into the prompt.
    """
    return {
        "title": section.title,
        "mapped_content": section.content,
        "incomplete": section.incomplete,
        "source_input_count": len(section.source_input_ids),
    }


async def _draft_one(
    section: TpiSection, llm: MultimodalLLMProvider
) -> TpiSection:
    """Draft one section, preserving provenance and the incomplete contract.

    Calls ``llm.draft_section(section.key, context)`` and returns a new
    :class:`TpiSection` whose ``content`` is the enriched narrative while
    ``key`` / ``title`` / ``source_input_ids`` are carried through unchanged
    (Req 3.3) and ``incomplete`` is preserved (Req 3.4) — a mapped section that
    was incomplete stays incomplete in the draft.

    On a provider error the section is NOT dropped: it keeps its mapped content
    as a fallback and is marked ``incomplete=True`` so the reviewer knows
    generation didn't fully succeed for it. The error is logged, never raised —
    so one failing section never fails the whole draft (Req 3.4; no-fabrication /
    flag-not-fail philosophy).
    """
    try:
        narrative = await llm.draft_section(section.key, _build_context(section))
    except Exception as exc:  # noqa: BLE001 - any provider error flags, never fails the draft
        logger.warning(
            "draft_section failed for section key=%s (provider=%s): %s; "
            "keeping mapped content and marking incomplete",
            section.key,
            getattr(llm, "name", "unknown"),
            exc,
        )
        return TpiSection(
            key=section.key,
            title=section.title,
            content=section.content,  # fallback: mapped content retained
            source_input_ids=list(section.source_input_ids),  # provenance preserved
            incomplete=True,  # generation didn't fully succeed for this section
        )

    # A provider that returns nothing usable is treated like a soft failure:
    # keep the mapped content rather than blanking the section, and flag it.
    if not isinstance(narrative, str) or not narrative.strip():
        logger.warning(
            "draft_section returned empty/invalid narrative for section key=%s "
            "(provider=%s); keeping mapped content and marking incomplete",
            section.key,
            getattr(llm, "name", "unknown"),
        )
        return TpiSection(
            key=section.key,
            title=section.title,
            content=section.content,
            source_input_ids=list(section.source_input_ids),
            incomplete=True,
        )

    # Success: enrich content, preserve provenance and the incomplete flag
    # exactly as mapping set it (a flagged-input section stays incomplete).
    return TpiSection(
        key=section.key,
        title=section.title,
        content=narrative.strip(),
        source_input_ids=list(section.source_input_ids),
        incomplete=section.incomplete,
    )


# ── Persistence ──────────────────────────────────────────────────────────────


async def _upsert_draft(pcba_id: str, template_kind: str, provider: str) -> None:
    """Upsert the one ``tpi_drafts`` row for a PCBA (Req 3.1).

    ``pcba_id`` is the PK (one draft per PCBA), so re-generating a draft refreshes
    ``template_kind`` / ``provider`` and resets ``review_state`` to ``'drafted'``
    — a regenerated draft returns to the review queue rather than keeping a stale
    finalized state.
    """
    db = await get_db()
    await db.execute(
        """INSERT INTO tpi_drafts (pcba_id, template_kind, provider, review_state)
           VALUES (?, ?, ?, 'drafted')
           ON CONFLICT(pcba_id) DO UPDATE SET
               template_kind = excluded.template_kind,
               provider = excluded.provider,
               review_state = 'drafted'""",
        (pcba_id, template_kind, provider),
    )
    await db.commit()


async def _set_pcba_status(pcba_id: str, status: str) -> None:
    """Update the ``tpi_pcbas.status`` badge column (Req 6.9) if the row exists."""
    db = await get_db()
    await db.execute(
        "UPDATE tpi_pcbas SET status = ? WHERE pcba_id = ?",
        (status, pcba_id),
    )
    await db.commit()


def _infer_template_kind(sections: list[TpiSection]) -> str:
    """Infer the template kind from the mapped section keys.

    The placeholder template (``tpi_mapping.placeholder_template``) always
    contains the ``overview``/``references`` brackets around the required
    sections; that shape is the current ``[CONFIRM]`` default. Without an
    explicit ``template_kind`` argument, generation records ``"placeholder"`` so
    the draft is honestly flagged as built against the stand-in structure rather
    than a confirmed client template. Callers with the real template pass
    ``template_kind`` explicitly.
    """
    return "placeholder"


# ── Public API ───────────────────────────────────────────────────────────────


async def generate_draft(
    pcba_id: str,
    sections: list[TpiSection],
    llm: MultimodalLLMProvider,
    template_kind: str | None = None,
) -> DraftTpi:
    """Generate a draft TPI by enriching each mapped section into a narrative.

    For every section produced by mapping, call ``llm.draft_section`` with a
    context built from the section's mapped content and provenance/incomplete
    state, and use the returned text as the section's drafted ``content``
    (Req 3.1). The required sections (``test_steps``, ``expected_results``,
    ``equipment``) are covered because mapping always produces them and this
    stage drafts every section it is given — none is dropped.

    Provenance is preserved (``source_input_ids`` unchanged, Req 3.3) and the
    ``incomplete`` contract holds (Req 3.4): a section whose ``incomplete`` was
    ``True`` from a flagged input stays ``incomplete`` in the draft. If a
    provider call fails for a section, that section keeps its mapped content
    (fallback) and is marked ``incomplete=True`` rather than crashing the draft.

    Persists the result: upserts the ``tpi_drafts`` row (``template_kind`` from
    the ``template_kind`` argument or inferred, defaulting to ``'placeholder'``;
    ``provider = llm.name``; ``review_state = 'drafted'``), saves the drafted
    sections via :func:`save_sections` (overwriting the mapped ones, provenance
    + incomplete preserved), and sets ``tpi_pcbas.status = 'drafted'``. Returns
    the :class:`DraftTpi`.
    """
    provider_name = getattr(llm, "name", "unknown")
    kind = template_kind or _infer_template_kind(sections)

    drafted: list[TpiSection] = [await _draft_one(s, llm) for s in sections]

    # Persist: draft row, drafted sections (replaces the mapped ones), status.
    await _upsert_draft(pcba_id, template_kind=kind, provider=provider_name)
    await save_sections(pcba_id, drafted)
    await _set_pcba_status(pcba_id, "drafted")

    logger.info(
        "Generated draft for pcba_id=%s: %d section(s) (%d incomplete), "
        "template_kind=%s provider=%s",
        pcba_id,
        len(drafted),
        sum(1 for s in drafted if s.incomplete),
        kind,
        provider_name,
    )
    return DraftTpi(
        pcba_id=pcba_id,
        sections=drafted,
        template_kind=kind,
        provider=provider_name,
        review_state="drafted",
    )


async def get_draft(pcba_id: str) -> DraftTpi | None:
    """Read back a persisted draft for a PCBA, or ``None`` if none exists.

    Reads the ``tpi_drafts`` row for ``template_kind`` / ``provider`` /
    ``review_state`` and the drafted sections via
    :func:`tpi_mapping.get_sections` (which restores provenance and the
    ``incomplete`` flag). Returns ``None`` when there is no draft row for the
    PCBA, so callers can distinguish "not yet generated" from an empty draft.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT template_kind, provider, review_state
             FROM tpi_drafts
            WHERE pcba_id = ?""",
        (pcba_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    sections = await get_sections(pcba_id)
    return DraftTpi(
        pcba_id=pcba_id,
        sections=sections,
        template_kind=row["template_kind"],
        provider=row["provider"],
        review_state=row["review_state"],
    )


async def process_pcba(
    pcba_id: str,
    llm: MultimodalLLMProvider | None = None,
) -> DraftTpi:
    """Run the full generation chain for a PCBA and return the draft.

    Thin convenience over the pipeline so the ``/tpi/pcbas/{id}/process`` endpoint
    (task 8.1) and the end-to-end wiring (task 11) call a single function:
    :func:`tpi_extraction.get_extractions` → :func:`tpi_mapping.map_to_structure`
    → :func:`generate_draft`. Assumes ingestion and extraction have already run
    for the PCBA (the process endpoint runs extraction before this).

    ``llm`` defaults to the configured provider via ``get_multimodal_provider``,
    which selects the deterministic mock unless configured otherwise (Req 8.1),
    so this runs out of the box with no network access or API key.
    """
    provider = llm or get_multimodal_provider(settings)
    extractions = await get_extractions(pcba_id)
    sections = map_to_structure(extractions)
    return await generate_draft(pcba_id, sections, provider)
