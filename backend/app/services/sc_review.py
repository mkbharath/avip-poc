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
    shaped like AVIP's existing review queue, extended with pagination
    (``{data, total_count, limit, offset}``) so the workbench UI feels native
    and never pulls the full pending set at once (Req 6.1, 6.2).
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

# Pagination defaults/caps shared by the pending queue and the confirmed report
# read paths. A default page keeps the API fast; the cap bounds worst-case work
# so a caller can never ask for an unbounded page (the root cause of the review
# list returning 67k+ rows and hanging the frontend).
DEFAULT_PAGE_LIMIT = 50
MAX_PAGE_LIMIT = 200


def _clamp_limit(limit: int | None) -> int:
    """Clamp a requested page ``limit`` into ``[1, MAX_PAGE_LIMIT]``.

    ``None`` (or a non-positive value) falls back to :data:`DEFAULT_PAGE_LIMIT`;
    anything above :data:`MAX_PAGE_LIMIT` is capped so a single page can never
    pull an unbounded number of rows.
    """
    if limit is None or limit <= 0:
        return DEFAULT_PAGE_LIMIT
    return min(limit, MAX_PAGE_LIMIT)


def _clamp_offset(offset: int | None) -> int:
    """Clamp a requested ``offset`` to a non-negative integer (default 0)."""
    if offset is None or offset < 0:
        return 0
    return offset

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


async def decide_many(
    discrepancy_ids: list[str],
    decision: Decision,
    reviewer: str,
    note: str | None = None,
) -> dict[str, object]:
    """Apply one review decision to many discrepancies (Req 6.3, 9.3, Property 6).

    Iterates ``discrepancy_ids`` and calls the same per-item :func:`decide`
    logic for each, so every decision still updates ``review_state``, upserts
    ``sc_review_decisions``, and appends an immutable ``sc_review_audit`` row —
    the full audit trail is preserved for every item, exactly as a single
    decide would produce.

    The ``decision`` value is validated **once up front** (a bad decision raises
    :class:`ValueError` before any item is touched — the router maps it to 422).
    Per-item lookups are resilient: an id with no matching discrepancy is
    collected into ``not_found`` rather than aborting the batch.

    Args:
        discrepancy_ids: the discrepancies to decide (may be empty).
        decision: ``"confirmed"`` or ``"dismissed"`` (validated once, up front).
        reviewer: the reviewer's identity (recorded per item).
        note: optional free-text note (recorded per item).

    Returns:
        A summary dict ``{"updated": <count success>, "not_found": [<missing
        ids>], "decision": decision}``. An empty ``discrepancy_ids`` yields
        ``{"updated": 0, "not_found": [], "decision": decision}`` — not an error.

    Raises:
        ValueError: if ``decision`` is not a valid decision string.
    """
    # Validate the decision once, up front (not per item).
    if decision not in _DECISION_TO_STATE:
        raise ValueError(
            f"Invalid decision {decision!r}; expected 'confirmed' or 'dismissed'."
        )

    updated = 0
    not_found: list[str] = []
    for discrepancy_id in discrepancy_ids:
        try:
            await decide(
                discrepancy_id=discrepancy_id,
                decision=decision,
                reviewer=reviewer,
                note=note,
            )
            updated += 1
        except LookupError:
            # Resilient: a missing id is collected, not fatal to the batch.
            not_found.append(discrepancy_id)

    logger.info(
        "Bulk review decision recorded: decision=%s reviewer=%s requested=%d "
        "updated=%d not_found=%d",
        decision,
        reviewer,
        len(discrepancy_ids),
        updated,
        len(not_found),
    )

    return {"updated": updated, "not_found": not_found, "decision": decision}


# ── Read helpers: review queue + detail (task 5.2) ───────────────────────────


async def count_pending() -> int:
    """Return the total number of pending discrepancies (all pages).

    A cheap ``COUNT(*)`` over the same ``pending`` predicate the queue page
    uses, so the paginated queue can report the full total alongside a single
    page of rows.
    """
    db = await get_db()
    cursor = await db.execute(
        "SELECT COUNT(*) FROM sc_discrepancies WHERE review_state = ?",
        (ReviewState.PENDING.value,),
    )
    row = await cursor.fetchone()
    try:
        return int(row[0]) if row is not None else 0
    except (TypeError, KeyError, IndexError):
        return 0


