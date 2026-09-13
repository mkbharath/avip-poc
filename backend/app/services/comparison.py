"""Comparison service — field classification and the three checks (Req 3, 4).

This module is the **pure comparison logic** for the source-comparison feature:
given an aligned group and an in-scope field, it decides *whether* the sources
disagree and, if so, produces a :class:`Discrepancy` carrying the provenance of
the check that found the disagreement. It has **no persistence and no DB writes**
— those belong to ``compare_group`` (task 4.3). Every function here is a pure
(or, for the LLM check, effect-isolated) function returning a ``Discrepancy`` or
``None``.

Field type drives dispatch (Req 3.6): :func:`classify_field` reads the field's
configured type rather than consulting a hardcoded list, and out-of-scope fields
are skipped (Req 3.7). Each check corresponds to one field-type family:

  * :func:`check_exact` — categorical / identifier fields. Flags iff the values
    present across sources are not all equal (Req 4.1, 4.5). Provenance
    ``exact-match``.
  * :func:`check_numeric` — numeric fields, measured against the **SHQ**
    reference (assumed — pending client confirmation; see ``sc_config``). Flags
    iff a source's absolute deviation from SHQ *exceeds* the per-field threshold.
    The boundary is **strict**: a deviation exactly equal to the threshold does
    NOT flag (Property 2, Req 4.2, 4.5, 8.2). Provenance ``numeric-threshold``.
    An unresolved threshold (``None``) or an absent SHQ reference is routed to
    manual review rather than silently agreeing or defaulting.
  * :func:`check_free_text` — free-text fields only (Req 3.3, 4.3). Delegates the
    judgement to the pluggable :class:`LLMProvider`. Flags per the provider's
    ``differ`` result with provenance ``llm``. On **any** provider exception the
    field is NOT treated as agreeing: a flagged discrepancy with provenance
    ``llm-unavailable`` is produced and routed to manual review (Req 5.5,
    Property 7).

Every produced :class:`Discrepancy` carries a **non-empty provenance** and a
per-source ``values`` dict (Property 3), and enters as ``pending`` — the review
gate (task 5.x) is the only path to ``confirmed`` (Property 7). ``compare_group``
dispatch and persistence to ``sc_discrepancies`` are a separate later task (4.3)
and are intentionally NOT implemented here.
"""

from __future__ import annotations

import json
import logging
import math
import uuid
from datetime import datetime, timezone
from typing import Any

from app.db.database import get_db
from app.models.source_comparison import (
    AlignedGroup,
    Discrepancy,
    FieldType,
    Provenance,
    ReviewState,
    SourceType,
)
from app.services.llm_provider import LLMProvider
from app.services.sc_config import ComparisonConfig, comparison_config

logger = logging.getLogger("app.source_comparison.comparison")

# The source designated as the numeric reference / source-of-truth for
# numeric-threshold checks (assumed — pending client confirmation; recorded in
# the ``shq_numeric_benchmark`` assumption item in sc_config).
NUMERIC_REFERENCE_SOURCE = SourceType.SHQ


# ── Helpers ──────────────────────────────────────────────────────────────────


def _new_discrepancy_id() -> str:
    """Generate a discrepancy id (uuid string), matching AVIP id conventions."""
    return str(uuid.uuid4())


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _collect_present_values(
    group: AlignedGroup, field: str
) -> dict[str, Any]:
    """Collect ``{source: value}`` for every source whose record has ``field``.

    Only records that actually carry the field are included, so a source that
    simply did not report the field is treated as *absent* for that field rather
    than as a ``None`` value. When multiple records exist for one source (should
    not normally happen for an aligned group) the last-seen value wins, mirroring
    a straightforward dict build over the group's records.
    """
    values: dict[str, Any] = {}
    for record in group.records:
        if field in record.fields:
            values[record.source.value] = record.fields[field]
    return values


