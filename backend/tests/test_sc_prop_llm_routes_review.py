# Feature: avip-source-comparison, Property 7
"""Property 7 — LLM free-text output always routes through review (task 5.5).

Free-text comparison is LLM-assisted, and its output is never authoritative on
its own: every LLM-produced finding — including the ``llm-unavailable`` case
where the provider fails — must enter the pipeline as ``pending`` and stay out
of the report until a reviewer explicitly confirms it (Req 5.4, 5.5).

This property drives ``comparison.compare_group`` over aligned groups whose
free-text fields disagree, using a MOCKED provider that Hypothesis flips between
two behaviours per example:

  * a working provider that reports ``differ=True`` → provenance ``llm``; and
  * a failing provider that raises on ``compare_text`` (simulated
    ``llm-unavailable``) → provenance ``llm-unavailable``, routed to review and
    never treated as agreeing.

For every generated case the test asserts each LLM discrepancy:
  * enters as ``pending`` (never auto-confirmed, Property 7);
  * is absent from the confirmed-only report while pending; and
  * becomes final (appears in the report) ONLY after a recorded confirmation
    through the review gate.

Hypothesis runs ``@settings(max_examples=100)``. Each example uses its own fresh
temp SQLite DB (init/teardown inside the test body) with the simulator disabled.

_Requirements: 5.4, 5.5_
_Properties: 7_
"""

import asyncio
import uuid
from datetime import datetime, timezone

from hypothesis import HealthCheck, given, settings
from hypothesis import strategies as st

from app.models.source_comparison import (
    AlignedGroup,
    AlignmentState,
    SourceRecord,
    SourceType,
)
from app.services.llm_provider import LLMComparison


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


class _DifferingLLMProvider:
    """Mock provider that always judges the two free-text values as differing."""

    name = "mock-differ"

    async def compare_text(self, a, b) -> LLMComparison:
        return LLMComparison(differ=True, rationale="mock: values differ")


class _FailingLLMProvider:
    """Mock provider that fails (simulated ``llm-unavailable``)."""

    name = "mock-unavailable"

    async def compare_text(self, a, b) -> LLMComparison:
        raise RuntimeError("simulated provider outage")


async def _init_temp_db(tmp_dir):
    """Point settings at a temp dir, initialize a fresh DB, return the module."""
    from app.config import settings

    settings.data_dir = tmp_dir
    settings.models_dir = tmp_dir / "models"
    settings.demo_data_dir = tmp_dir / "demo_data"

    from app.db import database

    await database.close_db()
    await database.init_db()
    return database


async def _persist_group(group: AlignedGroup) -> None:
    """Persist the aligned group row so the discrepancy FK is satisfied."""
    from app.db.database import get_db

    db = await get_db()
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    await db.execute(
        """INSERT INTO sc_aligned_groups
               (id, part_number, lot_number, present_sources,
                alignment_state, created_at, updated_at)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (
            group.id,
            group.part_number,
            group.lot_number,
            '["LAIR","SHQ"]',
            "complete",
            now,
            now,
        ),
    )
    await db.commit()


def _build_group(note_a: str, note_b: str) -> AlignedGroup:
    """Build a two-source aligned group differing on the free-text field."""
    gid = str(uuid.uuid4())
    part, lot = "PART-LLM", "LOT-LLM"
    return AlignedGroup(
        id=gid,
        part_number=part,
        lot_number=lot,
        present_sources=[SourceType.LAIR, SourceType.SHQ],
        alignment_state=AlignmentState.COMPLETE,
        created_at="2024-01-01T00:00:00+00:00",
        updated_at="2024-01-01T00:00:00+00:00",
        records=[
            SourceRecord(
                id=str(uuid.uuid4()),
                source=SourceType.LAIR,
                external_record_id="lair-1",
                part_number=part,
                lot_number=lot,
                fields={"inspector_notes": note_a},
                group_id=gid,
                received_at="2024-01-01T00:00:00+00:00",
            ),
            SourceRecord(
                id=str(uuid.uuid4()),
                source=SourceType.SHQ,
                external_record_id="shq-1",
                part_number=part,
                lot_number=lot,
                fields={"inspector_notes": note_b},
                group_id=gid,
                received_at="2024-01-01T00:00:00+00:00",
            ),
        ],
    )


# Two clearly-different free-text notes (the mock provider is what decides the
# outcome, but distinct values keep the scenario realistic).
_note_strategy = st.text(
    alphabet=st.characters(min_codepoint=32, max_codepoint=126), max_size=30
)


@settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=[HealthCheck.function_scoped_fixture],
)
@given(
    provider_fails=st.booleans(),
    note_a=_note_strategy,
    note_b=_note_strategy,
)
def test_llm_free_text_output_always_routes_through_review(
    tmp_path_factory, provider_fails, note_a, note_b
):
    tmp_dir = tmp_path_factory.mktemp("sc_llm_review")

    async def scenario():
        database = await _init_temp_db(tmp_dir)
        from app.services import comparison, report, sc_review

        provider = _FailingLLMProvider() if provider_fails else _DifferingLLMProvider()

        group = _build_group(note_a, note_b)
        await _persist_group(group)

        # Run comparison with the mocked provider for the free-text field.
        current = await comparison.compare_group(group, llm=provider)

        # Isolate the LLM-produced free-text discrepancies.
        llm_discrepancies = [
            d
            for d in current
            if d.field_type.value == "free_text"
            and d.provenance.value in ("llm", "llm-unavailable")
        ]
        # The free-text field disagrees (working provider) or the provider failed
        # (unavailable) — either way exactly one LLM discrepancy is produced.
        assert len(llm_discrepancies) == 1
        disc = llm_discrepancies[0]

        # Provenance matches the provider behaviour, and a failure NEVER agrees.
        if provider_fails:
            assert disc.provenance.value == "llm-unavailable"
        else:
            assert disc.provenance.value == "llm"

        # (1) It enters as pending — never auto-confirmed / auto-treated final.
        assert disc.review_state.value == "pending"

        db = await database.get_db()
        cur = await db.execute(
            "SELECT review_state FROM sc_discrepancies WHERE id = ?", (disc.id,)
        )
        assert (await cur.fetchone())["review_state"] == "pending"

        # No decision or audit rows exist yet — nothing was silently finalized.
        cur = await db.execute(
            "SELECT COUNT(*) FROM sc_review_decisions WHERE discrepancy_id = ?",
            (disc.id,),
        )
        assert int((await cur.fetchone())[0]) == 0
        cur = await db.execute(
            "SELECT COUNT(*) FROM sc_review_audit WHERE discrepancy_id = ?",
            (disc.id,),
        )
        assert int((await cur.fetchone())[0]) == 0

        # (2) While pending it is absent from the confirmed-only report.
        rows, total = await report.build_report(limit=None)
        assert all(r["id"] != disc.id for r in rows)

        # (3) It becomes final ONLY via a recorded confirmation through the gate.
        await sc_review.decide(
            discrepancy_id=disc.id, decision="confirmed", reviewer="qa"
        )
        rows, total = await report.build_report(limit=None)
        assert any(r["id"] == disc.id for r in rows)

        # The confirmation is recorded with an immutable audit row.
        cur = await db.execute(
            "SELECT COUNT(*) FROM sc_review_audit WHERE discrepancy_id = ?",
            (disc.id,),
        )
        assert int((await cur.fetchone())[0]) == 1

        await database.close_db()

    _run(scenario())