async def list_pending(
    limit: int | None = None,
    offset: int | None = None,
) -> list[Discrepancy]:
    """Return a page of pending discrepancies for the review workbench (Req 6.1).

    Only ``review_state = 'pending'`` discrepancies appear — decided ones
    (confirmed/dismissed) are excluded so the queue shows exactly the
    outstanding review work.

    Pagination (the fix for the queue returning 67k+ rows and hanging the UI):
    ``limit`` defaults to :data:`DEFAULT_PAGE_LIMIT` and is capped at
    :data:`MAX_PAGE_LIMIT`; ``offset`` defaults to 0. The ordering is stable
    (``created_at, id``) so paging is deterministic across requests. Passing
    ``limit=None`` still applies the default cap — there is intentionally no
    "fetch everything" mode on the pending queue.
    """
    page_limit = _clamp_limit(limit)
    page_offset = _clamp_offset(offset)
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, group_id, part_number, lot_number, field_name, field_type,
                  "values", provenance, review_state
             FROM sc_discrepancies
            WHERE review_state = ?
            ORDER BY created_at ASC, id ASC
            LIMIT ? OFFSET ?""",
        (ReviewState.PENDING.value, page_limit, page_offset),
    )
    rows = await cursor.fetchall()
    return [_row_to_discrepancy(r) for r in rows]


async def get_review_queue(
    limit: int | None = None,
    offset: int | None = None,
) -> dict[str, object]:
    """Return a page of the pending review queue (Req 6.1, 6.2).

    Mirrors AVIP's review-queue envelope so the UI can reuse the existing
    workbench patterns natively, extended with pagination metadata:
    ``{data, total_count, limit, offset}``. ``data`` is one page of pending
    discrepancies; ``total_count`` is the count of ALL pending discrepancies
    (not just the page) so the UI can render paging controls. ``limit`` /
    ``offset`` echo the effective (clamped) values applied.
    """
    page_limit = _clamp_limit(limit)
    page_offset = _clamp_offset(offset)
    total_count = await count_pending()
    pending = await list_pending(limit=page_limit, offset=page_offset)
    data = [d.model_dump(mode="json") for d in pending]
    return {
        "data": data,
        "total_count": total_count,
        "limit": page_limit,
        "offset": page_offset,
    }


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


def _confirmed_where(
    part_number: str | None,
    lot_number: str | None,
    field_name: str | None,
    provenance: str | None,
) -> tuple[str, list[str]]:
    """Build the SQL WHERE clause + params for the confirmed-only filters.

    Covers the filters SQL can express (``part_number`` / ``lot_number`` /
    ``field_name`` / ``provenance``); the ``source`` filter is applied in Python
    since it inspects the JSON-in-TEXT ``values`` dict. Shared by the row query
    and the count query so both stay in lock-step.
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
    return " AND ".join(clauses), params


async def list_confirmed(
    *,
    part_number: str | None = None,
    lot_number: str | None = None,
    source: str | None = None,
    field_name: str | None = None,
    provenance: str | None = None,
    limit: int | None = None,
    offset: int | None = None,
) -> tuple[list[Discrepancy], int]:
    """Return a page of **confirmed-only** discrepancies + the total (Property 5).

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

    Pagination:
      * ``limit=None`` means "no pagination" — every matching confirmed row is
        returned (used by the CSV export so the download stays complete).
      * a positive ``limit`` is capped at :data:`MAX_PAGE_LIMIT`; ``offset``
        defaults to 0. Ordering is stable (``part_number, lot_number,
        field_name, id``) so paging is deterministic.

    Returns a ``(rows, total_count)`` tuple where ``total_count`` is the number
    of matching confirmed discrepancies across ALL pages (after the ``source``
    filter), so callers can render paging controls. This is the clean helper the
    report service (task 6.1) calls so confirmed-only filtering lives in one
    place.
    """
    where, params = _confirmed_where(part_number, lot_number, field_name, provenance)
    db = await get_db()

    order_by = "ORDER BY part_number ASC, lot_number ASC, field_name ASC, id ASC"

    if source is not None:
        # The `source` filter inspects the JSON-in-TEXT `values` dict, which SQL
        # can't easily query, so we must materialise all matching rows, filter in
        # Python for the true total, then slice the requested page. This path is
        # only taken when a source filter is supplied.
        cursor = await db.execute(
            f"""SELECT id, group_id, part_number, lot_number, field_name,
                       field_type, "values", provenance, review_state
                  FROM sc_discrepancies
                 WHERE {where}
                 {order_by}""",
            tuple(params),
        )
        rows = await cursor.fetchall()
        filtered = [
            d for d in (_row_to_discrepancy(r) for r in rows) if source in d.values
        ]
        total_count = len(filtered)
        if limit is None:
            return filtered, total_count
        page_offset = _clamp_offset(offset)
        page_limit = _clamp_limit(limit)
        return filtered[page_offset : page_offset + page_limit], total_count

    # No source filter — count + page entirely in SQL (efficient at scale).
    count_cursor = await db.execute(
        f"SELECT COUNT(*) FROM sc_discrepancies WHERE {where}", tuple(params)
    )
    count_row = await count_cursor.fetchone()
    try:
        total_count = int(count_row[0]) if count_row is not None else 0
    except (TypeError, KeyError, IndexError):
        total_count = 0

    base_select = (
        f"""SELECT id, group_id, part_number, lot_number, field_name, field_type,
                   "values", provenance, review_state
              FROM sc_discrepancies
             WHERE {where}
             {order_by}"""
    )
    if limit is None:
        cursor = await db.execute(base_select, tuple(params))
    else:
        page_limit = _clamp_limit(limit)
        page_offset = _clamp_offset(offset)
        cursor = await db.execute(
            base_select + " LIMIT ? OFFSET ?",
            tuple(params) + (page_limit, page_offset),
        )
    rows = await cursor.fetchall()
    return [_row_to_discrepancy(r) for r in rows], total_count
