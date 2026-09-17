"""Integration coverage for the source-comparison threshold-config endpoints.

Exercises the runtime-editable numeric-threshold configuration API (Req 8.1,
8.2) end-to-end through the FastAPI TestClient:

  * GET  /config                — returns the effective field set.
  * PUT  /config/field/{name}   — edits a field default, which changes the
    persisted threshold AND appends a config-audit row.
  * GET  /config/audit          — the audit row for that edit is visible.
  * POST /config/overrides      — creates a per-part override.
  * GET  /config/overrides      — returns the created override.
  * POST /config/overrides      — a negative threshold is rejected 422.
  * DELETE /config/overrides    — removes the override → {deleted: true}.

Follows the conventions in ``test_sc_pagination_and_simulator.py``: a temp
``AVIP_DATA_DIR`` with the simulator disabled, a ``TestClient``, and a DB close
in teardown so the process exits cleanly.
"""

import asyncio

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

    from app.db import database  # noqa: F401 — imported for teardown close

    from fastapi.testclient import TestClient

    from app.main import app

    with TestClient(app) as c:
        # Clear any simulator handles leaked from an earlier test in the session.
        if getattr(app.state, "sc_simulator_task", None) is not None:
            app.state.sc_simulator_task.cancel()
        app.state.sc_simulator = None
        app.state.sc_simulator_task = None
        yield c

    async def _close():
        from app.db import database as _db

        await _db.close_db()

    _run(_close())


BASE = "/api/v1/source-comparison"


def test_get_config_returns_fields(client):
    resp = client.get(f"{BASE}/config")
    assert resp.status_code == 200
    body = resp.json()
    assert body["total_count"] == len(body["fields"])
    assert body["total_count"] > 0

    by_name = {f["field_name"]: f for f in body["fields"]}
    # A numeric field carries a positive default threshold.
    assert "diameter" in by_name
    assert by_name["diameter"]["type"] == "numeric"
    assert by_name["diameter"]["threshold"] == pytest.approx(0.10)
    assert by_name["diameter"]["in_scope"] is True


def test_put_field_default_changes_threshold_and_audits(client):
    # Edit the diameter default threshold.
    resp = client.put(
        f"{BASE}/config/field/diameter",
        json={"threshold": 0.25, "changed_by": "reviewer-a", "note": "tighten"},
    )
    assert resp.status_code == 200
    assert resp.json()["threshold"] == pytest.approx(0.25)

    # The persisted config reflects the change.
    cfg = client.get(f"{BASE}/config").json()
    diameter = next(f for f in cfg["fields"] if f["field_name"] == "diameter")
    assert diameter["threshold"] == pytest.approx(0.25)

    # An audit row for the change is visible, newest first.
    audit = client.get(f"{BASE}/config/audit").json()
    assert audit["total_count"] >= 1
    assert audit["limit"] == 50
    assert audit["offset"] == 0
    top = audit["data"][0]
    assert top["change_type"] == "field_default"
    assert top["field_name"] == "diameter"
    assert top["new_value"] == "0.25"
    assert top["changed_by"] == "reviewer-a"


def test_put_field_default_requires_changed_by(client):
    resp = client.put(
        f"{BASE}/config/field/diameter",
        json={"threshold": 0.3},
    )
    assert resp.status_code == 422
    assert "changed_by" in resp.json()["detail"]


def test_post_override_then_list_returns_it(client):
    resp = client.post(
        f"{BASE}/config/overrides",
        json={
            "part_number": "PN-1",
            "field_name": "diameter",
            "threshold": 0.5,
            "changed_by": "reviewer-b",
        },
    )
    assert resp.status_code == 200
    assert resp.json()["threshold"] == pytest.approx(0.5)

    listing = client.get(f"{BASE}/config/overrides?part_number=PN-1").json()
    assert listing["total_count"] == 1
    ov = listing["data"][0]
    assert ov["part_number"] == "PN-1"
    assert ov["field_name"] == "diameter"
    assert ov["threshold"] == pytest.approx(0.5)


def test_post_override_negative_threshold_is_422(client):
    resp = client.post(
        f"{BASE}/config/overrides",
        json={
            "part_number": "PN-1",
            "field_name": "diameter",
            "threshold": -1.0,
            "changed_by": "reviewer-b",
        },
    )
    assert resp.status_code == 422
    assert "threshold" in resp.json()["detail"]


def test_delete_override_returns_deleted_true(client):
    # Seed an override, then delete it.
    client.post(
        f"{BASE}/config/overrides",
        json={
            "part_number": "PN-2",
            "field_name": "thickness",
            "threshold": 0.2,
            "changed_by": "reviewer-c",
        },
    )
    resp = client.delete(
        f"{BASE}/config/overrides",
        params={
            "part_number": "PN-2",
            "field_name": "thickness",
            "changed_by": "reviewer-c",
        },
    )
    assert resp.status_code == 200
    assert resp.json() == {"deleted": True}

    # A second delete finds nothing to remove.
    resp = client.delete(
        f"{BASE}/config/overrides",
        params={
            "part_number": "PN-2",
            "field_name": "thickness",
            "changed_by": "reviewer-c",
        },
    )
    assert resp.json() == {"deleted": False}
