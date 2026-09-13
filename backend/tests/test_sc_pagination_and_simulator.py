"""Bounded verification for source-comparison pagination + simulator control.

Covers the two changes made server-side to fix the review list hanging the
frontend and to make ingestion controllable from the app:

  * PART A — pagination: ``/review/queue`` and ``/report`` return a single page
    plus the full ``total_count``; ``/report/export`` stays complete (all rows).
  * PART B — simulator control: ``/simulator/start`` and ``/simulator/stop``
    flip ``/status.simulator_running`` and are idempotent.

The test runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``) so no unbounded feed runs, seeds rows directly,
and closes the DB in teardown so the process exits cleanly.
"""

import asyncio
import os
import tempfile
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


def _iso(i: int) -> str:
    # Distinct, monotonic timestamps so ORDER BY created_at, id is deterministic.
    return datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", f".{i:06d}+00:00"
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient wired to a temp data dir with the simulator off."""
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

    # Ensure a fresh connection bound to the temp DB path.
    asyncio.get_event_loop_policy()  # touch to keep import side-effects sane

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

    # Teardown: close the DB so the process exits cleanly.
    async def _close():
        await database.close_db()

    _run(_close())


async def _seed_pending(n: int) -> None:
    """Insert ``n`` pending discrepancies (each in its own aligned group)."""
    from app.db.database import get_db

    db = await get_db()
    for i in range(n):
        gid = str(uuid.uuid4())
        part = f"PART-{i:05d}"
        lot = f"LOT-{i:05d}"
        await db.execute(
            """INSERT INTO sc_aligned_groups
                   (id, part_number, lot_number, present_sources,
                    alignment_state, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (gid, part, lot, '["LAIR","SHQ"]', "complete", _iso(i), _iso(i)),
        )
        await db.execute(
            """INSERT INTO sc_discrepancies
                   (id, group_id, part_number, lot_number, field_name,
                    field_type, "values", provenance, review_state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                gid,
                part,
                lot,
                "diameter",
                "numeric",
                '{"LAIR": 10.0, "SHQ": 12.0}',
                "numeric-threshold",
                "pending",
                _iso(i),
            ),
        )
    await db.commit()


async def _seed_confirmed(n: int) -> None:
    """Insert ``n`` confirmed discrepancies (each in its own aligned group)."""
    from app.db.database import get_db

    db = await get_db()
    for i in range(n):
        gid = str(uuid.uuid4())
        part = f"CPART-{i:05d}"
        lot = f"CLOT-{i:05d}"
        await db.execute(
            """INSERT INTO sc_aligned_groups
                   (id, part_number, lot_number, present_sources,
                    alignment_state, created_at, updated_at)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (gid, part, lot, '["LAIR","SHQ"]', "complete", _iso(i), _iso(i)),
        )
        await db.execute(
            """INSERT INTO sc_discrepancies
                   (id, group_id, part_number, lot_number, field_name,
                    field_type, "values", provenance, review_state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                str(uuid.uuid4()),
                gid,
                part,
                lot,
                "diameter",
                "numeric",
                '{"LAIR": 10.0, "SHQ": 12.0}',
                "numeric-threshold",
                "confirmed",
                _iso(i),
            ),
        )
    await db.commit()


def test_review_queue_pagination(client):
    _run(_seed_pending(120))

    # First page: 50 rows, total_count reflects ALL pending (120).
    resp = client.get("/api/v1/source-comparison/review/queue?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 50
    assert body["total_count"] == 120
    assert body["limit"] == 50
    assert body["offset"] == 0

    # Last partial page: offset=100 -> 20 remaining rows.
    resp = client.get("/api/v1/source-comparison/review/queue?limit=50&offset=100")
    body = resp.json()
    assert len(body["data"]) == 20
    assert body["total_count"] == 120


def test_review_queue_limit_capped(client):
    _run(_seed_pending(5))
    # Over-cap request is clamped to MAX_PAGE_LIMIT (200) by the query validator.
    resp = client.get("/api/v1/source-comparison/review/queue?limit=999")
    # FastAPI rejects limit > le=200 with 422 — the cap is enforced at the edge.
    assert resp.status_code == 422


def test_report_pagination(client):
    _run(_seed_confirmed(120))

    resp = client.get("/api/v1/source-comparison/report?limit=50")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["data"]) == 50
    assert body["total_count"] == 120
    assert body["limit"] == 50
    assert body["offset"] == 0

    resp = client.get("/api/v1/source-comparison/report?limit=50&offset=100")
    body = resp.json()
    assert len(body["data"]) == 20
    assert body["total_count"] == 120


def test_report_export_returns_all_rows(client):
    _run(_seed_confirmed(120))

    # Export ignores pagination — the CSV must contain ALL 120 confirmed rows.
    resp = client.get("/api/v1/source-comparison/report/export?limit=50")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("text/csv")
    lines = [ln for ln in resp.text.splitlines() if ln.strip()]
    # 1 header row + 120 data rows.
    assert len(lines) == 121


def test_simulator_start_stop_idempotent(client):
    # Simulator disabled at startup -> not running.
    status = client.get("/api/v1/source-comparison/status").json()
    assert status["simulator_running"] is False

    # Start -> running true.
    resp = client.post("/api/v1/source-comparison/simulator/start")
    assert resp.status_code == 200
    assert resp.json() == {"running": True}
    status = client.get("/api/v1/source-comparison/status").json()
    assert status["simulator_running"] is True

    # Start again -> idempotent, still running.
    resp = client.post("/api/v1/source-comparison/simulator/start")
    assert resp.json() == {"running": True}

    # Stop -> running false.
    resp = client.post("/api/v1/source-comparison/simulator/stop")
    assert resp.status_code == 200
    assert resp.json() == {"running": False}
    status = client.get("/api/v1/source-comparison/status").json()
    assert status["simulator_running"] is False

    # Stop again -> idempotent.
    resp = client.post("/api/v1/source-comparison/simulator/stop")
    assert resp.json() == {"running": False}