def _make_discrepancy(
    group: AlignedGroup,
    field: str,
    field_type: FieldType,
    values: dict[str, Any],
    provenance: Provenance,
) -> Discrepancy:
    """Build a pending :class:`Discrepancy` with non-empty provenance (Property 3).

    ``values`` is the per-source values dict carried onto the discrepancy so the
    report can render each present source's value (Req 7.2, Property 8). The
    discrepancy always enters as ``pending`` — only the review gate transitions
    it to ``confirmed`` (Req 5.4, Property 7).
    """
    return Discrepancy(
        id=_new_discrepancy_id(),
        group_id=group.id,
        part_number=group.part_number,
        lot_number=group.lot_number,
        field_name=field,
        field_type=field_type,
        values=dict(values),
        provenance=provenance,
        review_state=ReviewState.PENDING,
    )


# ── Field classification (Req 3.6, 3.7) ──────────────────────────────────────


def classify_field(field_name: str, config: ComparisonConfig) -> FieldType | None:
    """Return the configured :class:`FieldType` for ``field_name``, or ``None``.

    The comparison check a field receives is determined by the field's
    *configured* type (Req 3.6), never a hardcoded field list. A field that is
    not present in the configuration, or is present but marked ``in_scope=False``,
    is out of scope and returns ``None`` so the caller skips it (Req 3.7).
    """
    field_config = config.fields.get(field_name)
    if field_config is None:
        return None
    if not field_config.in_scope:
        return None
    return field_config.type


# ── Exact-match check — categorical / identifier (Req 4.1, 4.5) ───────────────


def check_exact(group: AlignedGroup, field: str) -> Discrepancy | None:
    """Exact-match check for categorical / identifier fields (Req 4.1, 4.5).

    Collects the field's value from each source that reported it and flags the
    field **iff** those values are not all equal across the present sources.
    Fewer than two present sources means there is nothing to compare, so no
    discrepancy is produced. Provenance is ``exact-match``; the per-source values
    dict is always carried (Property 3, Property 8).
    """
    values = _collect_present_values(group, field)
    if len(values) < 2:
        return None

    distinct = {_exact_key(v) for v in values.values()}
    if len(distinct) <= 1:
        return None  # all present sources agree — do not flag (Req 4.5)

    logger.info(
        "exact-match discrepancy: group_id=%s field=%s values=%s",
        group.id,
        field,
        values,
    )
    return _make_discrepancy(
        group, field, FieldType.CATEGORICAL, values, Provenance.EXACT
    )


def _exact_key(value: Any) -> Any:
    """Normalize a categorical/identifier value for exact comparison.

    Strings are compared case-insensitively after trimming surrounding
    whitespace, so ``" A36 "`` and ``"a36"`` are treated as equal; non-string
    values are compared by their raw value. This keeps trivial formatting
    differences from being reported as genuine discrepancies.
    """
    if isinstance(value, str):
        return value.strip().casefold()
    return value


# ── Numeric-threshold check — vs SHQ reference (Req 4.2, 4.5, 8.2) ────────────


