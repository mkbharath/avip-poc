"""Bounded verification for the report review-status filter + reopen action.

Covers the opt-in review-status views added to the source-comparison report and
the reopen path, while proving the DEFAULT report stays confirmed-only
(Property 5 preserved):

  * GET /report with NO review_state param returns confirmed rows only — the
    seeded dismissed and pending rows never appear.
  * GET /report?review_state=dismissed returns the dismissed rows only.
  * POST /review/{id}/reopen on a dismissed discrepancy returns it to pending
    (it leaves both the dismissed and the confirmed report views), and the
    default confirmed report is unchanged.

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``), seeds rows directly, and closes the DB in
teardown so the process exits cleanly — mirrors
``test_sc_pagination_and_simulator.py``.
"""

import asyncio
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
    return datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat().replace(
        "+00:00", f".{i:06d}+00:00"
    )


@pytest.fixture()
def client(tmp_path, monkeypatch):
    """A FastAPI TestClient wired to a temp data dir with the simulator off."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"

    from app.db import database

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        if getattr(app.state, "sc_simulator_task", None) is not None:
            app.state.sc_simulator_task.cancel()
        app.state.sc_simulator = None
        app.state.sc_simulator_task = None
        yield c

    async def _close():
        await database.close_db()

    _run(_close())


async def _seed_one(review_state: str, i: int) -> str:
    """Insert one discrepancy in ``review_state`` and return its id."""
    from app.db.database import get_db

    db = await get_db()
    gid = str(uuid.uuid4())
    disc_id = str(uuid.uuid4())
    part = f"{review_state.upper()}-PART-{i:03d}"
    lot = f"{review_state.upper()}-LOT-{i:03d}"
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
            disc_id,
            gid,
            part,
            lot,
            "diameter",
            "numeric",
            '{"LAIR": 10.0, "SHQ": 12.0}',
            "numeric-threshold",
            review_state,
            _iso(i),
        ),
    )
    await db.commit()
    return disc_id


async def _seed_mixed() -> dict[str, str]:
    """Seed one confirmed, one dismissed, and one pending discrepancy."""
    return {
        "confirmed": await _seed_one("confirmed", 0),
        "dismissed": await _seed_one("dismissed", 1),
        "pending": await _seed_one("pending", 2),
    }


def test_default_report_is_confirmed_only(client):
    ids = _run(_seed_mixed())

    # No review_state param -> confirmed-only (Property 5 preserved).
    resp = client.get("/api/v1/source-comparison/report")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    returned_ids = {r["id"] for r in body["data"]}
    assert returned_ids == {ids["confirmed"]}


def test_report_dismissed_filter_returns_dismissed_only(client):
    ids = _run(_seed_mixed())

    resp = client.get("/api/v1/source-comparison/report?review_state=dismissed")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    row = body["data"][0]
    assert row["id"] == ids["dismissed"]
    # The opt-in view carries review_state so the UI can drive Reopen.
    assert row["review_state"] == "dismissed"


def test_reopen_dismissed_moves_it_to_pending_and_leaves_confirmed_report(client):
    ids = _run(_seed_mixed())

    # Reopen the dismissed discrepancy -> becomes pending.
    resp = client.post(
        f"/api/v1/source-comparison/review/{ids['dismissed']}/reopen",
        json={"decision": "confirmed", "reviewer": "IQA Inspector", "note": "recheck"},
    )
    assert resp.status_code == 200
    assert resp.json()["review_state"] == "pending"

    # It no longer appears under the dismissed view...
    dismissed = client.get(
        "/api/v1/source-comparison/report?review_state=dismissed"
    ).json()
    assert dismissed["total_count"] == 0

    # ...and now appears under the pending view.
    pending = client.get(
        "/api/v1/source-comparison/report?review_state=pending"
    ).json()
    pending_ids = {r["id"] for r in pending["data"]}
    assert ids["dismissed"] in pending_ids

    # The DEFAULT confirmed report is unchanged (still just the confirmed row).
    default = client.get("/api/v1/source-comparison/report").json()
    assert default["total_count"] == 1
    assert {r["id"] for r in default["data"]} == {ids["confirmed"]}
