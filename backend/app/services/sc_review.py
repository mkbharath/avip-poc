"""Review gate + audit for the source-comparison feature (LAIR / FAIR / SHQ).

This service is the **mandatory human review gate** every flagged discrepancy
passes through. Discrepancies are created by the comparison service as
``pending`` (see ``services/comparison.py``); this module is the only path that
moves a discrepancy to ``confirmed`` or ``dismissed`` (Property 7) and the only
place review decisions are recorded.

``decide`` does three things atomically (Req 6.3, 9.3, Property 6):

  * Updates ``sc_discrepancies.review_state`` to the decision
    (``confirmed`` | ``dismissed``).
  * **Upserts** the ``sc_review_decisions`` row (``UNIQUE(discrepancy_id)``) so
    the *latest* decision wins — re-deciding a discrepancy overwrites the
    single current-decision row with the new decision, reviewer, note, and
    timestamp.
  * **Always appends** an immutable ``sc_review_audit`` row. Every decision —
    including re-decisions — writes a new audit row, so the full decision
    history is retained append-only (Req 9.3, Property 6).

Read helpers back the review endpoints (task 5.2) and the report service
(task 6.1):

  * :func:`list_pending` / :func:`get_review_queue` — the pending review queue
    shaped like AVIP's existing review queue (``{data, total_count}``) so the
    workbench UI feels native (Req 6.1, 6.2).
  * :func:`get_discrepancy` — single-discrepancy detail with ``values`` parsed
    (Req 6.2).
  * :func:`list_confirmed` — the confirmed-**only** query helper the report
    service uses so pending/dismissed discrepancies never reach the report
    (Property 5, Req 6.4, 6.5, 7.2), with optional part / lot / source / field /
    provenance filters (Req 7.2).

Structured logs are emitted for every decision, carrying reviewer identity,
note, and timestamp (Req 9.3, 9.4). No HTTP routes are added here — endpoints
live on the source-comparison router (task 5.2).
"""

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Literal

import aiosqlite

from app.db.database import get_db
from app.models.source_comparison import (
    Discrepancy,
    FieldType,
    Provenance,
    ReviewState,
)

logger = logging.getLogger("app.source_comparison.review")

Decision = Literal["confirmed", "dismissed"]

# Map the decision string to the review_state the discrepancy takes.
_DECISION_TO_STATE: dict[str, ReviewState] = {
    "confirmed": ReviewState.CONFIRMED,
    "dismissed": ReviewState.DISMISSED,
}


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _row_to_discrepancy(row: aiosqlite.Row) -> Discrepancy:
    """Build a :class:`Discrepancy` from an ``sc_discrepancies`` row.

    The ``"values"`` column is JSON-in-TEXT (quoted because ``values`` is a
    reserved word) and is parsed into the per-source dict.
    """
    raw_values = row["values"]
    values = json.loads(raw_values) if raw_values else {}
    return Discrepancy(
        id=row["id"],
        group_id=row["group_id"],
        part_number=row["part_number"],
        lot_number=row["lot_number"],
        field_name=row["field_name"],
        field_type=FieldType(row["field_type"]),
        values=values,
        provenance=Provenance(row["provenance"]),
        review_state=ReviewState(row["review_state"]),
    )


# ── Write path: the review gate ──────────────────────────────────────────────