def check_numeric(
    group: AlignedGroup, field: str, threshold: float | None
) -> Discrepancy | None:
    """Numeric-threshold check measured against the SHQ reference (Req 4.2, 4.5).

    SHQ is the reference / source-of-truth (assumed — pending client
    confirmation). For each *other* present source the absolute deviation
    ``|value - SHQ_value|`` is compared to the per-field ``threshold``. The field
    is flagged **iff** at least one deviation *exceeds* the threshold. The
    boundary is **strict**: a deviation exactly equal to the threshold does NOT
    flag (Property 2). Provenance is ``numeric-threshold``.

    Documented edge behavior — surfaced for manual review rather than silently
    agreeing or defaulting:

    * ``threshold is None`` (unresolved per-field threshold): the field is routed
      to manual review as a flagged ``numeric-threshold`` discrepancy rather than
      defaulting to a threshold — an unresolved config item must never be
      silently substituted (Req 8.5).
    * **SHQ reference absent** (SHQ did not report this numeric field): there is
      no reference to measure against. If two or more other sources reported the
      field, fall back to the max-min *spread* across those sources vs the
      threshold; if a threshold is present and the spread is within it, no flag.
      If fewer than two comparable values exist, or the threshold is unresolved,
      the field is routed to manual review as a flagged discrepancy so the gap is
      not silently dropped.
    * Non-numeric / unparseable values are treated as not comparable and routed
      to manual review rather than crashing or agreeing.
    """
    values = _collect_present_values(group, field)
    if len(values) < 2:
        return None

    ref_key = NUMERIC_REFERENCE_SOURCE.value
    ref_present = ref_key in values

    # Parse all present values to floats; unparseable values are recorded so the
    # field can be routed to manual review rather than silently ignored.
    numeric: dict[str, float] = {}
    unparseable: list[str] = []
    for source, raw in values.items():
        parsed = _to_float(raw)
        if parsed is None:
            unparseable.append(source)
        else:
            numeric[source] = parsed

    # Unparseable numeric values → cannot compare reliably → manual review.
    if unparseable:
        logger.warning(
            "numeric check: unparseable value(s) for group_id=%s field=%s "
            "sources=%s — routing to manual review",
            group.id,
            field,
            unparseable,
        )
        return _make_discrepancy(
            group, field, FieldType.NUMERIC, values, Provenance.NUMERIC
        )

    # Unresolved threshold must never be silently defaulted (Req 8.5) → review.
    if threshold is None:
        logger.warning(
            "numeric check: threshold unresolved (None) for group_id=%s field=%s "
            "— routing to manual review rather than defaulting",
            group.id,
            field,
        )
        return _make_discrepancy(
            group, field, FieldType.NUMERIC, values, Provenance.NUMERIC
        )

    if ref_present:
        ref_value = numeric[ref_key]
        exceeded = any(
            _exceeds(abs(v - ref_value), threshold)
            for source, v in numeric.items()
            if source != ref_key
        )
        if not exceeded:
            return None  # all within threshold of SHQ — do not flag (Req 4.5)
        logger.info(
            "numeric-threshold discrepancy (vs SHQ): group_id=%s field=%s "
            "ref=%s threshold=%s values=%s",
            group.id,
            field,
            ref_value,
            threshold,
            values,
        )
        return _make_discrepancy(
            group, field, FieldType.NUMERIC, values, Provenance.NUMERIC
        )

    # SHQ reference absent: fall back to max-min spread across the other sources.
    if len(numeric) < 2:
        logger.warning(
            "numeric check: SHQ reference absent and fewer than two comparable "
            "values for group_id=%s field=%s — routing to manual review",
            group.id,
            field,
        )
        return _make_discrepancy(
            group, field, FieldType.NUMERIC, values, Provenance.NUMERIC
        )

    spread = max(numeric.values()) - min(numeric.values())
    if _exceeds(spread, threshold):
        logger.info(
            "numeric-threshold discrepancy (SHQ absent, spread fallback): "
            "group_id=%s field=%s spread=%s threshold=%s values=%s",
            group.id,
            field,
            spread,
            threshold,
            values,
        )
        return _make_discrepancy(
            group, field, FieldType.NUMERIC, values, Provenance.NUMERIC
        )
    return None  # spread within threshold — do not flag


def _exceeds(deviation: float, threshold: float) -> bool:
    """Return whether ``deviation`` strictly exceeds ``threshold`` (Property 2).

    The threshold boundary is strict — a deviation exactly *equal* to the
    threshold does NOT flag. Binary floating-point cannot represent most decimal
    thresholds exactly (e.g. ``10.05 - 10.00`` evaluates to
    ``0.05000000000000071``), so a naive ``deviation > threshold`` would spuriously
    flag a deviation that is mathematically *at* the boundary. Treating deviations
    that are ``math.isclose`` to the threshold as "at the boundary" (not
    exceeding) keeps the strict-boundary property robust against representation
    error while still flagging any genuinely larger deviation.
    """
    if math.isclose(deviation, threshold, rel_tol=1e-9, abs_tol=1e-12):
        return False
    return deviation > threshold


