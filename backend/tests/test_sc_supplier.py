"""Bounded verification for the source-comparison SUPPLIER filter + rollup.

Supplier lives in the ``parts`` table (joined onto each report row via
``part_context``), NOT in ``sc_discrepancies``, so supplier filtering is applied
in Python after the confirmed-only set is assembled. This test verifies:

  * ``GET /report?supplier=<name>`` returns ONLY the confirmed rows whose part's
    supplier matches (case-insensitive), and never rows for a part with a
    different/unknown supplier.
  * ``GET /report/supplier-summary`` returns a confirmed-only rollup grouped by
    supplier, including the matching supplier with ``discrepancy_count >= 1`` and
    an ``"(unknown)"`` bucket for parts absent from the ``parts`` table.

Seeds a confirmed discrepancy for a seeded part with a known supplier
(``444-027654-002`` → "CircuitPro Electronics") and one for an unknown part.
Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled so no
unbounded feed runs, and closes the DB in teardown so the process exits cleanly.
Follows the conventions of tests/test_sc_pagination_and_simulator.py.
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest

# The seeded part with a known supplier (see app/db/database.py seed data).
KNOWN_PART = "444-027654-002"
KNOWN_SUPPLIER = "CircuitPro Electronics"
UNKNOWN_PART = "ZZZ-000000-999"  # not in the parts table → supplier unknown


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

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"

    from app.db import database  # noqa: F401  (import for teardown handle)

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


async def _seed_confirmed(part_number: str, i: int) -> None:
    """Insert one CONFIRMED discrepancy for ``part_number`` in its own group."""
    from app.db.database import get_db

    db = await get_db()
    gid = str(uuid.uuid4())
    lot = f"LOT-{i:05d}"
    await db.execute(
        """INSERT INTO sc_aligned_groups
               (id, part_number, lot_number, present_sources,
                alignment_state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (gid, part_number, lot, '["LAIR","SHQ"]', "complete", _iso(i), _iso(i)),
    )
    await db.execute(
        """INSERT INTO sc_discrepancies
               (id, group_id, part_number, lot_number, field_name,
                field_type, "values", provenance, review_state, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            str(uuid.uuid4()),
            gid,
            part_number,
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


def test_report_supplier_filter_returns_only_matching_rows(client):
    _run(_seed_confirmed(KNOWN_PART, 0))
    _run(_seed_confirmed(UNKNOWN_PART, 1))

    # Sanity: with no supplier filter, both confirmed rows are present.
    resp = client.get("/api/v1/source-comparison/report?limit=50")
    assert resp.status_code == 200
    all_parts = {r["part_number"] for r in resp.json()["data"]}
    assert {KNOWN_PART, UNKNOWN_PART} <= all_parts

    # Supplier filter → ONLY the matching part's row(s).
    resp = client.get(
        "/api/v1/source-comparison/report",
        params={"supplier": KNOWN_SUPPLIER, "limit": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    parts = {r["part_number"] for r in body["data"]}
    assert parts == {KNOWN_PART}
    assert UNKNOWN_PART not in parts
    assert body["total_count"] == 1
    # The matching row carries the supplier in its part_context.
    assert body["data"][0]["part_context"]["supplier"] == KNOWN_SUPPLIER


def test_report_supplier_filter_is_case_insensitive(client):
    _run(_seed_confirmed(KNOWN_PART, 0))

    resp = client.get(
        "/api/v1/source-comparison/report",
        params={"supplier": KNOWN_SUPPLIER.lower(), "limit": 50},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == 1
    assert body["data"][0]["part_number"] == KNOWN_PART


def test_supplier_summary_rolls_up_confirmed_discrepancies(client):
    _run(_seed_confirmed(KNOWN_PART, 0))
    _run(_seed_confirmed(UNKNOWN_PART, 1))

    resp = client.get("/api/v1/source-comparison/report/supplier-summary")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == len(body["data"])

    by_supplier = {r["supplier"]: r for r in body["data"]}

    # The known supplier appears with at least one discrepancy and one part.
    assert KNOWN_SUPPLIER in by_supplier
    known = by_supplier[KNOWN_SUPPLIER]
    assert known["discrepancy_count"] >= 1
    assert known["part_count"] >= 1
    assert known["provenance_counts"]["numeric-threshold"] >= 1

    # The part absent from the parts table rolls up under "(unknown)".
    assert "(unknown)" in by_supplier
    assert by_supplier["(unknown)"]["discrepancy_count"] >= 1

    # Sorted by discrepancy_count descending.
    counts = [r["discrepancy_count"] for r in body["data"]]
    assert counts == sorted(counts, reverse=True)
