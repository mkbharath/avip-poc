"""Bounded verification for part_context enrichment on the review queue.

The source-comparison rows carry a bare ``part_number``. This test verifies the
server enriches each row with a human-readable ``part_context`` object (joined
from the existing ``parts`` table) so a reviewer sees what a part IS, not just
its number:

  * A discrepancy whose ``part_number`` matches a seeded part carries
    ``part_context`` with the seeded ``description`` / ``revision``.
  * A discrepancy whose ``part_number`` has no matching parts row carries
    ``part_context = None`` (never an error — external/simulated parts may not be
    in the table).

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``) so no unbounded feed runs, seeds rows directly,
and closes the DB in teardown so the process exits cleanly. Follows the
conventions of tests/test_sc_pagination_and_simulator.py.
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


async def _seed_discrepancy(part_number: str, i: int) -> None:
    """Insert one pending discrepancy for ``part_number`` in its own group."""
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
            "pending",
            _iso(i),
        ),
    )
    await db.commit()


def test_review_queue_rows_carry_part_context(client):
    # Seeded part 444-027654-002 -> "ESC Controller Board", revision "E".
    known_part = "444-027654-002"
    unknown_part = "ZZZ-000000-999"  # not in parts table (external/simulated)

    _run(_seed_discrepancy(known_part, 0))
    _run(_seed_discrepancy(unknown_part, 1))

    resp = client.get("/api/v1/source-comparison/review/queue?limit=50")
    assert resp.status_code == 200
    body = resp.json()

    by_part = {row["part_number"]: row for row in body["data"]}
    assert known_part in by_part
    assert unknown_part in by_part

    # Known part → part_context carries the seeded human-readable fields.
    known_ctx = by_part[known_part]["part_context"]
    assert known_ctx is not None
    assert known_ctx["description"] == "ESC Controller Board"
    assert known_ctx["revision"] == "E"
    assert known_ctx["material"] == "FR-4 / Mixed"
    assert known_ctx["supplier"] == "CircuitPro Electronics"

    # Unknown part → part_context is null (never an error).
    assert by_part[unknown_part]["part_context"] is None
