"""Bounded verification for the GROUPED pending review queue (accordion view).

Covers ``GET /source-comparison/review/queue-grouped``, which groups pending
discrepancies by ``(part_number, lot_number)`` so the review UI can render an
accordion: one panel per group carrying its pending ``count``, a per-provenance
``provenance_counts`` breakdown, and the group's pending ``discrepancies``.

Seeds three part/lot groups with mixed provenance plus one CONFIRMED item that
must be excluded, then asserts group counts, provenance sums, exclusion of the
confirmed item, and group-level pagination (limit/offset page the groups).

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``), seeds rows directly, and closes the DB in
teardown so the process exits cleanly.
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
    # Distinct, monotonic timestamps so group ordering by MIN(created_at) is
    # deterministic (group A earliest, then B, then C).
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
        yield c

    async def _close():
        await database.close_db()

    _run(_close())


async def _insert_group(part: str, lot: str, ts_i: int) -> str:
    from app.db.database import get_db

    db = await get_db()
    gid = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO sc_aligned_groups
               (id, part_number, lot_number, present_sources,
                alignment_state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (gid, part, lot, '["LAIR","SHQ"]', "complete", _iso(ts_i), _iso(ts_i)),
    )
    await db.commit()
    return gid


async def _insert_disc(
    gid: str,
    part: str,
    lot: str,
    field_name: str,
    provenance: str,
    review_state: str,
    ts_i: int,
) -> None:
    from app.db.database import get_db

    db = await get_db()
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
            field_name,
            "numeric",
            '{"LAIR": 10.0, "SHQ": 12.0}',
            provenance,
            review_state,
            _iso(ts_i),
        ),
    )
    await db.commit()


async def _seed() -> None:
    """Seed 3 groups of pending discrepancies + one confirmed item in group A.

    Group A (PART-A/LOT-A): 3 pending, mixed provenance + 1 CONFIRMED (excluded).
    Group B (PART-B/LOT-B): 2 pending.
    Group C (PART-C/LOT-C): 1 pending.
    Timestamps make A the earliest group, then B, then C.
    """
    # Group A — earliest.
    a = await _insert_group("PART-A", "LOT-A", 0)
    await _insert_disc(a, "PART-A", "LOT-A", "diameter", "exact-match", "pending", 0)
    await _insert_disc(a, "PART-A", "LOT-A", "length", "numeric-threshold", "pending", 1)
    await _insert_disc(a, "PART-A", "LOT-A", "material", "llm", "pending", 2)
    # A confirmed item in group A that must NOT appear in the pending queue.
    await _insert_disc(a, "PART-A", "LOT-A", "coating", "llm", "confirmed", 3)

    # Group B — next.
    b = await _insert_group("PART-B", "LOT-B", 10)
    await _insert_disc(b, "PART-B", "LOT-B", "diameter", "exact-match", "pending", 10)
    await _insert_disc(b, "PART-B", "LOT-B", "length", "llm-unavailable", "pending", 11)

    # Group C — last.
    c = await _insert_group("PART-C", "LOT-C", 20)
    await _insert_disc(c, "PART-C", "LOT-C", "diameter", "numeric-threshold", "pending", 20)


def test_grouped_queue_shape_and_exclusion(client):
    _run(_seed())

    resp = client.get("/api/v1/source-comparison/review/queue-grouped")
    assert resp.status_code == 200
    body = resp.json()

    # 3 groups total; all fit on the default page.
    assert body["total_count"] == 3
    assert len(body["data"]) == 3

    by_part = {g["part_number"]: g for g in body["data"]}
    assert set(by_part) == {"PART-A", "PART-B", "PART-C"}

    # Group A: 3 pending (confirmed item excluded), provenance sums to count.
    a = by_part["PART-A"]
    assert a["lot_number"] == "LOT-A"
    assert a["count"] == 3
    assert len(a["discrepancies"]) == 3
    assert sum(a["provenance_counts"].values()) == 3
    assert a["provenance_counts"]["exact-match"] == 1
    assert a["provenance_counts"]["numeric-threshold"] == 1
    assert a["provenance_counts"]["llm"] == 1
    assert a["provenance_counts"]["llm-unavailable"] == 0
    # The confirmed "coating" discrepancy must not be present.
    fields = {d["field_name"] for d in a["discrepancies"]}
    assert "coating" not in fields
    assert all(d["review_state"] == "pending" for d in a["discrepancies"])

    # Group B: 2 pending.
    b = by_part["PART-B"]
    assert b["count"] == 2
    assert len(b["discrepancies"]) == 2
    assert sum(b["provenance_counts"].values()) == 2

    # Group C: 1 pending.
    c = by_part["PART-C"]
    assert c["count"] == 1
    assert len(c["discrepancies"]) == 1
    assert sum(c["provenance_counts"].values()) == 1

    # Stable ordering by earliest pending item: A, then B, then C.
    assert [g["part_number"] for g in body["data"]] == ["PART-A", "PART-B", "PART-C"]


def test_grouped_queue_pagination(client):
    _run(_seed())

    # First page of 2 groups; total_count still reports all 3 groups.
    resp = client.get("/api/v1/source-comparison/review/queue-grouped?limit=2")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 3
    assert body["limit"] == 2
    assert body["offset"] == 0
    assert len(body["data"]) == 2
    assert [g["part_number"] for g in body["data"]] == ["PART-A", "PART-B"]

    # offset=2 returns the last group.
    resp = client.get("/api/v1/source-comparison/review/queue-grouped?limit=2&offset=2")
    body = resp.json()
    assert body["total_count"] == 3
    assert len(body["data"]) == 1
    assert body["data"][0]["part_number"] == "PART-C"
    assert body["data"][0]["count"] == 1
