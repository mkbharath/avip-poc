"""Runtime-editable numeric threshold configuration (source-comparison feature).

This service is the **single source of truth for the effective numeric
threshold** applied to a given ``(part_number, field_name)`` during comparison.
It layers two configurable levels on top of the seeded defaults in
``sc_config.py``:

  1. **Global per-FIELD default** — persisted in the ``sc_comparison_config``
     row (id ``'default'``) inside its ``fields`` JSON (``FieldConfig.threshold``
     / ``FieldConfig.in_scope``). This is the org-wide default for a field,
     editable at runtime and surviving restart.
  2. **Optional per-PART override** — a row in ``sc_threshold_overrides`` keyed
     by ``(part_number, field_name)``. When present it wins over the field
     default for that specific part.

Every mutation — a field-default change, a part-override set/delete, or a
field-scope (in_scope) change — writes an **append-only** ``sc_config_audit``
row capturing who / when / old→new (Req: full auditability). The audit table is
never updated or deleted from; each change is a fresh immutable row, mirroring
the ``sc_review_audit`` pattern in ``sc_review.py``.

Resolution order (``resolve_threshold``), the one rule the comparison engine
relies on:

    per-part override  →  persisted field default  →  None

A ``None`` result is passed through unchanged so the comparison engine routes an
unresolved threshold to manual review rather than silently defaulting (see
``comparison.check_numeric``). When no persisted config / override is reachable
(e.g. a pure unit test with no DB), ``resolve_threshold`` gracefully falls back
to the in-memory field default from ``sc_config`` so DB-less comparison keeps
working.

No HTTP routes and no comparison wiring live here — this module is the backend
foundation only. The comparison engine calls :func:`resolve_threshold`; API
endpoints (later task) call the mutation + list helpers.
"""

from __future__ import annotations

import json
import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_db
from app.services.sc_config import (
    ComparisonConfig,
    FieldConfig,
    comparison_config,
    default_config,
)

logger = logging.getLogger("app.source_comparison.threshold_config")

# The single persisted comparison-config row id (mirrors the schema default).
CONFIG_ROW_ID = "default"

# Audit change_type tags (kept in one place so callers/tests share the vocab).
CHANGE_FIELD_DEFAULT = "field_default"
CHANGE_PART_OVERRIDE_SET = "part_override_set"
CHANGE_PART_OVERRIDE_DELETE = "part_override_delete"
CHANGE_FIELD_SCOPE = "field_scope"


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _new_id() -> str:
    """Generate a uuid string id, matching AVIP id conventions."""
    return str(uuid.uuid4())


def _validate_threshold(threshold: float) -> float:
    """Validate that ``threshold`` is a positive number; return it as ``float``.

    A threshold must be a strictly positive numeric deviation — zero or negative
    values, booleans, and non-numeric inputs are rejected with ``ValueError`` so
    a bad value never reaches persistence or comparison.
    """
    if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
        raise ValueError(f"threshold must be a positive number, got {threshold!r}")
    value = float(threshold)
    if not (value > 0) or value != value or value in (float("inf"), float("-inf")):
        raise ValueError(f"threshold must be a positive finite number, got {threshold!r}")
    return value


# ── Persisted config load / seed ─────────────────────────────────────────────


async def load_config() -> ComparisonConfig:
    """Load the persisted :class:`ComparisonConfig` (row id ``'default'``).

    If the ``sc_comparison_config`` row is absent, seed it from
    :func:`sc_config.default_config` and persist it, then return that config.
    This makes the persisted config self-initialising: the first call after a
    fresh DB writes the seed so subsequent edits have a row to upsert into.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT common_key, fields, llm_provider, assumptions
             FROM sc_comparison_config
            WHERE id = ?""",
        (CONFIG_ROW_ID,),
    )
    row = await cursor.fetchone()

    if row is None:
        config = default_config()
        await _seed_config(db, config)
        return config

    return _row_to_config(row)


async def _seed_config(db: Any, config: ComparisonConfig) -> None:
    """Persist the seed config into the single ``sc_comparison_config`` row."""
    await db.execute(
        """INSERT INTO sc_comparison_config
               (id, common_key, fields, llm_provider, assumptions, updated_at)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(id) DO NOTHING""",
        (
            CONFIG_ROW_ID,
            json.dumps(config.common_key),
            json.dumps(_fields_to_json(config.fields)),
            config.llm_provider,
            json.dumps([a.model_dump() for a in config.assumptions]),
            _now_iso(),
        ),
    )
    await db.commit()


