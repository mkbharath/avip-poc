"""Streaming alignment service for the source-comparison feature (LAIR / FAIR / SHQ).

The background worker (task 7.2) drains the ingest queue and hands each persisted
``SourceRecord`` to :func:`align_record`. This service reconciles records into
``sc_aligned_groups`` rows by their **common key** (read from configuration —
``part_number`` + ``lot_number`` by default, Req 8.3) as they stream in:

  * **Find-or-create** the group row for a record's common key, respecting the
    ``UNIQUE (part_number, lot_number)`` constraint and tolerating a concurrent
    create (two records for the same key racing) by re-reading after a unique
    violation (Req 2.1).
  * **Attach** the record: set ``sc_source_records.group_id`` to the group id.
  * **Recompute** ``present_sources`` (the JSON list of *distinct* sources whose
    records are attached to the group) and ``alignment_state``:
    ``"complete"`` when all three sources (LAIR, FAIR, SHQ) are present, else
    ``"partial"`` (Req 2.2, 2.4). ``updated_at`` is bumped on every change.
  * **Late arrivals** re-evaluate an existing partial group: attaching a new
    record recomputes present-sources + state, retaining every earlier record
    (Req 2.2, 2.3, 2.4, Property 10).
  * **Idempotency**: attaching the same source-record id twice does NOT
    double-count. ``present_sources`` is always derived from the *distinct*
    sources currently attached, so re-running yields the same group state
    (Req 2.1-2.4, Property 9).
  * **Unmatched**: a record with no derivable common key (blank/whitespace
    part or lot — ingestion largely guards this, but alignment is defensive)
    is attached to a per-record ``unmatched`` group and retained rather than
    dropped (Req 2.5).

Read helpers :func:`get_group` and :func:`list_groups` are provided for the
group endpoints (task 3.2); no HTTP routes are added here.

Structured logs are emitted for group creation, attachment, and state changes
(Req 9.4).
"""

import json
import logging
import uuid
from datetime import datetime, timezone

import aiosqlite

from app.db.database import get_db
from app.models.source_comparison import (
    AlignedGroup,
    AlignmentState,
    SourceRecord,
    SourceType,
)
from app.services.sc_config import ComparisonConfig, comparison_config

logger = logging.getLogger("app.source_comparison.alignment")

# The three sources that must all be present for a group to be "complete".
ALL_SOURCES: tuple[str, ...] = tuple(s.value for s in SourceType)


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _derive_common_key(
    record: SourceRecord, config: ComparisonConfig
) -> tuple[str, ...] | None:
    """Derive the common-key tuple for a record from configuration (Req 8.3).

    Returns the ordered tuple of common-key field values, or ``None`` if any
    configured key field is missing or blank/whitespace — signalling the record
    cannot be aligned and must be treated as unmatched (Req 2.5).
    """
    values: list[str] = []
    for key in config.common_key:
        value = getattr(record, key, None)
        if not isinstance(value, str) or not value.strip():
            return None
        values.append(value)
    return tuple(values)


