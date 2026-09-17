# Feature: avip-source-comparison, Property 11
"""Property test for source-comparison ingestion (task 2.4).

**Property 11: Invalid records are rejected with identifying detail, never
dropped.**

For an arbitrary MALFORMED inbound record, ingestion must:
  * answer ``422`` with a body naming the source + record id (Req 1.6);
  * retain the record in ``sc_rejected_records`` with a reason that names the
    source + record id (Req 1.6, 1.7);
  * NOT persist it to ``sc_source_records`` and NOT enqueue it on the ingest
    queue — no invalid record is ever silently dropped OR treated as accepted
    (Req 1.7).

Uses Hypothesis (min 100 iterations via ``@settings(max_examples=100)``) to
generate a variety of malformed shapes: missing required common-key fields,
blank/whitespace-only common-key values, and a wrong-typed field. Each generated
payload deliberately carries a recoverable ``source`` and ``external_record_id``
so the "names source + record id" assertion is meaningful.

Follows ``test_sc_pagination_and_simulator.py`` conventions: a temp
``AVIP_DATA_DIR`` with the simulator disabled (``AVIP_SC_SIMULATOR=false``),
settings paths rebound after import, the DB initialised via the app lifespan,
and the DB closed in teardown. The background worker is stopped so it cannot
drain the ingest queue during the property run (making the "not enqueued"
assertion deterministic). The DB and the ``asyncio.Queue`` are bound to the
app's lifespan event loop, so every async helper runs **on that loop** via
``client.portal.call(...)``; the relevant ``sc_*`` tables and the queue are
reset before each generated example so per-example counts are exact. The LLM
provider is never reached on the ingestion (rejection) path, so no mock is
required.

_Requirements: 1.6, 1.7_
_Properties: 11_
"""

import asyncio

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient on a temp data dir, simulator off, worker stopped."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

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
    # (now-closed) loop and could process a record leaked from that test.
    ingestion._ingest_queue = None

    from fastapi.testclient import TestClient

    from app.main import app

    async def _quiesce():
        # Stop the worker so nothing drains the ingest queue during the property
        # run; drain any residual queue items and clear the ingestion tables so
        # the run starts from clean, isolated state. All of this runs on the
        # app's lifespan loop (via the portal), so the DB connection and the
        # asyncio.Queue are only ever touched on their own loop.
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

        # Force a fresh DB connection bound to THIS test's temp db_path (a prior
        # test may have left the singleton open against its own DB). Closing on
        # the app loop joins the aiosqlite thread cleanly; re-init guarantees the
        # schema exists at our path and that reads/writes hit the same DB.
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


async def _reset_state() -> None:
    """Clear the ingestion tables and the ingest queue before each example."""
    from app.db.database import get_db
    from app.services.ingestion import get_ingest_queue

    db = await get_db()
    await db.execute("DELETE FROM sc_source_records")
    await db.execute("DELETE FROM sc_rejected_records")
    await db.commit()

    q = get_ingest_queue()
    while not q.empty():
        try:
            q.get_nowait()
            q.task_done()
        except asyncio.QueueEmpty:
            break


async def _counts() -> tuple[int, int]:
    """Return (source_records_count, rejected_records_count)."""
    from app.db.database import get_db

    db = await get_db()
    src = await (await db.execute("SELECT COUNT(*) FROM sc_source_records")).fetchone()
    rej = await (await db.execute("SELECT COUNT(*) FROM sc_rejected_records")).fetchone()
    return int(src[0]), int(rej[0])


async def _first_rejected() -> dict:
    from app.db.database import get_db

    db = await get_db()
    cursor = await db.execute(
        "SELECT source, external_record_id, reason FROM sc_rejected_records"
    )
    row = await cursor.fetchone()
    return {
        "source": row["source"],
        "external_record_id": row["external_record_id"],
        "reason": row["reason"],
    }


async def _queue_size() -> int:
    from app.services.ingestion import get_ingest_queue

    return get_ingest_queue().qsize()


# ── Strategy: malformed ingest payloads that still name a source + record id ──
#
# Each payload is invalid in exactly one of several ways, but always carries a
# recoverable ``source`` (a valid enum string) and ``external_record_id`` so the
# "reason names source + record id" assertion is testable. The invalidity kinds:
#   * missing "lot_number" (required common-key field absent)
#   * missing "part_number"
#   * blank/whitespace-only "lot_number" (present but unusable common key)
#   * "part_number" of the wrong type (int, not str) -> schema validation fails

_VALID_SOURCES = ["LAIR", "FAIR", "SHQ"]

_ids = st.text(
    alphabet=st.characters(min_codepoint=48, max_codepoint=90),
    min_size=1,
    max_size=12,
)
_whitespace = st.sampled_from(["", " ", "   ", "\t", "\n  "])


def _make_payload(source, ext_id, kind, ws, bad_part):
    """Build one malformed payload of the given ``kind``."""
    base = {
        "source": source,
        "external_record_id": ext_id,
        "part_number": "PN-1",
        "lot_number": "LOT-1",
        "fields": {"diameter": 10.0},
    }
    if kind == "missing_lot":
        base.pop("lot_number")
    elif kind == "missing_part":
        base.pop("part_number")
    elif kind == "blank_lot":
        base["lot_number"] = ws
    elif kind == "wrong_type_part":
        base["part_number"] = bad_part  # int instead of str
    return base


_malformed = st.builds(
    _make_payload,
    source=st.sampled_from(_VALID_SOURCES),
    ext_id=_ids,
    kind=st.sampled_from(
        ["missing_lot", "missing_part", "blank_lot", "wrong_type_part"]
    ),
    ws=_whitespace,
    bad_part=st.integers(),
)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(payload=_malformed)
def test_invalid_records_rejected_with_detail_never_dropped(client, payload):
    """Every malformed record -> 422 naming source+id, retained, never enqueued."""
    client.portal.call(_reset_state)

    resp = client.post("/api/v1/source-comparison/ingest", json=payload)

    # Rejected with identifying detail (Req 1.6).
    assert resp.status_code == 422
    body = resp.json()
    assert body["source"] == payload["source"]
    assert body["record_id"] == payload["external_record_id"]
    assert isinstance(body["reason"], str) and body["reason"]

    # Retained in rejected-records with a reason naming source + record id
    # (never dropped, Req 1.7).
    src_count, rej_count = client.portal.call(_counts)
    assert rej_count == 1
    rejected = client.portal.call(_first_rejected)
    assert rejected["source"] == payload["source"]
    assert rejected["external_record_id"] == payload["external_record_id"]
    assert rejected["reason"]

    # Never accepted and never enqueued.
    assert src_count == 0
    assert client.portal.call(_queue_size) == 0
