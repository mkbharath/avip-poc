"""Unit/integration tests for source-comparison ingestion (task 2.3).

Exercises the ingestion path through the FastAPI ``TestClient`` end to end
(router -> ``ingestion.ingest_payload`` -> ``sc_source_records`` /
``sc_rejected_records`` + the in-process ingest queue):

  * a VALID record POST to ``/api/v1/source-comparison/ingest`` returns ``202``,
    is persisted in ``sc_source_records``, and is enqueued on the ingest queue
    (Req 1.3, 1.4);
  * a MALFORMED record returns ``422`` whose body names the source + record id,
    and a row is written to ``sc_rejected_records`` — never dropped, never
    enqueued (Req 1.6, 1.7).

Follows the conventions in ``test_sc_pagination_and_simulator.py``: a temp
``AVIP_DATA_DIR`` with the simulator disabled (``AVIP_SC_SIMULATOR=false``),
settings paths rebound after import, the DB initialised via the app lifespan,
and the DB closed in teardown so the process exits cleanly.

The background worker started by the app lifespan drains the ingest queue in the
app's own event loop, which would race the "is it enqueued?" assertion. To keep
that assertion deterministic the fixture STOPS the worker immediately after
startup (and clears any residual queue items) so nothing consumes what
``ingest`` enqueues. Both the DB and the ``asyncio.Queue`` are bound to the
app's lifespan event loop, so every async helper here is run **on that loop**
via ``client.portal.call(...)`` rather than a separate loop. The LLM provider is
never reached on the ingestion path, so no mock is needed here.

_Requirements: 1.3, 1.4, 1.6, 1.7_
"""

import asyncio

