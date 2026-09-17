"""Review service and audit trail for the PCBA TPI Generation feature.

Presents drafts for human review, records a reviewer's corrections as the final
TPI, and writes an audit entry per decision — consistent with the
source-comparison review/audit pattern (``sc_review.py``). ``list_drafts``
returns drafts for the review UI queue; ``finalize`` records the corrected
sections as the final TPI and writes exactly one ``tpi_review_audit`` row
capturing who / when / what changed (Req 4.3, 4.4); ``list_final`` returns only
finalized TPIs so unreviewed drafts never reach the final set (Req 4.1, 4.2;
Property 5). ``get_audit`` reads a PCBA's audit trail for the audit endpoint
(task 8.2).

Contract: a draft becomes part of the final set only after ``finalize``; every
finalize writes one audit row.

Conventions mirror ``sc_review.py`` and the sibling ``tpi_*`` services: the
``get_db()`` singleton connection, ``uuid4`` string ids, ISO-8601 UTC
timestamps, JSON-in-TEXT for structured payloads (``changes_json``), and reuse
of ``tpi_generation.get_draft`` / ``tpi_mapping.get_sections`` /
``save_sections`` so drafts hydrate with provenance (Req 3.3) and the
``incomplete`` flag (Req 3.4) preserved end to end.
"""

from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.db.database import get_db
from app.services.tpi_generation import DraftTpi, get_draft
from app.services.tpi_mapping import TpiSection, get_sections, save_sections

logger = logging.getLogger("app.tpi.review")


# ── Review decision model ────────────────────────────────────────────────────


@dataclass
class TpiReviewDecision:
    """A reviewer's finalize decision for a PCBA (design: Review service).

    ``corrected_sections`` is the reviewer-approved section list that becomes
    the final TPI (Req 4.3) — each :class:`TpiSection` carries its own
    provenance (``source_input_ids``, Req 3.3) and ``incomplete`` flag (Req 3.4),
    which :func:`finalize` preserves verbatim. ``reviewer`` and ``note`` are
    recorded on the audit row (who / what, Req 4.4); ``note`` is optional.
    """

    pcba_id: str
    reviewer: str
    corrected_sections: list[TpiSection] = field(default_factory=list)
    note: str | None = None


# ── Helpers ──────────────────────────────────────────────────────────────────


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _compute_changes(
    before: list[TpiSection],
    after: list[TpiSection],
    note: str | None,
) -> dict:
    """Compute an honest "what changed" payload for the audit row (Req 4.4).

    Compares the reviewer's ``after`` (corrected) sections against the ``before``
    (drafted) sections, keyed by section ``key``. A section key is "changed" when
    its ``content`` differs, its ``incomplete`` flag flips, or its provenance
    (``source_input_ids``) differs; keys present only on one side are recorded as
    added / removed. The payload keeps a compact per-changed-key before/after of
    ``content`` (so the diff is auditable) plus a summary of the changed keys and
    the reviewer's ``note``. Deliberately simple and truthful — it records what a
    reviewer actually altered, not a guess.
    """
    before_by_key = {s.key: s for s in before}
    after_by_key = {s.key: s for s in after}

    changed_keys: list[str] = []
    section_changes: dict[str, dict] = {}

    for key, aft in after_by_key.items():
        bef = before_by_key.get(key)
        if bef is None:
            changed_keys.append(key)
            section_changes[key] = {
                "change": "added",
                "before": None,
                "after": aft.content,
                "incomplete_before": None,
                "incomplete_after": aft.incomplete,
            }
            continue
        content_changed = bef.content != aft.content
        incomplete_changed = bool(bef.incomplete) != bool(aft.incomplete)
        provenance_changed = list(bef.source_input_ids) != list(aft.source_input_ids)
        if content_changed or incomplete_changed or provenance_changed:
            changed_keys.append(key)
            section_changes[key] = {
                "change": "edited",
                "content_changed": content_changed,
                "incomplete_changed": incomplete_changed,
                "provenance_changed": provenance_changed,
                "before": bef.content if content_changed else None,
                "after": aft.content if content_changed else None,
                "incomplete_before": bef.incomplete,
                "incomplete_after": aft.incomplete,
            }

    removed_keys = [k for k in before_by_key if k not in after_by_key]
    for key in removed_keys:
        bef = before_by_key[key]
        section_changes[key] = {
            "change": "removed",
            "before": bef.content,
            "after": None,
            "incomplete_before": bef.incomplete,
            "incomplete_after": None,
        }

    return {
        "changed_section_keys": changed_keys,
        "removed_section_keys": removed_keys,
        "section_count_before": len(before),
        "section_count_after": len(after),
        "sections": section_changes,
        "note": note,
    }


