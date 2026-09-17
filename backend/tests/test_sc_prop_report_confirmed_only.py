"""Property-based test — the report contains exactly the confirmed subset.

# Feature: avip-source-comparison, Property 5

Property 5: Unconfirmed discrepancies never reach the report.

*For any* set of discrepancies with arbitrary review states, the report SHALL
contain exactly those whose recorded decision is ``confirmed`` — no ``pending``
and no ``dismissed`` discrepancy SHALL appear (Req 6.1, 6.4, 6.5, 7.2).

The test seeds a batch of discrepancies with randomly-assigned review states
into a temp SQLite DB, assembles the report via ``report.build_report`` (which
delegates confirmed-only filtering to ``sc_review.list_confirmed``), and
asserts the report's id set equals exactly the seeded ``confirmed`` id set.

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled
(``AVIP_SC_SIMULATOR=false``); settings are rebound to the temp dir, the schema
is initialized per test, and the DB is closed in teardown so the process exits
cleanly.

_Requirements: 6.1, 6.4, 6.5, 7.2_
"""

import asyncio
import uuid
from datetime import datetime, timezone

import pytest
from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.source_comparison import ReviewState


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
def db_env(tmp_path, monkeypatch):
    """Wire a temp data dir with the simulator off, init the schema, teardown."""
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"
    # Create the temp data dir (and derived dirs) so the SQLite file can open —
    # the app normally does this at startup; here we init the schema directly.
    settings.ensure_dirs()

    from app.db import database

    _run(database.init_db())

    yield

    async def _close():
        await database.close_db()

    _run(_close())


async def _reset_discrepancies() -> None:
    """Clear discrepancy + audit/decision rows so each example starts clean."""
    from app.db.database import get_db

    db = await get_db()
    await db.execute("DELETE FROM sc_review_audit")
    await db.execute("DELETE FROM sc_review_decisions")
    await db.execute("DELETE FROM sc_discrepancies")
    await db.execute("DELETE FROM sc_aligned_groups")
    await db.commit()


async def _seed_with_states(states: list[str]) -> dict[str, set[str]]:
    """Seed one discrepancy per state; return the ids bucketed by state.

    Each discrepancy gets its own aligned group (UNIQUE part+lot) so the
    ``(group_id, field_name)`` uniqueness never collides.
    """
    from app.db.database import get_db

    db = await get_db()
    ids_by_state: dict[str, set[str]] = {s.value: set() for s in ReviewState}
    for i, state in enumerate(states):
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
                state,
                _iso(i),
            ),
        )
        ids_by_state[state].add(did)
    await db.commit()
    return ids_by_state


_REVIEW_STATES = st.sampled_from([s.value for s in ReviewState])


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(states=st.lists(_REVIEW_STATES, min_size=0, max_size=12))
def test_report_contains_exactly_confirmed_subset(db_env, states: list[str]) -> None:
    """The report's id set equals exactly the seeded ``confirmed`` ids."""

    async def _scenario() -> None:
        from app.services.report import build_report

        await _reset_discrepancies()
        ids_by_state = await _seed_with_states(states)

        # Fetch ALL matching rows (limit=None) so no page truncation hides rows.
        rows, total_count = await build_report(limit=None)
        report_ids = {row["id"] for row in rows}

        confirmed_ids = ids_by_state[ReviewState.CONFIRMED.value]
        pending_ids = ids_by_state[ReviewState.PENDING.value]
        dismissed_ids = ids_by_state[ReviewState.DISMISSED.value]

        # Exactly the confirmed subset — no pending, no dismissed.
        assert report_ids == confirmed_ids
        assert total_count == len(confirmed_ids)
        assert report_ids.isdisjoint(pending_ids)
        assert report_ids.isdisjoint(dismissed_ids)

    _run(_scenario())