async def decide(
    discrepancy_id: str,
    decision: Decision,
    reviewer: str,
    note: str | None = None,
) -> Discrepancy:
    """Record a review decision against a discrepancy (Req 6.3, 6.4, 6.5, 9.3).

    Updates the discrepancy's ``review_state`` to the decision, upserts the
    single current-decision row (``sc_review_decisions``, ``UNIQUE`` per
    discrepancy — latest decision wins), and **always** appends a new immutable
    ``sc_review_audit`` row so the full decision history is retained
    (Property 6).

    Args:
        discrepancy_id: the discrepancy being decided.
        decision: ``"confirmed"`` or ``"dismissed"``.
        reviewer: the reviewer's identity (recorded on the decision + audit).
        note: optional free-text note (recorded on the decision + audit).

    Returns:
        The updated :class:`Discrepancy` reflecting the new ``review_state``.

    Raises:
        ValueError: if ``decision`` is not a valid decision string.
        LookupError: if no discrepancy exists with ``discrepancy_id`` (the
            router maps this to a 404 with a clear message — task 5.2).
    """
    if decision not in _DECISION_TO_STATE:
        raise ValueError(
            f"Invalid decision {decision!r}; expected 'confirmed' or 'dismissed'."
        )

    db = await get_db()

    # Verify the discrepancy exists (404 / clear error if not).
    cursor = await db.execute(
        """SELECT id, group_id, part_number, lot_number, field_name, field_type,
                  "values", provenance, review_state
             FROM sc_discrepancies
            WHERE id = ?""",
        (discrepancy_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        logger.warning(
            "Review decision rejected: discrepancy not found: discrepancy_id=%s",
            discrepancy_id,
        )
        raise LookupError(f"Discrepancy not found: {discrepancy_id}")

    new_state = _DECISION_TO_STATE[decision]
    decided_at = _now_iso()

    # 1) Update the discrepancy's review_state to the decision.
    await db.execute(
        "UPDATE sc_discrepancies SET review_state = ? WHERE id = ?",
        (new_state.value, discrepancy_id),
    )

    # 2) Upsert the single current-decision row (latest decision wins).
    #    UNIQUE(discrepancy_id) means the conflict target is discrepancy_id.
    decision_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO sc_review_decisions
               (id, discrepancy_id, decision, reviewer, note, decided_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(discrepancy_id) DO UPDATE SET
               decision = excluded.decision,
               reviewer = excluded.reviewer,
               note = excluded.note,
               decided_at = excluded.decided_at""",
        (decision_id, discrepancy_id, decision, reviewer, note, decided_at),
    )

    # 3) ALWAYS append an immutable audit row (full history retained).
    audit_id = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO sc_review_audit
               (id, discrepancy_id, decision, reviewer, note, decided_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (audit_id, discrepancy_id, decision, reviewer, note, decided_at),
    )

    await db.commit()

    logger.info(
        "Review decision recorded: discrepancy_id=%s decision=%s reviewer=%s "
        "note=%s decided_at=%s audit_id=%s",
        discrepancy_id,
        decision,
        reviewer,
        note if note is not None else "",
        decided_at,
        audit_id,
    )

    # Reflect the new state on the returned model.
    return _row_to_discrepancy(row).model_copy(update={"review_state": new_state})


# ── Read helpers: review queue + detail (task 5.2) ───────────────────────────


async def list_pending() -> list[Discrepancy]:
    """Return all pending discrepancies for the review workbench (Req 6.1).

    Only ``review_state = 'pending'`` discrepancies appear — decided ones
    (confirmed/dismissed) are excluded so the queue shows exactly the
    outstanding review work.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, group_id, part_number, lot_number, field_name, field_type,
                  "values", provenance, review_state
             FROM sc_discrepancies
            WHERE review_state = ?
            ORDER BY created_at ASC, id ASC""",
        (ReviewState.PENDING.value,),
    )
    rows = await cursor.fetchall()
    return [_row_to_discrepancy(r) for r in rows]


async def get_review_queue() -> dict[str, object]:
    """Return the pending review queue shaped like AVIP's review queue (Req 6.1).

    Mirrors ``review.py::get_review_queue`` output shape ``{data, total_count}``
    so the UI can reuse the existing review-workbench patterns natively
    (Req 6.2). ``data`` is the list of pending discrepancies.
    """
    pending = await list_pending()
    data = [d.model_dump(mode="json") for d in pending]
    return {"data": data, "total_count": len(data)}


async def get_discrepancy(discrepancy_id: str) -> Discrepancy | None:
    """Return one discrepancy (with ``values`` parsed) for the workbench detail.

    Used by ``GET /source-comparison/review/{id}`` (task 5.2). Returns ``None``
    when no discrepancy exists so the router can raise a 404.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, group_id, part_number, lot_number, field_name, field_type,
                  "values", provenance, review_state
             FROM sc_discrepancies
            WHERE id = ?""",
        (discrepancy_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    return _row_to_discrepancy(row)


# ── Confirmed-only query helper for the report service (task 6.1) ────────────


async def list_confirmed(
    *,
    part_number: str | None = None,
    lot_number: str | None = None,
    source: str | None = None,
    field_name: str | None = None,
    provenance: str | None = None,
) -> list[Discrepancy]:
    """Return **confirmed-only** discrepancies for the report (Property 5).

    Pending and dismissed discrepancies are excluded — dismissed permanently
    (Req 6.4, 6.5) — so the report only ever surfaces reviewer-confirmed
    findings (Req 7.2). All filters are optional and ANDed; omitted filters
    match everything:

      * ``part_number`` / ``lot_number`` — exact match on the common key.
      * ``field_name`` — exact match on the discrepancy's field.
      * ``provenance`` — exact match on the provenance tag.
      * ``source`` — keep only discrepancies that carry a value from that source
        in their per-source ``values`` dict (filtered in Python since ``values``
        is JSON-in-TEXT).

    This is the clean helper the report service (task 6.1) calls so
    confirmed-only filtering lives in one place.
    """
    clauses: list[str] = ["review_state = ?"]
    params: list[str] = [ReviewState.CONFIRMED.value]
    if part_number is not None:
        clauses.append("part_number = ?")
        params.append(part_number)
    if lot_number is not None:
        clauses.append("lot_number = ?")
        params.append(lot_number)
    if field_name is not None:
        clauses.append("field_name = ?")
        params.append(field_name)
    if provenance is not None:
        clauses.append("provenance = ?")
        params.append(provenance)
    where = " AND ".join(clauses)

    db = await get_db()
    cursor = await db.execute(
        f"""SELECT id, group_id, part_number, lot_number, field_name, field_type,
                   "values", provenance, review_state
              FROM sc_discrepancies
             WHERE {where}
             ORDER BY part_number ASC, lot_number ASC, field_name ASC, id ASC""",
        tuple(params),
    )
    rows = await cursor.fetchall()
    discrepancies = [_row_to_discrepancy(r) for r in rows]

    # `source` filters on the JSON-in-TEXT `values` dict, which SQL can't easily
    # query — keep only discrepancies that carry a value from that source.
    if source is not None:
        discrepancies = [d for d in discrepancies if source in d.values]

    return discrepancies