def _to_float(value: Any) -> float | None:
    """Best-effort parse of a value to ``float``; ``None`` if not parseable.

    Booleans are rejected (a bool is not a meaningful numeric measurement) so a
    stray ``True`` is treated as unparseable and routed to review.
    """
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        try:
            return float(value.strip())
        except ValueError:
            return None
    return None


# ── Free-text check — LLM-assisted, free-text only (Req 3.3, 4.3, 5.5) ────────


async def check_free_text(
    group: AlignedGroup, field: str, llm: LLMProvider
) -> Discrepancy | None:
    """LLM-assisted free-text check — free-text fields only (Req 3.3, 4.3).

    Collects the field's value from each present source and asks the pluggable
    :class:`LLMProvider` whether the values disagree in substance. The field is
    flagged **iff** the provider reports ``differ=True``; provenance ``llm``. The
    resulting discrepancy always enters as ``pending`` — never auto-confirmed
    (Req 5.4, Property 7).

    On **any** provider exception the field is NOT treated as agreeing: a flagged
    discrepancy with provenance ``llm-unavailable`` is produced and routed to
    manual review (Req 5.5, Property 7). This guarantees a provider outage never
    silently hides a potential mismatch.

    When more than two sources report the field, each non-first value is compared
    against the first present value; a differ on any pair flags the field. A
    single provider failure across those comparisons yields ``llm-unavailable``.
    """
    values = _collect_present_values(group, field)
    if len(values) < 2:
        return None

    ordered = list(values.items())
    baseline_source, baseline_value = ordered[0]

    try:
        differ = False
        for source, value in ordered[1:]:
            result = await llm.compare_text(_as_text(baseline_value), _as_text(value))
            if result.differ:
                differ = True
                logger.info(
                    "llm free-text discrepancy: group_id=%s field=%s "
                    "baseline=%s vs %s rationale=%s",
                    group.id,
                    field,
                    baseline_source,
                    source,
                    result.rationale,
                )
                break
    except Exception:  # noqa: BLE001 — any provider failure routes to review
        logger.exception(
            "llm provider failure for group_id=%s field=%s — routing to manual "
            "review with provenance llm-unavailable",
            group.id,
            field,
        )
        return _make_discrepancy(
            group, field, FieldType.FREE_TEXT, values, Provenance.LLM_UNAVAILABLE
        )

    if not differ:
        return None  # provider judged the free-text values equivalent

    return _make_discrepancy(
        group, field, FieldType.FREE_TEXT, values, Provenance.LLM
    )


def _as_text(value: Any) -> str | None:
    """Coerce a free-text field value to ``str`` (or ``None``) for the provider."""
    if value is None:
        return None
    return str(value)


# ── Group comparison dispatch + persistence (task 4.3, Req 4.1-4.5, 5.4) ──────
#
# ``compare_group`` is the orchestration layer over the pure checks above. It
# walks every in-scope field of an aligned group, dispatches each to the check
# matching its configured type, collects the produced discrepancies (each already
# carrying non-empty provenance — Property 3), and persists them to
# ``sc_discrepancies`` as ``pending`` (Req 5.4). The LLM is invoked **only** for
# free-text fields (Property 4) — numeric/categorical/identifier never touch it.
#
# Idempotency + recompare semantics (design: "idempotent recompare",
# ``UNIQUE(group_id, field_name)``). A group can be compared many times as it
# streams to completeness, so persistence is an **upsert** keyed on
# ``(group_id, field_name)``:
#
#   * FIELD WITH NO EXISTING ROW, now discrepant  → INSERT a fresh ``pending``
#     row (new id, ISO ``created_at``).
#   * FIELD WHOSE ROW ALREADY EXISTS, still discrepant → ON CONFLICT DO UPDATE:
#     refresh ``field_type``, ``values`` (the quoted column), and ``provenance``
#     so the row reflects the latest source values/check, but **PRESERVE the
#     existing ``review_state``**. A reviewer's ``confirmed`` / ``dismissed``
#     decision is NEVER reset back to ``pending`` on recompare (Req 5.4,
#     Property 7). ``id`` and ``created_at`` are preserved.
#   * FIELD THAT PREVIOUSLY FLAGGED BUT NOW AGREES (no discrepancy produced this
#     run) → documented "agree-again" behavior: a still-``pending`` row is
#     **cleared** (deleted), because it no longer reflects a real disagreement
#     and leaving it would keep a stale item in the review queue; a **decided**
#     row (``confirmed`` / ``dismissed``) is **left intact**, preserving the
#     reviewer's decision and keeping Property 5 consistent (only ``confirmed``
#     reach the report — a confirmed finding stays confirmed, a dismissed one
#     stays out). This clearing is scoped strictly to fields that were checked
#     this run and produced no discrepancy; it never touches other fields.
#
# The return value is the list of **current** discrepancies for the group as
# persisted (reflecting preserved review states), so callers see the effective
# state after the upsert rather than only the freshly-produced flags.


