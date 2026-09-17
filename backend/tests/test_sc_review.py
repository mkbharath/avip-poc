"""Unit tests for the source-comparison review gate + audit (task 5.3).

Exercises ``app.services.sc_review`` directly (no HTTP) against a fresh temp
SQLite DB:

  * ``decide("confirmed", ...)`` / ``decide("dismissed", ...)`` update the
    discrepancy's ``review_state`` AND write both the single current-decision
    row (``sc_review_decisions``) and an immutable ``sc_review_audit`` row
    carrying reviewer + note + timestamp (Req 6.3, 9.3).
  * The confirmed-only report path (``sc_review.list_confirmed`` /
    ``services/report.build_report``) EXCLUDES pending and dismissed
    discrepancies — dismissed permanently — so only reviewer-confirmed findings
    reach the report (Req 6.4, 6.5, Property 5).

Convention (mirrors ``test_sc_pagination_and_simulator.py`` /
``test_sc_bulk_decide.py``): a temp ``AVIP_DATA_DIR`` with the simulator off
(``AVIP_SC_SIMULATOR=false``), settings rebound to the temp paths, the DB
initialized via ``init_db()``, discrepancies seeded directly, and the DB closed
in teardown so the process exits cleanly.

_Requirements: 6.3, 6.4, 6.5, 9.3_
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
def db(tmp_path, monkeypatch):
    """A freshly-initialized temp SQLite DB with the simulator disabled.

    Rebinds the ``settings`` paths (settings is instantiated at import time) so
    ``init_db()`` creates the schema in the temp data dir, then closes the
    connection in teardown.
    """
    data_dir = tmp_path / "data"
    monkeypatch.setenv("AVIP_DATA_DIR", str(data_dir))
    monkeypatch.setenv("AVIP_SC_SIMULATOR", "false")

    from app.config import settings

    settings.data_dir = data_dir
    settings.models_dir = tmp_path / "models"
    settings.demo_data_dir = tmp_path / "demo_data"
    # Create the temp data dir (the TestClient lifespan does this via
    # ensure_dirs(); direct-service tests must do it before init_db()).
    settings.ensure_dirs()

    from app.db import database

    _run(database.init_db())

    yield database

    _run(database.close_db())


async def _seed_discrepancy(
    *,
    part: str,
    lot: str,
    field_name: str = "diameter",
    field_type: str = "numeric",
    values_json: str = '{"LAIR": 10.0, "SHQ": 12.0}',
    provenance: str = "numeric-threshold",
    review_state: str = "pending",
    i: int = 0,
) -> str:
    """Insert one aligned group + one discrepancy; return the discrepancy id."""
    from app.db.database import get_db

    db = await get_db()
    gid = str(uuid.uuid4())
    did = str(uuid.uuid4())
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
            field_name,
            field_type,
            values_json,
            provenance,
            review_state,
            _iso(i),
        ),
    )
    await db.commit()
    return did


async def _review_state(discrepancy_id: str) -> str:
    from app.db.database import get_db

    db = await get_db()
    cur = await db.execute(
        "SELECT review_state FROM sc_discrepancies WHERE id = ?", (discrepancy_id,)
    )
    row = await cur.fetchone()
    return row["review_state"]


async def _decision_row(discrepancy_id: str):
    from app.db.database import get_db

    db = await get_db()
    cur = await db.execute(
        """SELECT decision, reviewer, note, decided_at
             FROM sc_review_decisions WHERE discrepancy_id = ?""",
        (discrepancy_id,),
    )
    return await cur.fetchone()


async def _audit_rows(discrepancy_id: str):
    from app.db.database import get_db

    db = await get_db()
    cur = await db.execute(
        """SELECT decision, reviewer, note, decided_at
             FROM sc_review_audit WHERE discrepancy_id = ?
            ORDER BY decided_at ASC""",
        (discrepancy_id,),
    )
    return await cur.fetchall()


# ── decide() updates state + writes decision + immutable audit (Req 6.3, 9.3) ─


def test_confirm_updates_state_and_writes_decision_and_audit(db):
    did = _run(_seed_discrepancy(part="PART-A", lot="LOT-A"))

    from app.services import sc_review

    updated = _run(
        sc_review.decide(
            discrepancy_id=did,
            decision="confirmed",
            reviewer="qa.lead",
            note="looks like a real deviation",
        )
    )

    # Returned model reflects the new state.
    assert updated.review_state.value == "confirmed"
    # Persisted discrepancy state updated.
    assert _run(_review_state(did)) == "confirmed"

    # A single current-decision row was written with reviewer + note + timestamp.
    decision = _run(_decision_row(did))
    assert decision is not None
    assert decision["decision"] == "confirmed"
    assert decision["reviewer"] == "qa.lead"
    assert decision["note"] == "looks like a real deviation"
    assert decision["decided_at"]  # a non-empty ISO timestamp

    # An immutable audit row was appended, mirroring the decision.
    audit = _run(_audit_rows(did))
    assert len(audit) == 1
    assert audit[0]["decision"] == "confirmed"
    assert audit[0]["reviewer"] == "qa.lead"
    assert audit[0]["note"] == "looks like a real deviation"
    assert audit[0]["decided_at"]


def test_dismiss_updates_state_and_writes_decision_and_audit(db):
    did = _run(_seed_discrepancy(part="PART-B", lot="LOT-B"))

    from app.services import sc_review

    updated = _run(
        sc_review.decide(
            discrepancy_id=did,
            decision="dismissed",
            reviewer="inspector.j",
            note="false alarm — tooling rounding",
        )
    )

    assert updated.review_state.value == "dismissed"
    assert _run(_review_state(did)) == "dismissed"

    decision = _run(_decision_row(did))
    assert decision["decision"] == "dismissed"
    assert decision["reviewer"] == "inspector.j"

    audit = _run(_audit_rows(did))
    assert len(audit) == 1
    assert audit[0]["decision"] == "dismissed"


def test_redecide_upserts_single_decision_but_appends_audit_history(db):
    """Re-deciding keeps ONE current-decision row but retains full audit history.

    The audit table is immutable/append-only (Req 9.3): a re-decision writes a
    NEW audit row, so the decision history is retained even though the single
    ``sc_review_decisions`` row reflects only the latest decision.
    """
    did = _run(_seed_discrepancy(part="PART-C", lot="LOT-C"))

    from app.services import sc_review

    _run(sc_review.decide(discrepancy_id=did, decision="confirmed", reviewer="a"))
    _run(
        sc_review.decide(
            discrepancy_id=did, decision="dismissed", reviewer="b", note="reversed"
        )
    )

    # Latest decision wins on the single current-decision row.
    assert _run(_review_state(did)) == "dismissed"
    decision = _run(_decision_row(did))
    assert decision["decision"] == "dismissed"
    assert decision["reviewer"] == "b"

    # But the audit trail retains BOTH decisions (append-only).
    audit = _run(_audit_rows(did))
    assert len(audit) == 2
    assert [r["decision"] for r in audit] == ["confirmed", "dismissed"]


def test_decide_invalid_decision_raises(db):
    did = _run(_seed_discrepancy(part="PART-D", lot="LOT-D"))

    from app.services import sc_review

    with pytest.raises(ValueError):
        _run(sc_review.decide(discrepancy_id=did, decision="maybe", reviewer="x"))
    # Nothing was decided.
    assert _run(_review_state(did)) == "pending"


def test_decide_unknown_discrepancy_raises_lookup(db):
    from app.services import sc_review

    with pytest.raises(LookupError):
        _run(
            sc_review.decide(
                discrepancy_id="does-not-exist", decision="confirmed", reviewer="x"
            )
        )


# ── Report excludes pending + dismissed (Req 6.4, 6.5, Property 5) ────────────


def test_report_excludes_pending_and_dismissed(db):
    """Only confirmed discrepancies reach the report; dismissed are permanent."""
    from app.services import report, sc_review

    confirmed_id = _run(_seed_discrepancy(part="P-CONF", lot="L1", i=0))
    dismissed_id = _run(_seed_discrepancy(part="P-DISM", lot="L2", i=1))
    pending_id = _run(_seed_discrepancy(part="P-PEND", lot="L3", i=2))

    _run(sc_review.decide(discrepancy_id=confirmed_id, decision="confirmed", reviewer="r"))
    _run(sc_review.decide(discrepancy_id=dismissed_id, decision="dismissed", reviewer="r"))
    # pending_id is left pending.

    rows, total = _run(report.build_report(limit=None))

    ids = {row["id"] for row in rows}
    assert confirmed_id in ids
    assert dismissed_id not in ids
    assert pending_id not in ids
    assert total == 1


def test_dismissed_stays_excluded_permanently(db):
    """A dismissed discrepancy never appears in the report (dismissed = final)."""
    from app.services import report, sc_review

    did = _run(_seed_discrepancy(part="P-X", lot="L-X"))
    _run(sc_review.decide(discrepancy_id=did, decision="dismissed", reviewer="r"))

    rows, total = _run(report.build_report(limit=None))
    assert total == 0
    assert all(row["id"] != did for row in rows)

    # list_confirmed (the report's source of truth) also excludes it.
    confirmed, count = _run(sc_review.list_confirmed())
    assert count == 0
    assert all(d.id != did for d in confirmed)