def _row_to_group(row: aiosqlite.Row, records: list[SourceRecord]) -> AlignedGroup:
    """Build an :class:`AlignedGroup` from a ``sc_aligned_groups`` row + records."""
    present = [SourceType(s) for s in json.loads(row["present_sources"])]
    return AlignedGroup(
        id=row["id"],
        part_number=row["part_number"],
        lot_number=row["lot_number"],
        present_sources=present,
        alignment_state=AlignmentState(row["alignment_state"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
        records=records,
    )


async def _fetch_group_records(
    db: aiosqlite.Connection, group_id: str
) -> list[SourceRecord]:
    """Fetch all source records attached to a group, ordered by arrival."""
    cursor = await db.execute(
        """SELECT id, source, external_record_id, part_number, lot_number,
                  serial_number, fields, group_id, received_at
             FROM sc_source_records
            WHERE group_id = ?
            ORDER BY received_at ASC, id ASC""",
        (group_id,),
    )
    rows = await cursor.fetchall()
    records: list[SourceRecord] = []
    for r in rows:
        records.append(
            SourceRecord(
                id=r["id"],
                source=SourceType(r["source"]),
                external_record_id=r["external_record_id"],
                part_number=r["part_number"],
                lot_number=r["lot_number"],
                serial_number=r["serial_number"],
                fields=json.loads(r["fields"]) if r["fields"] else {},
                group_id=r["group_id"],
                received_at=r["received_at"],
            )
        )
    return records


def _compute_state(present_sources: list[str]) -> AlignmentState:
    """Recompute alignment state from the distinct present sources (Req 2.2, 2.4).

    ``complete`` iff all three sources (LAIR, FAIR, SHQ) are present; otherwise
    ``partial``. Unmatched groups are handled separately and never pass through
    here.
    """
    if all(s in present_sources for s in ALL_SOURCES):
        return AlignmentState.COMPLETE
    return AlignmentState.PARTIAL


async def _find_or_create_group(
    db: aiosqlite.Connection, part_number: str, lot_number: str
) -> str:
    """Find or create the ``sc_aligned_groups`` row for a common key (Req 2.1).

    Respects ``UNIQUE (part_number, lot_number)`` and tolerates a concurrent
    create: if a unique violation occurs between the existence check and the
    insert (two records for the same key racing), the existing row is re-read
    and its id returned. Returns the group id.
    """
    cursor = await db.execute(
        "SELECT id FROM sc_aligned_groups WHERE part_number = ? AND lot_number = ?",
        (part_number, lot_number),
    )
    row = await cursor.fetchone()
    if row is not None:
        return row["id"]

    group_id = str(uuid.uuid4())
    now = _now_iso()
    try:
        await db.execute(
            """INSERT INTO sc_aligned_groups
                   (id, part_number, lot_number, present_sources, alignment_state,
                    created_at, updated_at)
               VALUES (?, ?, ?, '[]', ?, ?, ?)""",
            (group_id, part_number, lot_number, AlignmentState.PARTIAL.value, now, now),
        )
        await db.commit()
        logger.info(
            "Created aligned group: id=%s part_number=%s lot_number=%s",
            group_id,
            part_number,
            lot_number,
        )
        return group_id
    except aiosqlite.IntegrityError:
        # Concurrent create raced us to the UNIQUE(part_number, lot_number) row.
        await db.rollback()
        cursor = await db.execute(
            "SELECT id FROM sc_aligned_groups WHERE part_number = ? AND lot_number = ?",
            (part_number, lot_number),
        )
        row = await cursor.fetchone()
        if row is None:
            # Should not happen: the violation implies a row exists. Re-raise.
            raise
        logger.info(
            "Reused concurrently-created aligned group: id=%s part_number=%s lot_number=%s",
            row["id"],
            part_number,
            lot_number,
        )
        return row["id"]


async def _create_unmatched_group(
    db: aiosqlite.Connection, record: SourceRecord
) -> str:
    """Create a per-record ``unmatched`` group for a record with no common key.

    The record is retained (attached to this group) rather than dropped
    (Req 2.5). Each unmatched record gets its own group to avoid colliding on
    the ``UNIQUE (part_number, lot_number)`` constraint when keys are blank.
    """
    group_id = str(uuid.uuid4())
    now = _now_iso()
    # Use a unique synthetic key so blank/duplicate unmatched records don't
    # collide on UNIQUE(part_number, lot_number).
    synthetic_key = f"__unmatched__:{group_id}"
    await db.execute(
        """INSERT INTO sc_aligned_groups
               (id, part_number, lot_number, present_sources, alignment_state,
                created_at, updated_at)
           VALUES (?, ?, ?, '[]', ?, ?, ?)""",
        (group_id, synthetic_key, synthetic_key, AlignmentState.UNMATCHED.value, now, now),
    )
    await db.commit()
    logger.warning(
        "Created unmatched group for record with no derivable common key: "
        "group_id=%s record_id=%s source=%s",
        group_id,
        record.id,
        record.source.value,
    )
    return group_id


async def _attach_and_recompute(
    db: aiosqlite.Connection, group_id: str, record: SourceRecord
) -> AlignedGroup:
    """Attach ``record`` to ``group_id`` and recompute present-sources + state.

    Idempotent: present-sources is derived from the *distinct* sources of the
    records actually attached to the group, so re-attaching the same record id
    never double-counts (Property 9). ``updated_at`` is bumped whenever the
    stored present-sources or state changes.
    """
    # Attach the record (set its group_id). Idempotent for the same record id.
    await db.execute(
        "UPDATE sc_source_records SET group_id = ? WHERE id = ?",
        (group_id, record.id),
    )

    # Recompute present-sources from the distinct sources actually attached.
    records = await _fetch_group_records(db, group_id)
    distinct_present = sorted({r.source.value for r in records})
    new_state = _compute_state(distinct_present)

    cursor = await db.execute(
        "SELECT present_sources, alignment_state FROM sc_aligned_groups WHERE id = ?",
        (group_id,),
    )
    current = await cursor.fetchone()
    old_present = sorted(json.loads(current["present_sources"])) if current else []
    old_state = current["alignment_state"] if current else None

    changed = old_present != distinct_present or old_state != new_state.value
    now = _now_iso()
    if changed:
        await db.execute(
            """UPDATE sc_aligned_groups
                  SET present_sources = ?, alignment_state = ?, updated_at = ?
                WHERE id = ?""",
            (json.dumps(distinct_present), new_state.value, now, group_id),
        )
        logger.info(
            "Group state updated: group_id=%s present_sources=%s state=%s "
            "(attached record_id=%s source=%s)",
            group_id,
            distinct_present,
            new_state.value,
            record.id,
            record.source.value,
        )
    else:
        logger.info(
            "Group unchanged (idempotent attach): group_id=%s present_sources=%s "
            "state=%s (record_id=%s source=%s)",
            group_id,
            distinct_present,
            new_state.value,
            record.id,
            record.source.value,
        )
    await db.commit()

    cursor = await db.execute(
        """SELECT id, part_number, lot_number, present_sources, alignment_state,
                  created_at, updated_at
             FROM sc_aligned_groups WHERE id = ?""",
        (group_id,),
    )
    group_row = await cursor.fetchone()
    return _row_to_group(group_row, records)


async def align_record(
    record: SourceRecord,
    *,
    config: ComparisonConfig | None = None,
) -> AlignedGroup:
    """Align a single persisted source record into its aligned group.

    Derives the common key from configuration (Req 8.3). If the key is
    derivable, finds-or-creates the ``sc_aligned_groups`` row for that key
    (respecting the UNIQUE constraint and tolerating concurrent create),
    attaches the record, and recomputes ``present_sources`` +
    ``alignment_state`` (``complete`` when LAIR+FAIR+SHQ all present, else
    ``partial``). Late arrivals re-evaluate an existing partial group; attaching
    the same record id twice is idempotent (Req 2.1-2.4).

    If no common key can be derived, the record is attached to a retained
    ``unmatched`` group rather than dropped (Req 2.5).

    Returns the updated :class:`AlignedGroup` including its attached records.
    ``config`` defaults to the module-level ``comparison_config`` and is
    injectable for testing.
    """
    cfg = config or comparison_config
    db = await get_db()

    key = _derive_common_key(record, cfg)
    if key is None:
        group_id = await _create_unmatched_group(db, record)
        await db.execute(
            "UPDATE sc_source_records SET group_id = ? WHERE id = ?",
            (group_id, record.id),
        )
        await db.commit()
        records = await _fetch_group_records(db, group_id)
        cursor = await db.execute(
            """SELECT id, part_number, lot_number, present_sources, alignment_state,
                      created_at, updated_at
                 FROM sc_aligned_groups WHERE id = ?""",
            (group_id,),
        )
        group_row = await cursor.fetchone()
        return _row_to_group(group_row, records)

    group_id = await _find_or_create_group(db, record.part_number, record.lot_number)
    return await _attach_and_recompute(db, group_id, record)


# ── Read helpers for the group endpoints (task 3.2) — no HTTP routes here ─────


async def get_group(group_id: str) -> AlignedGroup | None:
    """Return one aligned group with its attached records, or ``None``.

    Used by ``GET /source-comparison/groups/{id}`` (task 3.2).
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, part_number, lot_number, present_sources, alignment_state,
                  created_at, updated_at
             FROM sc_aligned_groups WHERE id = ?""",
        (group_id,),
    )
    row = await cursor.fetchone()
    if row is None:
        return None
    records = await _fetch_group_records(db, group_id)
    return _row_to_group(row, records)


async def list_groups(
    *,
    part_number: str | None = None,
    lot_number: str | None = None,
    state: str | None = None,
) -> list[AlignedGroup]:
    """List aligned groups, optionally filtered by part, lot, and state.

    Used by ``GET /source-comparison/groups`` (task 3.2). Each returned group
    includes its attached records. Filters are ANDed; omitted filters match all.
    """
    clauses: list[str] = []
    params: list[str] = []
    if part_number is not None:
        clauses.append("part_number = ?")
        params.append(part_number)
    if lot_number is not None:
        clauses.append("lot_number = ?")
        params.append(lot_number)
    if state is not None:
        clauses.append("alignment_state = ?")
        params.append(state)
    where = f" WHERE {' AND '.join(clauses)}" if clauses else ""

    db = await get_db()
    cursor = await db.execute(
        f"""SELECT id, part_number, lot_number, present_sources, alignment_state,
                   created_at, updated_at
              FROM sc_aligned_groups{where}
             ORDER BY updated_at DESC, id ASC""",
        tuple(params),
    )
    rows = await cursor.fetchall()
    groups: list[AlignedGroup] = []
    for row in rows:
        records = await _fetch_group_records(db, row["id"])
        groups.append(_row_to_group(row, records))
    return groups