def _make_discrepancy_for_field(
    group: AlignedGroup,
    field: str,
    field_type: FieldType,
    threshold: float | None,
    llm: LLMProvider,
) -> Discrepancy | None:
    """Synchronous dispatch for the non-LLM field types (Property 4).

    Kept separate from :func:`compare_group` so the async free-text path is the
    only one that awaits. Numeric/categorical/identifier fields never invoke the
    LLM.
    """
    if field_type is FieldType.NUMERIC:
        return check_numeric(group, field, threshold)
    if field_type in (FieldType.CATEGORICAL, FieldType.IDENTIFIER):
        return check_exact(group, field)
    # FREE_TEXT is handled by the async caller; anything else is out of scope.
    return None


async def compare_group(
    group: AlignedGroup,
    config: ComparisonConfig | None = None,
    llm: LLMProvider | None = None,
) -> list[Discrepancy]:
    """Dispatch every in-scope field, persist discrepancies, return the current set.

    For each field carried by the group's records, :func:`classify_field`
    decides scope + type (out-of-scope fields are skipped, Req 3.7). Dispatch is
    type-directed (Req 4.1-4.3, Property 4):

      * NUMERIC → :func:`check_numeric` with the per-field threshold from config.
      * CATEGORICAL / IDENTIFIER → :func:`check_exact`.
      * FREE_TEXT → :func:`check_free_text` (the **only** LLM path).

    Produced discrepancies (each carrying non-empty provenance, Property 3) are
    persisted to ``sc_discrepancies`` as ``pending`` via an idempotent upsert on
    ``(group_id, field_name)``; fields that were checked but now agree have any
    still-``pending`` row cleared while decided rows are preserved (see module
    notes). Returns the current persisted discrepancies for the group.

    ``config`` defaults to the module-level ``comparison_config``; ``llm``
    defaults to ``get_llm_provider(config)`` so free-text comparison always has a
    working provider.
    """
    # Imported here to avoid a circular import at module load (llm_provider and
    # sc_config both import from lightweight modules; get_llm_provider pulls in
    # provider construction which is not needed unless compare_group runs).
    from app.services.llm_provider import get_llm_provider

    cfg = config if config is not None else comparison_config
    provider = llm if llm is not None else get_llm_provider(cfg)

    # Collect the distinct field names carried by any record in the group.
    field_names: list[str] = []
    seen: set[str] = set()
    for record in group.records:
        for name in record.fields:
            if name not in seen:
                seen.add(name)
                field_names.append(name)

    produced: list[Discrepancy] = []
    # Fields that were in scope + comparable this run but produced NO flag — used
    # to clear a stale still-pending row for a field that now agrees.
    agreed_fields: list[str] = []

    for field in field_names:
        field_type = classify_field(field, cfg)
        if field_type is None:
            continue  # out of scope (Req 3.7) — do not compare, do not clear

        if field_type is FieldType.FREE_TEXT:
            discrepancy = await check_free_text(group, field, provider)
        else:
            threshold = _field_threshold(cfg, field)
            discrepancy = _make_discrepancy_for_field(
                group, field, field_type, threshold, provider
            )

        if discrepancy is not None:
            produced.append(discrepancy)
        else:
            agreed_fields.append(field)

    logger.info(
        "compare_group dispatched: group_id=%s part_number=%s lot_number=%s "
        "fields_checked=%d discrepancies_produced=%d",
        group.id,
        group.part_number,
        group.lot_number,
        len(field_names),
        len(produced),
    )

    await _persist_discrepancies(group, produced, agreed_fields)
    return await _load_group_discrepancies(group.id)


