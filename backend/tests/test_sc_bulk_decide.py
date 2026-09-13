"""Bounded verification for the source-comparison BULK decide capability.

Covers the additive ``POST /source-comparison/review/decide-bulk`` endpoint
(and the ``sc_review.decide_many`` service behind it) that lets the review UI
confirm/dismiss many discrepancies in a single request:

  * A batch of real ids + one bogus id, decision ``"confirmed"`` ->
    ``{updated: N, not_found: [bogus]}``; the confirmed ids move to
    ``confirmed`` (review_state) and each gains an immutable ``sc_review_audit``
    row; the confirmed-only report count reflects them.
  * An empty ``discrepancy_ids`` list is a no-op (200, ``{updated: 0}``).
  * A bad ``decision`` value -> ``422``.

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``) so no unbounded feed runs, seeds rows directly,
and closes the DB in teardown so the process exits cleanly.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

API = "/api/v1/source-comparison"


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

    from app.db import database  # noqa: F401 — imported for teardown handle

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        yield c

    async def _close():
        from app.db import database as db_mod

        await db_mod.close_db()

    _run(_close())


async def _seed_pending(n: int) -> list[str]:
    """Insert ``n`` pending discrepancies; return their ids (own group each)."""
    from app.db.database import get_db

    db = await get_db()
    ids: list[str] = []
    for i in range(n):
        gid = str(uuid.uuid4())
        did = str(uuid.uuid4())
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
                did,
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
        ids.append(did)
    await db.commit()
    return ids


async def _review_state(discrepancy_id: str) -> str:
    from app.db.database import get_db

    db = await get_db()
    cur = await db.execute(
        "SELECT review_state FROM sc_discrepancies WHERE id = ?", (discrepancy_id,)
    )
    row = await cur.fetchone()
    return row["review_state"]


async def _audit_count(discrepancy_id: str) -> int:
    from app.db.database import get_db

    db = await get_db()
    cur = await db.execute(
        "SELECT COUNT(*) FROM sc_review_audit WHERE discrepancy_id = ?",
        (discrepancy_id,),
    )
    row = await cur.fetchone()
    return int(row[0])


def test_bulk_decide_confirms_subset_and_reports_not_found(client):
    ids = _run(_seed_pending(5))
    chosen = ids[:3]
    bogus = "does-not-exist-" + uuid.uuid4().hex

    resp = client.post(
        f"{API}/review/decide-bulk",
        json={
            "discrepancy_ids": chosen + [bogus],
            "decision": "confirmed",
            "reviewer": "qa.lead",
            "note": "batch confirm",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 3
    assert body["not_found"] == [bogus]
    assert body["decision"] == "confirmed"

    # Each chosen discrepancy is now confirmed and has exactly one audit row.
    for did in chosen:
        assert _run(_review_state(did)) == "confirmed"
        assert _run(_audit_count(did)) == 1

    # Untouched discrepancies remain pending.
    for did in ids[3:]:
        assert _run(_review_state(did)) == "pending"

    # The confirmed-only report reflects exactly the 3 confirmed rows.
    report = client.get(f"{API}/report").json()
    assert report["total_count"] == 3


def test_bulk_decide_empty_ids_is_noop(client):
    resp = client.post(
        f"{API}/review/decide-bulk",
        json={
            "discrepancy_ids": [],
            "decision": "confirmed",
            "reviewer": "qa.lead",
        },
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["updated"] == 0
    assert body["not_found"] == []


def test_bulk_decide_bad_decision_is_422(client):
    ids = _run(_seed_pending(1))
    resp = client.post(
        f"{API}/review/decide-bulk",
        json={
            "discrepancy_ids": ids,
            "decision": "maybe",
            "reviewer": "qa.lead",
        },
    )
    # FastAPI's Literal validation rejects an invalid decision at the edge.
    assert resp.status_code == 422
    # The discrepancy stays pending — nothing was decided.
    assert _run(_review_state(ids[0])) == "pending"
