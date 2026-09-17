"""Property test: alignment is idempotent and order-independent (task 3.4).

# Feature: avip-source-comparison, Property 9

**Property 9: Alignment is idempotent and order-independent (streaming).**

For a single common key, records may be delivered by the streaming worker in any
order and the same record may be re-delivered (duplicate). Regardless of delivery
order or duplication:

  * each *distinct* source record appears exactly once in the group, and
  * the group's present-sources and alignment_state are order-independent —
    they depend only on the set of distinct sources present, not on the order or
    number of deliveries.

The test generates a set of distinct records for one key (subset of LAIR/FAIR/SHQ,
each source at most once so present-sources is well-defined), builds a shuffled
delivery schedule that re-delivers each record one-or-more times, aligns them in
that order, and asserts the resulting group is exactly what the distinct set
implies.

Conventions follow ``tests/test_sc_pagination_and_simulator.py``: temp
``AVIP_DATA_DIR``, ``AVIP_SC_SIMULATOR=false``, rebind settings, init DB, close in
teardown.

_Requirements: 2.1, 2.2, 2.3, 2.4_
_Properties: 9_
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

SOURCES = ["LAIR", "FAIR", "SHQ"]


def _run(coro):
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


def _fresh_db(tmp_path, monkeypatch):
    """Point settings at a fresh temp DB and initialise it."""
    data_dir = tmp_path / f"data-{uuid.uuid4().hex}"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from app.db import database

    _run(database.close_db())  # drop any prior connection so db_path is re-read
    _run(database.init_db())


async def _persist_and_align(source: str, part: str, lot: str, record_id: str):
    from app.db.database import get_db
    from app.models.source_comparison import SourceRecord, SourceType
    from app.services.alignment import align_record

    received_at = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    # Idempotent persist: re-delivery of the same record id is a no-op insert.
    await db.execute(
        """INSERT OR IGNORE INTO sc_source_records
               (id, source, external_record_id, part_number, lot_number,
                serial_number, fields, group_id, received_at)
           VALUES (?, ?, ?, ?, ?, NULL, '{}', NULL, ?)""",
        (record_id, source, f"ext-{record_id}", part, lot, received_at),
    )
    await db.commit()

    record = SourceRecord(
        id=record_id,
        source=SourceType(source),
        external_record_id=f"ext-{record_id}",
        part_number=part,
        lot_number=lot,
        received_at=received_at,
    )
    return await align_record(record)


# Distinct sources for one key (at most one record per source), plus a
# re-delivery count per record; Hypothesis shuffles the flattened schedule.
@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    present=st.lists(st.sampled_from(SOURCES), min_size=1, max_size=3, unique=True),
    dupes=st.lists(st.integers(min_value=1, max_value=3), min_size=3, max_size=3),
    data=st.data(),
)
def test_alignment_idempotent_and_order_independent(
    tmp_path_factory, monkeypatch, present, dupes, data
):
    tmp_path = tmp_path_factory.mktemp("prop9")
    _fresh_db(tmp_path, monkeypatch)

    part, lot = "PART-9", "LOT-9"

    # One distinct record per present source; deliver each 1..3 times.
    records = [(src, str(uuid.uuid4())) for src in present]
    schedule: list[tuple[str, str]] = []
    for i, (src, rid) in enumerate(records):
        schedule.extend([(src, rid)] * dupes[i])
    schedule = data.draw(st.permutations(schedule))

    group = None
    for src, rid in schedule:
        group = _run(_persist_and_align(src, part, lot, rid))

    from app.models.source_comparison import AlignmentState, SourceType
    from app.services.alignment import get_group

    final = _run(get_group(group.id))
    assert final is not None

    # Each distinct record appears exactly once (no double-counting on re-delivery).
    seen_ids = [r.id for r in final.records]
    assert sorted(seen_ids) == sorted(rid for _, rid in records)
    assert len(seen_ids) == len(set(seen_ids))

    # Present-sources depends only on the distinct set of sources — order-independent.
    expected_sources = {SourceType(s) for s in present}
    assert set(final.present_sources) == expected_sources

    # State is complete iff all three sources present, else partial.
    expected_state = (
        AlignmentState.COMPLETE if len(present) == 3 else AlignmentState.PARTIAL
    )
    assert final.alignment_state == expected_state