def _field_threshold(config: ComparisonConfig, field: str) -> float | None:
    """Resolve the per-field numeric threshold from config (Req 8.2).

    Prefers the ``FieldConfig.threshold`` on the in-scope field; falls back to
    the top-level ``numeric_thresholds`` map. ``None`` (unresolved) is passed
    through so :func:`check_numeric` routes the field to manual review rather
    than silently defaulting.
    """
    field_config = config.fields.get(field)
    if field_config is not None and field_config.threshold is not None:
        return field_config.threshold
    return config.numeric_thresholds.get(field)


async def _persist_discrepancies(
    group: AlignedGroup,
    discrepancies: list[Discrepancy],
    agreed_fields: list[str],
) -> None:
    """Upsert produced discrepancies and clear stale-pending agreed fields.

    Each produced discrepancy is inserted as ``pending`` or, on
    ``(group_id, field_name)`` conflict, updates ``field_type`` / ``values`` /
    ``provenance`` while **preserving** an already-decided ``review_state``
    (Req 5.4, Property 7). Fields that were checked this run but produced no
    discrepancy have any still-``pending`` row removed; decided rows are left
    intact (documented agree-again behavior — see module notes).
    """
    db = await get_db()
    now = _now_iso()

    for discrepancy in discrepancies:
        values_json = json.dumps(discrepancy.values, default=str)
        await db.execute(
            """INSERT INTO sc_discrepancies
                   (id, group_id, part_number, lot_number, field_name,
                    field_type, "values", provenance, review_state, created_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
               ON CONFLICT(group_id, field_name) DO UPDATE SET
                   field_type = excluded.field_type,
                   "values"   = excluded."values",
                   provenance = excluded.provenance
               -- review_state and created_at are intentionally NOT updated:
               -- a decided (confirmed/dismissed) row keeps its decision and a
               -- pending row stays pending; recompare never resets state.""",
            (
                discrepancy.id,
                discrepancy.group_id,
                discrepancy.part_number,
                discrepancy.lot_number,
                discrepancy.field_name,
                discrepancy.field_type.value,
                values_json,
                discrepancy.provenance.value,
                ReviewState.PENDING.value,
                now,
            ),
        )

    # Agree-again: clear only still-pending rows for fields that now agree.
    # Decided rows (confirmed/dismissed) are preserved to keep Property 5 stable.
    for field in agreed_fields:
        await db.execute(
            """DELETE FROM sc_discrepancies
                WHERE group_id = ? AND field_name = ?
                  AND review_state = ?""",
            (group.id, field, ReviewState.PENDING.value),
        )

    await db.commit()


async def _load_group_discrepancies(group_id: str) -> list[Discrepancy]:
    """Load the current persisted discrepancies for a group (post-upsert).

    Returns them as :class:`Discrepancy` models reflecting the stored
    ``review_state`` (so preserved confirmed/dismissed decisions are visible),
    ordered by field name for stable output.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, group_id, part_number, lot_number, field_name, field_type,
                  "values", provenance, review_state
             FROM sc_discrepancies
            WHERE group_id = ?
            ORDER BY field_name ASC, id ASC""",
        (group_id,),
    )
    rows = await cursor.fetchall()
    result: list[Discrepancy] = []
    for row in rows:
        raw_values = row["values"]
        values = json.loads(raw_values) if raw_values else {}
        result.append(
            Discrepancy(
                id=row["id"],
                group_id=row["group_id"],
                part_number=row["part_number"],
                lot_number=row["lot_number"],
                field_name=row["field_name"],
                field_type=FieldType(row["field_type"]),
                values=values,
                provenance=Provenance(row["provenance"]),
                review_state=ReviewState(row["review_state"]),
            )
        )
    return result