# ── Public API ───────────────────────────────────────────────────────────────


async def list_drafts(status: str | None = None) -> list[DraftTpi]:
    """Return drafts for the review UI queue (design: Review service).

    This is the QUEUE view — it excludes nothing by itself. When ``status`` is
    given (``"drafted"`` | ``"in_review"`` | ``"finalized"``) it filters by
    ``tpi_drafts.review_state``; when ``None`` it returns every draft. Each
    :class:`DraftTpi` is hydrated via :func:`tpi_generation.get_draft`, so its
    sections carry provenance (Req 3.3) and the ``incomplete`` flag (Req 3.4).
    Ordered by ``pcba_id`` for a stable queue.
    """
    db = await get_db()
    if status is None:
        cursor = await db.execute(
            "SELECT pcba_id FROM tpi_drafts ORDER BY pcba_id ASC"
        )
    else:
        cursor = await db.execute(
            "SELECT pcba_id FROM tpi_drafts WHERE review_state = ? ORDER BY pcba_id ASC",
            (status,),
        )
    rows = await cursor.fetchall()

    drafts: list[DraftTpi] = []
    for row in rows:
        draft = await get_draft(row["pcba_id"])
        if draft is not None:  # defensive: draft row implies a hydratable draft
            drafts.append(draft)
    return drafts


async def finalize(decision: TpiReviewDecision) -> DraftTpi:
    """Record a reviewer's corrections as the final TPI and audit it (Req 4.3, 4.4).

    Steps, in order:

    1. **Guard** — read the current draft via :func:`tpi_generation.get_draft`.
       If there is no draft for ``decision.pcba_id``, raise :class:`ValueError`
       rather than finalizing nothing.
    2. **Compute what changed** — compare ``decision.corrected_sections`` against
       the current drafted sections (:func:`tpi_mapping.get_sections`) BEFORE
       overwriting, so the audit records the real edits (:func:`_compute_changes`).
    3. **Record the corrected sections as the final TPI** (Req 4.3) via
       :func:`tpi_mapping.save_sections`, preserving each section's provenance
       (``source_input_ids``, Req 3.3) and ``incomplete`` flag (Req 3.4).
    4. **Advance state** — set ``tpi_drafts.review_state = 'finalized'`` and
       ``tpi_pcbas.status = 'finalized'`` so the draft leaves the review queue
       and reaches the final set (Property 5).
    5. **Write exactly ONE audit row** (Req 4.4) into ``tpi_review_audit``:
       ``id`` = uuid, ``pcba_id``, ``reviewer`` = ``decision.reviewer``,
       ``action = 'finalize'``, ``changes_json`` = the what-changed payload (who
       / when are captured by ``reviewer`` / ``decided_at``), ``decided_at`` =
       ISO now.

    Returns the finalized :class:`DraftTpi` (re-read so its sections and
    ``review_state`` reflect the persisted final TPI).

    Raises:
        ValueError: if no draft exists for ``decision.pcba_id`` (nothing to
            finalize).
    """
    existing = await get_draft(decision.pcba_id)
    if existing is None:
        logger.warning(
            "Finalize rejected: no draft for pcba_id=%s", decision.pcba_id
        )
        raise ValueError(
            f"Cannot finalize: no draft exists for pcba_id={decision.pcba_id!r}"
        )

    # Capture the drafted sections BEFORE overwriting so the audit is honest.
    before_sections = await get_sections(decision.pcba_id)
    corrected = list(decision.corrected_sections)
    changes = _compute_changes(before_sections, corrected, decision.note)

    db = await get_db()

    # 1) Record the corrected sections as the final TPI (Req 4.3). save_sections
    #    replaces the drafted rows, preserving provenance + incomplete per section.
    await save_sections(decision.pcba_id, corrected)

    # 2) Advance the draft + PCBA state to finalized (Property 5).
    await db.execute(
        "UPDATE tpi_drafts SET review_state = 'finalized' WHERE pcba_id = ?",
        (decision.pcba_id,),
    )
    await db.execute(
        "UPDATE tpi_pcbas SET status = 'finalized' WHERE pcba_id = ?",
        (decision.pcba_id,),
    )

    # 3) Write EXACTLY ONE audit row (Req 4.4).
    audit_id = str(uuid.uuid4())
    decided_at = _now_iso()
    await db.execute(
        """INSERT INTO tpi_review_audit
               (id, pcba_id, reviewer, action, changes_json, decided_at)
           VALUES (?, ?, ?, 'finalize', ?, ?)""",
        (
            audit_id,
            decision.pcba_id,
            decision.reviewer,
            json.dumps(changes),
            decided_at,
        ),
    )

    await db.commit()

    logger.info(
        "Finalized TPI pcba_id=%s reviewer=%s changed_keys=%s audit_id=%s "
        "decided_at=%s",
        decision.pcba_id,
        decision.reviewer,
        changes["changed_section_keys"],
        audit_id,
        decided_at,
    )

    # Re-read so the returned draft reflects the persisted final TPI + state.
    finalized = await get_draft(decision.pcba_id)
    assert finalized is not None  # we just wrote it; guarded above
    return finalized