def _fields_to_json(fields: dict[str, FieldConfig]) -> dict[str, dict]:
    """Serialise the ``fields`` map to the JSON shape stored in the config row."""
    out: dict[str, dict] = {}
    for name, fc in fields.items():
        out[name] = {
            "type": fc.type.value,
            "in_scope": fc.in_scope,
            "threshold": fc.threshold,
        }
    return out


def _row_to_config(row: Any) -> ComparisonConfig:
    """Build a :class:`ComparisonConfig` from a persisted config row.

    The ``fields`` JSON is parsed back into ``FieldConfig`` objects and the
    per-field thresholds are also surfaced on the top-level
    ``numeric_thresholds`` map so both access paths stay consistent with the
    in-memory ``default_config`` shape.
    """
    common_key = json.loads(row["common_key"]) if row["common_key"] else []
    raw_fields = json.loads(row["fields"]) if row["fields"] else {}
    fields: dict[str, FieldConfig] = {}
    numeric_thresholds: dict[str, float] = {}
    for name, spec in raw_fields.items():
        fc = FieldConfig(
            type=spec["type"],
            in_scope=spec.get("in_scope", True),
            threshold=spec.get("threshold"),
        )
        fields[name] = fc
        if fc.threshold is not None:
            numeric_thresholds[name] = fc.threshold

    from app.services.sc_config import AssumptionItem

    raw_assumptions = json.loads(row["assumptions"]) if row["assumptions"] else []
    assumptions = [AssumptionItem(**a) for a in raw_assumptions]

    return ComparisonConfig(
        common_key=common_key,
        fields=fields,
        numeric_thresholds=numeric_thresholds,
        llm_provider=row["llm_provider"],
        assumptions=assumptions,
    )


# ── Mutations (each writes an append-only audit row) ─────────────────────────


