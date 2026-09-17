"""Unit tests for the streaming alignment service (task 3.3).

Covers the alignment edge cases from ``backend/app/services/alignment.py`` via
``align_record``:

  * single-source group -> ``partial`` with one present source
  * two-source partial group -> ``partial`` with both present sources
  * full three-source group (LAIR + FAIR + SHQ) -> ``complete``
  * a record with no derivable common key -> ``unmatched`` (retained, not dropped)

The alignment service persists group state to ``sc_aligned_groups`` and attaches
records via ``sc_source_records.group_id``; a record row must already exist
before ``align_record`` is called (it sets ``group_id`` with an ``UPDATE``), so a
small helper persists each record first, mirroring what the ingestion service
does in production.

Conventions follow ``tests/test_sc_pagination_and_simulator.py``: a temp
``AVIP_DATA_DIR`` with ``AVIP_SC_SIMULATOR=false``, rebind the module-level
settings paths, initialise the DB, and close it in teardown so the process
exits cleanly.

_Requirements: 2.1, 2.2, 2.4, 2.5_
"""

import asyncio
import json
import uuid
from datetime import datetime, timezone

import pytest


def _run(coro):
    """Run an async coroutine from a sync test, reusing/creating a loop."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    return loop.run_until_complete(coro)


@pytest.fixture()
def db_env(tmp_path, monkeypatch):
    """Temp data dir + initialised DB with the simulator disabled."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"
    data_dir.mkdir(parents=True, exist_ok=True)

    from app.db import database

    _run(database.init_db())

    yield

    async def _close():
        await database.close_db()

    _run(_close())


async def _persist_and_align(
    source: str,
    part_number: str,
    lot_number: str,
    *,
    fields: dict | None = None,
    serial_number: str | None = None,
    record_id: str | None = None,
):
    """Persist a source record, then align it — returns the updated group.

    Mirrors the ingestion -> worker path: the row must exist in
    ``sc_source_records`` before ``align_record`` attaches it.
    """
    from app.db.database import get_db
    from app.models.source_comparison import SourceRecord, SourceType
    from app.services.alignment import align_record

    rid = record_id or str(uuid.uuid4())
    received_at = datetime.now(timezone.utc).isoformat()
    db = await get_db()
    await db.execute(
        """INSERT INTO sc_source_records
               (id, source, external_record_id, part_number, lot_number,
                serial_number, fields, group_id, received_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
        (
            rid,
            source,
            f"ext-{rid}",
            part_number,
            lot_number,
            serial_number,
            json.dumps(fields or {}),
            received_at,
        ),
    )
    await db.commit()

    record = SourceRecord(
        id=rid,
        source=SourceType(source),
        external_record_id=f"ext-{rid}",
        part_number=part_number,
        lot_number=lot_number,
        serial_number=serial_number,
        fields=fields or {},
        group_id=None,
        received_at=received_at,
    )
    return await align_record(record)


def test_single_source_group_is_partial(db_env):
    """A lone source record forms a partial group with just that source."""
    group = _run(_persist_and_align("LAIR", "PART-A", "LOT-1"))

    from app.models.source_comparison import AlignmentState, SourceType

    assert group.alignment_state == AlignmentState.PARTIAL
    assert group.present_sources == [SourceType.LAIR]
    assert group.part_number == "PART-A"
    assert group.lot_number == "LOT-1"
    assert len(group.records) == 1
    assert group.records[0].source == SourceType.LAIR


def test_two_source_partial_group(db_env):
    """Two of three sources for the same key -> partial with both present."""
    _run(_persist_and_align("LAIR", "PART-B", "LOT-2"))
    group = _run(_persist_and_align("FAIR", "PART-B", "LOT-2"))

    from app.models.source_comparison import AlignmentState, SourceType

    assert group.alignment_state == AlignmentState.PARTIAL
    assert set(group.present_sources) == {SourceType.LAIR, SourceType.FAIR}
    assert len(group.records) == 2
    assert {r.source for r in group.records} == {SourceType.LAIR, SourceType.FAIR}


def test_full_three_source_group_is_complete(db_env):
    """All three sources (LAIR + FAIR + SHQ) present -> complete."""
    _run(_persist_and_align("LAIR", "PART-C", "LOT-3"))
    _run(_persist_and_align("FAIR", "PART-C", "LOT-3"))
    group = _run(_persist_and_align("SHQ", "PART-C", "LOT-3"))

    from app.models.source_comparison import AlignmentState, SourceType

    assert group.alignment_state == AlignmentState.COMPLETE
    assert set(group.present_sources) == {
        SourceType.LAIR,
        SourceType.FAIR,
        SourceType.SHQ,
    }
    assert len(group.records) == 3


def test_unmatched_key_record_is_retained(db_env):
    """A record with a blank common-key field is marked unmatched, not dropped."""
    # A blank lot_number yields no derivable common key.
    group = _run(_persist_and_align("SHQ", "PART-D", "   "))

    from app.models.source_comparison import AlignmentState

    assert group.alignment_state == AlignmentState.UNMATCHED
    assert len(group.records) == 1

    # The record is retained: it is attached to the unmatched group and readable.
    from app.services.alignment import get_group

    fetched = _run(get_group(group.id))
    assert fetched is not None
    assert fetched.alignment_state == AlignmentState.UNMATCHED
    assert len(fetched.records) == 1