import pytest


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient on a temp data dir, simulator off, worker stopped.

    The worker is stopped right after the lifespan starts it so the shared
    ingest queue is not drained during the test; any item the lifespan/worker
    left behind is cleared so ``qsize()`` starts at 0. All worker/queue/DB
    interaction runs on the app's event loop via the client's blocking portal.
    """
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    # Import inside the fixture so settings pick up the patched env, then rebind
    # the module-level settings paths (settings is instantiated at import time).
    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"

    from app.db import database
    from app.db.database import init_db
    from app.services import ingestion
    from app.services.ingestion import get_ingest_queue

    # The ingest queue is a module-level singleton shared across TestClient
    # instances, but each TestClient runs its lifespan on its OWN event loop.
    # Reset it to None so a fresh queue is lazily bound to THIS lifespan's loop;
    # otherwise the new worker would drain a queue bound to a prior test's
    # (now-closed) loop and could process a record leaked from that test —
    # spuriously persisting a source row here.
    ingestion._ingest_queue = None

    from fastapi.testclient import TestClient

    from app.main import app

    async def _quiesce():
        # Stop the background worker so it does not consume queued records, then
        # start each test from clean, isolated state ON THE APP LOOP:
        #   * drain any residual queue items so qsize() starts at 0;
        #   * clear the ingestion tables so counts are exact even if a prior
        #     test left rows behind via the shared DB connection singleton.
        # Everything here runs on the app's lifespan loop (via the portal), so
        # the DB connection and the asyncio.Queue are touched on their own loop
        # — no cross-loop access and no orphaned connection/thread.
        worker = getattr(app.state, "sc_worker", None)
        if worker is not None:
            await worker.stop()

        q = get_ingest_queue()
        while not q.empty():
            try:
                q.get_nowait()
                q.task_done()
            except asyncio.QueueEmpty:
                break

        # Force a fresh DB connection bound to THIS test's temp db_path. A prior
        # test may have left the module-level connection singleton open against
        # its own temp DB; closing it here (on the app loop, so the aiosqlite
        # thread joins cleanly) and re-initialising guarantees the schema exists
        # at our path and that reads/writes below all hit the same fresh DB.
        await database.close_db()
        await init_db()
        db = await database.get_db()
        await db.execute("DELETE FROM sc_source_records")
        await db.execute("DELETE FROM sc_rejected_records")
        await db.commit()

    with TestClient(app) as c:
        c.portal.call(_quiesce)
        yield c
        # Teardown: close the DB on the app's loop so the process exits cleanly.
        c.portal.call(database.close_db)


def _valid_record() -> dict:
    """A schema-valid ingest payload with the required common-key fields."""
    return {
        "source": "LAIR",
        "external_record_id": "LAIR-0001",
        "part_number": "PN-100",
        "lot_number": "LOT-1",
        "serial_number": "SN-1",
        "fields": {"diameter": 10.0, "material_grade": "A2"},
    }


async def _fetch_source_records() -> list:
    from app.db.database import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, source, external_record_id, part_number, lot_number, "
        "serial_number, fields, group_id FROM sc_source_records"
    )
    return await cursor.fetchall()


async def _fetch_rejected_records() -> list:
    from app.db.database import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT id, source, external_record_id, raw_payload, reason "
        "FROM sc_rejected_records"
    )
    return await cursor.fetchall()


async def _queue_size() -> int:
    from app.services.ingestion import get_ingest_queue

    return get_ingest_queue().qsize()


async def _drain_one():
    from app.services.ingestion import get_ingest_queue

    q = get_ingest_queue()
    item = q.get_nowait()
    q.task_done()
    return item


def test_valid_record_accepted_persisted_and_enqueued(client):
    """A valid record -> 202, persisted in sc_source_records, and enqueued.

    Verifies Req 1.3 (202 on accept), Req 1.4 (persisted), and Req 1.5's enqueue
    contract (the persisted SourceRecord is put on the ingest queue).
    """
    payload = _valid_record()
    resp = client.post("/api/v1/source-comparison/ingest", json=payload)

    # 202 accepted, echoing the new record id + external id + source.
    assert resp.status_code == 202
    body = resp.json()
    assert body["accepted"] is True
    assert body["external_record_id"] == payload["external_record_id"]
    assert body["source"] == payload["source"]
    new_id = body["record_id"]
    assert isinstance(new_id, str) and new_id

    # Persisted exactly once in sc_source_records with the expected columns.
    rows = client.portal.call(_fetch_source_records)
    assert len(rows) == 1
    row = rows[0]
    assert row["id"] == new_id
    assert row["source"] == "LAIR"
    assert row["external_record_id"] == "LAIR-0001"
    assert row["part_number"] == "PN-100"
    assert row["lot_number"] == "LOT-1"
    assert row["group_id"] is None  # worker attaches the group later

    # Enqueued on the shared ingest queue (worker is stopped, so it stays there).
    assert client.portal.call(_queue_size) == 1
    enqueued = client.portal.call(_drain_one)
    assert enqueued.id == new_id
    assert enqueued.external_record_id == "LAIR-0001"

    # A valid record is never rejected.
    assert client.portal.call(_fetch_rejected_records) == []


def test_malformed_record_rejected_with_detail_and_persisted(client):
    """A malformed record -> 422 naming source + record id, retained, not enqueued.

    The payload names its source + external record id but omits the required
    common-key field ``lot_number`` so it fails validation. We assert the 422
    body carries the identifying detail and that a row lands in
    sc_rejected_records (Req 1.6, 1.7).
    """
    # Missing required "lot_number" -> Pydantic validation fails, but the raw
    # payload still names the source + external record id for the 422 body.
    malformed = {
        "source": "FAIR",
        "external_record_id": "FAIR-9999",
        "part_number": "PN-200",
        # lot_number intentionally omitted
        "fields": {"diameter": 12.0},
    }

    resp = client.post("/api/v1/source-comparison/ingest", json=malformed)

    # 422 with a body naming the source + record id + a reason.
    assert resp.status_code == 422
    body = resp.json()
    assert body["source"] == "FAIR"
    assert body["record_id"] == "FAIR-9999"
    assert isinstance(body["reason"], str) and body["reason"]

    # Retained in sc_rejected_records (never dropped) with source + record id.
    rejected = client.portal.call(_fetch_rejected_records)
    assert len(rejected) == 1
    rrow = rejected[0]
    assert rrow["source"] == "FAIR"
    assert rrow["external_record_id"] == "FAIR-9999"
    assert rrow["reason"]

    # Nothing accepted, nothing enqueued.
    assert client.portal.call(_fetch_source_records) == []
    assert client.portal.call(_queue_size) == 0

    # And the retained rejection is visible via the rejected-records endpoint.
    listed = client.get("/api/v1/source-comparison/rejected").json()
    assert listed["total_count"] == 1
    assert listed["data"][0]["source"] == "FAIR"
    assert listed["data"][0]["external_record_id"] == "FAIR-9999"


def test_incomplete_common_key_record_rejected(client):
    """A record with a blank common-key value is rejected and retained.

    Structurally valid as an IngestRecord (all required fields present) but with
    a whitespace-only ``lot_number`` — the ingestion service's common-key check
    rejects it, names the source + record id, and persists the rejection
    (Req 1.6, 1.7).
    """
    payload = {
        "source": "SHQ",
        "external_record_id": "SHQ-42",
        "part_number": "PN-300",
        "lot_number": "   ",  # whitespace-only -> not a usable common key
        "fields": {"diameter": 11.0},
    }

    resp = client.post("/api/v1/source-comparison/ingest", json=payload)

    assert resp.status_code == 422
    body = resp.json()
    assert body["source"] == "SHQ"
    assert body["record_id"] == "SHQ-42"
    assert "lot_number" in body["reason"]

    rejected = client.portal.call(_fetch_rejected_records)
    assert len(rejected) == 1
    assert rejected[0]["source"] == "SHQ"
    assert rejected[0]["external_record_id"] == "SHQ-42"

    assert client.portal.call(_fetch_source_records) == []
    assert client.portal.call(_queue_size) == 0