async def _write_audit(
    db: Any,
    *,
    change_type: str,
    field_name: str | None,
    part_number: str | None,
    old_value: str | None,
    new_value: str | None,
    changed_by: str,
    note: str | None,
) -> str:
    """Append an immutable :data:`sc_config_audit` row; return its id.

    The audit table is append-only — every change (including re-setting the same
    value) writes a fresh row capturing who (``changed_by``), when
    (``changed_at``), and old→new. ``old_value`` / ``new_value`` are stored as
    strings so the trail is uniform across change types.
    """
    audit_id = _new_id()
    await db.execute(
        """INSERT INTO sc_config_audit
               (id, change_type, field_name, part_number, old_value, new_value,
                changed_by, changed_at, note)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (
            audit_id,
            change_type,
            field_name,
            part_number,
            old_value,
            new_value,
            changed_by,
            _now_iso(),
            note,
        ),
    )
    return audit_id


async def set_field_default(
    field_name: str,
    threshold: float | None,
    in_scope: bool | None,
    changed_by: str,
    note: str | None = None,
) -> FieldConfig:
    """Upsert a field's default ``threshold`` and/or ``in_scope`` in the config.

    Both ``threshold`` and ``in_scope`` are optional edits: pass a value to
    change it, or ``None`` to leave that aspect untouched. A non-``None``
    ``threshold`` is validated as a positive number (:func:`_validate_threshold`)
    before it is persisted. A distinct audit row is written for each aspect that
    changes — ``field_default`` for a threshold edit, ``field_scope`` for an
    in_scope edit — each capturing old→new.

    Returns the updated :class:`FieldConfig`. Raises ``ValueError`` on an invalid
    threshold or an unknown field.
    """
    if threshold is not None:
        threshold = _validate_threshold(threshold)

    db = await get_db()
    config = await load_config()

    old_fc = config.fields.get(field_name)
    if old_fc is None:
        raise ValueError(f"Unknown field {field_name!r}; not present in config.")

    old_threshold = old_fc.threshold
    old_in_scope = old_fc.in_scope

    new_threshold = old_threshold if threshold is None else threshold
    new_in_scope = old_in_scope if in_scope is None else in_scope

    updated_fc = FieldConfig(
        type=old_fc.type, in_scope=new_in_scope, threshold=new_threshold
    )
    config.fields[field_name] = updated_fc

    # Persist the whole fields map back into the single config row.
    await db.execute(
        """UPDATE sc_comparison_config
              SET fields = ?, updated_at = ?
            WHERE id = ?""",
        (json.dumps(_fields_to_json(config.fields)), _now_iso(), CONFIG_ROW_ID),
    )

    # Audit each aspect that actually changed.
    if threshold is not None and new_threshold != old_threshold:
        await _write_audit(
            db,
            change_type=CHANGE_FIELD_DEFAULT,
            field_name=field_name,
            part_number=None,
            old_value=None if old_threshold is None else str(old_threshold),
            new_value=str(new_threshold),
            changed_by=changed_by,
            note=note,
        )
    if in_scope is not None and new_in_scope != old_in_scope:
        await _write_audit(
            db,
            change_type=CHANGE_FIELD_SCOPE,
            field_name=field_name,
            part_number=None,
            old_value=str(old_in_scope),
            new_value=str(new_in_scope),
            changed_by=changed_by,
            note=note,
        )

    await db.commit()

    logger.info(
        "Field default updated: field=%s threshold=%s in_scope=%s changed_by=%s",
        field_name,
        new_threshold,
        new_in_scope,
        changed_by,
    )
    return updated_fc


async def set_part_override(
    part_number: str,
    field_name: str,
    threshold: float,
    changed_by: str,
    note: str | None = None,
) -> None:
    """Upsert a per-part threshold override and audit the old→new change.

    The override is keyed ``(part_number, field_name)`` and wins over the field
    default for that part during resolution. ``threshold`` is validated as a
    positive number. The prior override value (if any) is captured as the audit
    ``old_value`` so a first set records ``None → new`` and a re-set records the
    previous value → new.
    """
    threshold = _validate_threshold(threshold)

    db = await get_db()

    cursor = await db.execute(
        """SELECT threshold FROM sc_threshold_overrides
            WHERE part_number = ? AND field_name = ?""",
        (part_number, field_name),
    )
    existing = await cursor.fetchone()
    old_value = None if existing is None else str(existing["threshold"])

    await db.execute(
        """INSERT INTO sc_threshold_overrides
               (id, part_number, field_name, threshold, updated_at)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(part_number, field_name) DO UPDATE SET
               threshold = excluded.threshold,
               updated_at = excluded.updated_at""",
        (_new_id(), part_number, field_name, threshold, _now_iso()),
    )

    await _write_audit(
        db,
        change_type=CHANGE_PART_OVERRIDE_SET,
        field_name=field_name,
        part_number=part_number,
        old_value=old_value,
        new_value=str(threshold),
        changed_by=changed_by,
        note=note,
    )
    await db.commit()

    logger.info(
        "Part override set: part=%s field=%s threshold=%s changed_by=%s",
        part_number,
        field_name,
        threshold,
        changed_by,
    )


async def delete_part_override(
    part_number: str,
    field_name: str,
    changed_by: str,
    note: str | None = None,
) -> bool:
    """Delete a per-part override and audit the removal (old→new is value→None).

    Returns ``True`` if an override row existed and was deleted, ``False`` if
    there was nothing to delete. An audit row is written only when a row is
    actually removed, capturing the removed value as ``old_value`` and ``None``
    as ``new_value``.
    """
    db = await get_db()

    cursor = await db.execute(
        """SELECT threshold FROM sc_threshold_overrides
            WHERE part_number = ? AND field_name = ?""",
        (part_number, field_name),
    )
    existing = await cursor.fetchone()
    if existing is None:
        return False

    old_value = str(existing["threshold"])
    await db.execute(
        """DELETE FROM sc_threshold_overrides
            WHERE part_number = ? AND field_name = ?""",
        (part_number, field_name),
    )
    await _write_audit(
        db,
        change_type=CHANGE_PART_OVERRIDE_DELETE,
        field_name=field_name,
        part_number=part_number,
        old_value=old_value,
        new_value=None,
        changed_by=changed_by,
        note=note,
    )
    await db.commit()

    logger.info(
        "Part override deleted: part=%s field=%s changed_by=%s",
        part_number,
        field_name,
        changed_by,
    )
    return True


# ── Read helpers ─────────────────────────────────────────────────────────────


async def list_overrides(part_number: str | None = None) -> list[dict[str, Any]]:
    """Return per-part overrides — all, or scoped to a single ``part_number``.

    Each item is a dict ``{id, part_number, field_name, threshold, updated_at}``.
    Ordered by part then field for stable output.
    """
    db = await get_db()
    if part_number is None:
        cursor = await db.execute(
            """SELECT id, part_number, field_name, threshold, updated_at
                 FROM sc_threshold_overrides
                ORDER BY part_number ASC, field_name ASC"""
        )
    else:
        cursor = await db.execute(
            """SELECT id, part_number, field_name, threshold, updated_at
                 FROM sc_threshold_overrides
                WHERE part_number = ?
                ORDER BY field_name ASC""",
            (part_number,),
        )
    rows = await cursor.fetchall()
    return [
        {
            "id": r["id"],
            "part_number": r["part_number"],
            "field_name": r["field_name"],
            "threshold": r["threshold"],
            "updated_at": r["updated_at"],
        }
        for r in rows
    ]


async def count_audit() -> int:
    """Return the total number of append-only ``sc_config_audit`` rows.

    Companion to :func:`list_audit` so a paginated endpoint can report the full
    ``total_count`` (across all pages) alongside a single page — mirroring the
    review-queue envelope (``count_pending`` + ``list_pending`` in
    ``sc_review.py``).
    """
    db = await get_db()
    cursor = await db.execute("SELECT COUNT(*) FROM sc_config_audit")
    row = await cursor.fetchone()
    try:
        return int(row[0]) if row is not None else 0
    except (TypeError, KeyError, IndexError):
        return 0


async def list_audit(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """Return a page of config-audit rows, newest first (Req: full auditability).

    ``limit`` / ``offset`` paginate the append-only ``sc_config_audit`` trail
    ordered by ``changed_at`` descending (ties broken by ``id`` for stability).
    Each item is the full audit row so the UI can render who/when/old→new.
    """
    page_limit = max(1, int(limit))
    page_offset = max(0, int(offset))
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, change_type, field_name, part_number, old_value, new_value,
                  changed_by, changed_at, note
             FROM sc_config_audit
            ORDER BY changed_at DESC, id DESC
            LIMIT ? OFFSET ?""",
        (page_limit, page_offset),
    )
    rows = await cursor.fetchall()
    return [
        {
            "id": r["id"],
            "change_type": r["change_type"],
            "field_name": r["field_name"],
            "part_number": r["part_number"],
            "old_value": r["old_value"],
            "new_value": r["new_value"],
            "changed_by": r["changed_by"],
            "changed_at": r["changed_at"],
            "note": r["note"],
        }
        for r in rows
    ]


