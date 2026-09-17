"""Property-based test — review decisions round-trip with an immutable audit row.

# Feature: avip-source-comparison, Property 6

Property 6: Review decisions round-trip with audit.

*For any* discrepancy and any confirm/dismiss decision recorded against it with
a reviewer and optional note, reading the discrepancy back SHALL yield that
decision, reviewer, and note, and a corresponding timestamped audit entry SHALL
exist (Req 6.3, 9.3).

The test seeds a ``pending`` discrepancy, applies a generated
decision/reviewer/note through the review gate (``sc_review.decide``), then
asserts:

  * the discrepancy's ``review_state`` reflects the decision;
  * the current-decision row (``sc_review_decisions``) reads back with the same
    decision, reviewer, and note;
  * an append-only ``sc_review_audit`` row exists for the decision, carrying the
    same decision/reviewer/note and a non-empty ``decided_at`` timestamp.

Runs against a temp ``AVIP_DATA_DIR`` with the simulator disabled; settings are
rebound to the temp dir, the schema is initialized per test, and the DB is
closed in teardown.

_Requirements: 6.3, 9.3_
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


async def _reset() -> None:
    from app.db.database import get_db

    db = await get_db()
    await db.execute("DELETE FROM sc_review_audit")
    await db.execute("DELETE FROM sc_review_decisions")
    await db.execute("DELETE FROM sc_discrepancies")
    await db.execute("DELETE FROM sc_aligned_groups")
    await db.commit()


async def _seed_pending_discrepancy() -> str:
    """Seed a single pending discrepancy in its own group; return its id."""
    from app.db.database import get_db

    db = await get_db()
    gid = str(uuid.uuid4())
    did = str(uuid.uuid4())
    await db.execute(
        """INSERT INTO sc_aligned_groups
               (id, part_number, lot_number, present_sources,
                alignment_state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (gid, "PART-1", "LOT-1", '["LAIR","SHQ"]', "complete", _iso(0), _iso(0)),
    )
    await db.execute(
        """INSERT INTO sc_discrepancies
               (id, group_id, part_number, lot_number, field_name,
                field_type, "values", provenance, review_state, created_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            did,
            gid,
            "PART-1",
            "LOT-1",
            "diameter",
            "numeric",
            '{"LAIR": 10.0, "SHQ": 12.0}',
            "numeric-threshold",
            ReviewState.PENDING.value,
            _iso(0),
        ),
    )
    await db.commit()
    return did


_DECISIONS = st.sampled_from(["confirmed", "dismissed"])
# Reviewer identity: non-empty printable text.
_REVIEWERS = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126), min_size=1, max_size=40
)
# Optional note: either None or arbitrary text (incl. empty).
_NOTES = st.one_of(
    st.none(),
    st.text(alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=80),
)

_STATE_FOR_DECISION = {
    "confirmed": ReviewState.CONFIRMED,
    "dismissed": ReviewState.DISMISSED,
}


@settings(max_examples=50, deadline=None, suppress_health_check=[HealthCheck.function_scoped_fixture])
@given(decision=_DECISIONS, reviewer=_REVIEWERS, note=_NOTES)
def test_review_decision_roundtrips_with_audit(
    db_env, decision: str, reviewer: str, note: str | None
) -> None:
    """A recorded decision reads back equal and leaves a timestamped audit row."""

    async def _scenario() -> None:
        from app.db.database import get_db
        from app.services import sc_review

        await _reset()
        did = await _seed_pending_discrepancy()

        returned = await sc_review.decide(did, decision, reviewer, note)

        # 1) The returned model + the persisted discrepancy reflect the decision.
        expected_state = _STATE_FOR_DECISION[decision]
        assert returned.review_state is expected_state

        fetched = await sc_review.get_discrepancy(did)
        assert fetched is not None
        assert fetched.review_state is expected_state

        db = await get_db()

        # 2) The current-decision row reads back equal (decision/reviewer/note).
        cur = await db.execute(
            """SELECT decision, reviewer, note, decided_at
                 FROM sc_review_decisions WHERE discrepancy_id = ?""",
            (did,),
        )
        drow = await cur.fetchone()
        assert drow is not None
        assert drow["decision"] == decision
        assert drow["reviewer"] == reviewer
        assert drow["note"] == note
        assert drow["decided_at"]  # non-empty timestamp

        # 3) A timestamped audit row exists for this decision (append-only).
        cur = await db.execute(
            """SELECT decision, reviewer, note, decided_at
                 FROM sc_review_audit WHERE discrepancy_id = ?""",
            (did,),
        )
        arows = await cur.fetchall()
        assert len(arows) == 1
        arow = arows[0]
        assert arow["decision"] == decision
        assert arow["reviewer"] == reviewer
        assert arow["note"] == note
        assert arow["decided_at"]  # non-empty timestamp

    _run(_scenario())