async def list_final() -> list[DraftTpi]:
    """Return ONLY finalized TPIs (Req 4.1, 4.2; Property 5).

    Filters ``tpi_drafts`` to ``review_state = 'finalized'`` so unreviewed drafts
    (``drafted`` / ``in_review``) are excluded from the final set — a draft
    reaches the final set only after :func:`finalize`. Each :class:`DraftTpi` is
    hydrated via :func:`tpi_generation.get_draft`, preserving section provenance
    (Req 3.3) and the ``incomplete`` flag (Req 3.4). Ordered by ``pcba_id`` for
    a stable listing.
    """
    return await list_drafts(status="finalized")


def _row_to_audit(row) -> dict:
    """Build an audit dict from a ``tpi_review_audit`` row.

    ``changes_json`` is JSON-in-TEXT and parsed back into ``changes``; a
    malformed value yields ``{}`` so a read never crashes. The ``reviewer`` /
    ``decided_at`` columns carry the who / when (Req 4.4).
    """
    raw = row["changes_json"]
    try:
        changes = json.loads(raw) if raw else {}
    except (json.JSONDecodeError, TypeError):
        changes = {}
    return {
        "id": row["id"],
        "pcba_id": row["pcba_id"],
        "reviewer": row["reviewer"],
        "action": row["action"],
        "changes": changes,
        "decided_at": row["decided_at"],
    }


async def get_audit(pcba_id: str) -> list[dict]:
    """Return the review audit trail for a PCBA, oldest first (Req 4.4).

    Reads every ``tpi_review_audit`` row for ``pcba_id`` ordered by
    ``decided_at`` (ascending) so the caller (task 8.2's ``/tpi/audit/{id}``
    endpoint) sees the decision history in the order it happened. Each row's
    ``changes_json`` is parsed back into a ``changes`` dict. Returns ``[]`` when
    the PCBA has no audit rows.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, pcba_id, reviewer, action, changes_json, decided_at
             FROM tpi_review_audit
            WHERE pcba_id = ?
            ORDER BY decided_at ASC""",
        (pcba_id,),
    )
    rows = await cursor.fetchall()
    return [_row_to_audit(r) for r in rows]
