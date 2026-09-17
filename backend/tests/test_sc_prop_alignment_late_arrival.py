"""Property test: late arrival completes without loss (task 3.5).

# Feature: avip-source-comparison, Property 10

**Property 10: Late arrival completes without loss.**

A partial group is formed from one or two sources; a later-arriving record for a
*new* source is then attached to the same common key. After the late arrival:

  * every earlier record is still retained (nothing dropped),
  * the new record is included in the group, and
  * present-sources / alignment_state are re-evaluated to reflect the union of
    all sources now present (complete iff all three present, else partial).

The test draws an initial non-empty proper subset of {LAIR, FAIR, SHQ} for the
early records and one late source not already present, aligns the early records
first, then attaches the late record, and asserts retention + re-evaluation.

Conventions follow ``tests/test_sc_pagination_and_simulator.py``: temp
``AVIP_DATA_DIR``, ``AVIP_SC_SIMULATOR=false``, rebind settings, init DB, close in
teardown.

_Requirements: 2.2, 2.3, 9.2_
_Properties: 10_
"""

import asyncio
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
    data_dir = tmp_path / f"data-{uuid.uuid4().hex}"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from app.db import database

    _run(database.close_db())
    _run(database.init_db())


async def _persist_and_align(source: str, part: str, lot: str, record_id: str):
    from app.db.database import get_db
    from app.models.source_comparison import SourceRecord, SourceType
    from app.services.alignment import align_record

    received_at = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    await db.execute(
        """INSERT INTO sc_source_records
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


@settings(max_examples=100, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(
    # Early sources: 1 or 2 distinct sources (a proper subset leaves room for a
    # late arrival of a genuinely new source).
    early=st.lists(st.sampled_from(SOURCES), min_size=1, max_size=2, unique=True),
    data=st.data(),
)
def test_late_arrival_completes_without_loss(
    tmp_path_factory, monkeypatch, early, data
):
    tmp_path = tmp_path_factory.mktemp("prop10")
    _fresh_db(tmp_path, monkeypatch)

    part, lot = "PART-10", "LOT-10"

    # A late source that is not already present in the early set.
    remaining = [s for s in SOURCES if s not in early]
    late = data.draw(st.sampled_from(remaining))

    from app.models.source_comparison import AlignmentState, SourceType

    # Align the early records -> a partial group.
    early_records = [(src, str(uuid.uuid4())) for src in early]
    group = None
    for src, rid in early_records:
        group = _run(_persist_and_align(src, part, lot, rid))
    assert group.alignment_state == AlignmentState.PARTIAL
    early_ids = {rid for _, rid in early_records}
    assert {r.id for r in group.records} == early_ids

    # A later-arriving record for a new source attaches to the same group.
    late_id = str(uuid.uuid4())
    after = _run(_persist_and_align(late, part, lot, late_id))

    from app.services.alignment import get_group

    final = _run(get_group(after.id))
    assert final is not None

    # Same group (same common key) — no new group spawned for the late arrival.
    assert final.id == group.id

    # Earlier records retained AND the new record included — nothing lost.
    final_ids = {r.id for r in final.records}
    assert early_ids <= final_ids
    assert late_id in final_ids
    assert final_ids == early_ids | {late_id}

    # State re-evaluated over the union of all present sources.
    expected_sources = {SourceType(s) for s in early} | {SourceType(late)}
    assert set(final.present_sources) == expected_sources
    expected_state = (
        AlignmentState.COMPLETE
        if len(expected_sources) == 3
        else AlignmentState.PARTIAL
    )
    assert final.alignment_state == expected_state