# ── Effective-threshold resolution (single source of truth) ──────────────────


async def resolve_threshold(part_number: str | None, field_name: str) -> float | None:
    """Resolve the effective numeric threshold for ``(part_number, field_name)``.

    Resolution order — the one rule the comparison engine relies on:

        per-part override  →  persisted field default  →  None

    A per-part override (when ``part_number`` is given and a row exists) wins.
    Otherwise the persisted field default from ``sc_comparison_config`` is used.
    ``None`` is returned when neither resolves, and is passed through unchanged so
    ``comparison.check_numeric`` routes an unresolved threshold to manual review
    rather than silently defaulting.

    Graceful degradation: if the DB / persisted config is unreachable (e.g. a
    pure unit test running comparison logic without a DB), this falls back to the
    in-memory field default from ``sc_config`` so DB-less comparison keeps
    working and behavior matches today's defaults when no override exists.
    """
    # 1) Per-part override wins when present.
    if part_number is not None:
        try:
            db = await get_db()
            cursor = await db.execute(
                """SELECT threshold FROM sc_threshold_overrides
                    WHERE part_number = ? AND field_name = ?""",
                (part_number, field_name),
            )
            row = await cursor.fetchone()
            if row is not None:
                return float(row["threshold"])
        except Exception:  # noqa: BLE001 — DB unavailable → fall through to defaults
            logger.debug(
                "resolve_threshold: override lookup unavailable for part=%s "
                "field=%s — falling back to field default",
                part_number,
                field_name,
            )

    # 2) Persisted field default.
    try:
        config = await load_config()
        return _field_default_from_config(config, field_name)
    except Exception:  # noqa: BLE001 — no DB/persisted config → in-memory default
        logger.debug(
            "resolve_threshold: persisted config unavailable for field=%s — "
            "using in-memory default",
            field_name,
        )
        return _field_default_from_config(comparison_config, field_name)


def _field_default_from_config(config: ComparisonConfig, field_name: str) -> float | None:
    """Field-default resolution mirroring ``comparison._field_threshold``.

    Prefers ``FieldConfig.threshold`` on the field; falls back to the top-level
    ``numeric_thresholds`` map; returns ``None`` (unresolved) if neither is set.
    Kept here to avoid a comparison→threshold_config→comparison import cycle.
    """
    fc = config.fields.get(field_name)
    if fc is not None and fc.threshold is not None:
        return fc.threshold
    return config.numeric_thresholds.get(field_name)
