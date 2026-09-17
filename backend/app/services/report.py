"""Discrepancy report + CSV export service for source-comparison (Req 7).

This service assembles the **confirmed-only** discrepancy report (Property 5)
that backs the report screen and its CSV export (endpoints are added in
task 6.2 — this module adds no HTTP routes). It is deliberately thin: the
confirmed-only filtering, the optional part / lot / source / field / provenance
filters, and the audit-backed review state all live in
``services/sc_review.list_confirmed`` — this module calls that helper so
pending and dismissed discrepancies can never reach the report (Property 5,
Req 6.4, 6.5, 7.2).

What this module owns:

  * :func:`build_report` — the confirmed-only report as a clean, serializable
    list of row dicts. Every row is **complete** (Property 8, Req 7.2):
    ``part_number``, ``lot_number``, ``field_name``, ``field_type``, the
    per-source ``values`` dict (the value present from each source), and
    ``provenance``. Filterable by part, lot, source, field, and provenance
    (Req 7.3).
  * :func:`render_report_csv` — flattens each row's per-source ``values`` dict
    into stable ``value_<SOURCE>`` columns (``value_LAIR``, ``value_FAIR``,
    ``value_SHQ``) so a non-technical reviewer can read the export without extra
    explanation (Req 7.5). Returns a CSV string for the export endpoint (6.2).
  * :func:`report_header` — the assumptions / open-items banner data from
    ``comparison_config.assumptions`` (the "assumed — pending client
    confirmation" items), surfaced in the report header rather than silently
    defaulted (Req 8.5). Exposed as an endpoint in task 6.2.

Structured logs are emitted for report assembly and export so report generation
is observable (Req 9.4).
"""

import csv
import io
import logging
from typing import Any

from app.models.source_comparison import Discrepancy, Provenance, SourceType
from app.services import sc_review
from app.services.part_context import get_part_context_map
from app.services.sc_config import ComparisonConfig, comparison_config

logger = logging.getLogger("app.source_comparison.report")

# Stable column order for the flattened per-source value columns in the CSV
# export (Req 7.5). Sourced from the SourceType enum so it stays in sync.
_SOURCE_ORDER: list[str] = [s.value for s in SourceType]

# The base (non per-source) columns of a report row, in export order.
_BASE_COLUMNS: list[str] = [
    "part_number",
    "lot_number",
    "field_name",
    "field_type",
    "provenance",
]


def _discrepancy_to_row(d: Discrepancy) -> dict[str, Any]:
    """Render one confirmed discrepancy as a complete, serializable report row.

    Includes part+lot, field name + type, the per-source ``values`` dict (the
    value from each present source), and the provenance that produced the flag
    (Property 8, Req 7.2). ``values`` is kept as a nested dict so the JSON
    report endpoint (6.2) can render per-source columns; the CSV helper flattens
    it into ``value_<SOURCE>`` columns.
    """
    return {
        "id": d.id,
        "group_id": d.group_id,
        "part_number": d.part_number,
        "lot_number": d.lot_number,
        "field_name": d.field_name,
        "field_type": d.field_type.value,
        "values": dict(d.values),
        "provenance": d.provenance.value,
    }


async def build_report(
    filters: dict[str, Any] | None = None,
    *,
    limit: int | None = sc_review.DEFAULT_PAGE_LIMIT,
    offset: int | None = 0,
) -> tuple[list[dict[str, Any]], int]:
    """Assemble a page of the confirmed-only discrepancy report (Req 7.1-7.3).

    Delegates to :func:`sc_review.list_confirmed` so **only** confirmed
    discrepancies are included — pending and dismissed never reach the report
    (Property 5). Each returned row is complete: part+lot, field name + type,
    the per-source ``values`` dict, and provenance (Property 8, Req 7.2).

    Args:
        filters: optional mapping of any of ``part_number`` / ``part``,
            ``lot_number`` / ``lot``, ``source``, ``field_name`` / ``field``,
            ``provenance`` (Req 7.3), and ``supplier``. Omitted or ``None``
            filters match everything. Both the short (``part``) and long
            (``part_number``) aliases are accepted so callers and the endpoint
            (6.2) can use the requirement's filter names directly. The
            ``supplier`` filter is applied in Python after joining part_context
            (case-insensitive exact match) — supplier lives in the ``parts``
            table, not in ``sc_discrepancies``, so it can't be filtered in SQL;
            it is applied to the FULL confirmed set before pagination so pages
            and counts stay correct.
        limit: page size. Defaults to :data:`sc_review.DEFAULT_PAGE_LIMIT` and
            is capped at :data:`sc_review.MAX_PAGE_LIMIT` by the read helper.
            Pass ``limit=None`` to fetch ALL matching confirmed rows — the CSV
            export uses this so the download stays complete rather than being
            truncated to one page.
        offset: page offset (default 0). Ignored when ``limit is None``.

    Returns:
        A ``(rows, total_count)`` tuple: ``rows`` is one page of serializable
        row dicts (ordered by part, lot, then field); ``total_count`` is the
        number of matching confirmed discrepancies across ALL pages so callers
        can render paging controls.
    """
    filters = filters or {}
    part_number = filters.get("part_number") or filters.get("part")
    lot_number = filters.get("lot_number") or filters.get("lot")
    field_name = filters.get("field_name") or filters.get("field")
    source = filters.get("source")
    provenance = filters.get("provenance")
    supplier = filters.get("supplier")

    # ── Supplier filter path ─────────────────────────────────────────────────
    # Supplier lives in the ``parts`` table (via part_context), NOT in
    # ``sc_discrepancies``, so it can't be expressed in the confirmed-only SQL.
    # It must be applied in Python AFTER attaching part_context, and it must be
    # applied to the FULL confirmed set BEFORE paginating (paginating first,
    # then filtering, would give wrong pages/counts). So when a supplier filter
    # is present we fetch every matching confirmed row (limit=None), attach
    # part_context, filter by supplier (case-insensitive exact match), compute
    # total_count from the filtered set, then slice the page in Python.
    if supplier is not None:
        confirmed, _all_count = await sc_review.list_confirmed(
            part_number=part_number,
            lot_number=lot_number,
            source=source,
            field_name=field_name,
            provenance=provenance,
            limit=None,
        )
        context_map = await get_part_context_map([d.part_number for d in confirmed])
        supplier_key = supplier.strip().casefold()
        filtered_rows: list[dict[str, Any]] = []
        for d in confirmed:
            ctx = context_map.get(d.part_number)
            row_supplier = (ctx or {}).get("supplier")
            if row_supplier is None:
                continue
            if str(row_supplier).strip().casefold() != supplier_key:
                continue
            row = _discrepancy_to_row(d)
            row["part_context"] = ctx
            filtered_rows.append(row)

        total_count = len(filtered_rows)
        if limit is None:
            rows = filtered_rows
        else:
            page_offset = offset if (offset is not None and offset > 0) else 0
            page_limit = (
                sc_review._clamp_limit(limit) if limit is not None else total_count
            )
            rows = filtered_rows[page_offset : page_offset + page_limit]

        logger.info(
            "Report assembled: confirmed_only rows=%d total=%d limit=%s offset=%s "
            "filters part=%s lot=%s source=%s field=%s provenance=%s supplier=%s",
            len(rows),
            total_count,
            limit,
            offset,
            part_number,
            lot_number,
            source,
            field_name,
            provenance,
            supplier,
        )
        return rows, total_count

    confirmed, total_count = await sc_review.list_confirmed(
        part_number=part_number,
        lot_number=lot_number,
        source=source,
        field_name=field_name,
        provenance=provenance,
        limit=limit,
        offset=offset,
    )
    # Batch-fetch human-readable part context for the distinct part numbers on
    # this page (one query, no N+1) and attach it to each report row. A part
    # number with no matching parts row yields part_context = None.
    context_map = await get_part_context_map([d.part_number for d in confirmed])
    rows = []
    for d in confirmed:
        row = _discrepancy_to_row(d)
        row["part_context"] = context_map.get(d.part_number)
        rows.append(row)

    logger.info(
        "Report assembled: confirmed_only rows=%d total=%d limit=%s offset=%s "
        "filters part=%s lot=%s source=%s field=%s provenance=%s",
        len(rows),
        total_count,
        limit,
        offset,
        part_number,
        lot_number,
        source,
        field_name,
        provenance,
    )
    return rows, total_count


async def supplier_summary(
    filters: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Roll up confirmed-only discrepancies by supplier (Req 7 supplier view).

    Returns a supplier-quality rollup over the **confirmed-only** discrepancy
    set (Property 5), respecting the same part / lot / source / field /
    provenance filters as :func:`build_report` but deliberately NOT the
    ``supplier`` filter (the rollup is the thing that shows every supplier, so a
    supplier filter here would be self-defeating).

    Each entry is::

        {
          "supplier": str | "(unknown)",
          "discrepancy_count": int,               # confirmed rows for supplier
          "part_count": int,                       # distinct part_numbers
          "provenance_counts": {                   # per-provenance breakdown
              "exact-match": int, "numeric-threshold": int,
              "llm": int, "llm-unavailable": int
          }
        }

    Rows whose part has no supplier in ``part_context`` (external/simulated
    parts, or parts absent from the ``parts`` table) are grouped under
    ``"(unknown)"``. The list is sorted by ``discrepancy_count`` descending
    (ties broken by supplier name for stable output).

    Args:
        filters: optional mapping of ``part`` / ``part_number``, ``lot`` /
            ``lot_number``, ``source``, ``field`` / ``field_name``, and
            ``provenance``. Omitted filters match everything. Any ``supplier``
            entry is ignored here.

    Returns:
        The supplier rollup list described above.
    """
    filters = filters or {}
    part_number = filters.get("part_number") or filters.get("part")
    lot_number = filters.get("lot_number") or filters.get("lot")
    field_name = filters.get("field_name") or filters.get("field")
    source = filters.get("source")
    provenance = filters.get("provenance")

    # Full confirmed-only set (respecting every filter except supplier), then
    # group in Python by the supplier joined from part_context.
    confirmed, _total = await sc_review.list_confirmed(
        part_number=part_number,
        lot_number=lot_number,
        source=source,
        field_name=field_name,
        provenance=provenance,
        limit=None,
    )
    context_map = await get_part_context_map([d.part_number for d in confirmed])

    _UNKNOWN = "(unknown)"
    provenance_keys = [p.value for p in Provenance]

    rollup: dict[str, dict[str, Any]] = {}
    for d in confirmed:
        ctx = context_map.get(d.part_number)
        supplier = (ctx or {}).get("supplier")
        key = str(supplier) if supplier is not None and str(supplier).strip() else _UNKNOWN

        bucket = rollup.get(key)
        if bucket is None:
            bucket = {
                "supplier": key,
                "discrepancy_count": 0,
                "_part_numbers": set(),
                "provenance_counts": {k: 0 for k in provenance_keys},
            }
            rollup[key] = bucket
        bucket["discrepancy_count"] += 1
        bucket["_part_numbers"].add(d.part_number)
        prov = d.provenance.value
        if prov in bucket["provenance_counts"]:
            bucket["provenance_counts"][prov] += 1

    result: list[dict[str, Any]] = []
    for bucket in rollup.values():
        part_numbers = bucket.pop("_part_numbers")
        bucket["part_count"] = len(part_numbers)
        result.append(bucket)

    # Sort by discrepancy_count desc, then supplier asc for stable output.
    result.sort(key=lambda b: (-b["discrepancy_count"], b["supplier"]))

    logger.info(
        "Supplier summary assembled: suppliers=%d rows=%d "
        "filters part=%s lot=%s source=%s field=%s provenance=%s",
        len(result),
        len(confirmed),
        part_number,
        lot_number,
        source,
        field_name,
        provenance,
    )
    return result


def render_report_csv(rows: list[dict[str, Any]]) -> str:
    """Render report rows to a CSV string for the export endpoint (Req 7.4, 7.5).

    The per-source ``values`` dict on each row is flattened into stable
    ``value_<SOURCE>`` columns (``value_LAIR``, ``value_FAIR``, ``value_SHQ``)
    so a non-technical reviewer can read each source's value side-by-side
    (Req 7.5). Columns are fixed and ordered regardless of which sources are
    present on a given row (missing sources render as an empty cell). The rows
    are confirmed-only because they come from :func:`build_report`.

    Args:
        rows: report rows produced by :func:`build_report`.

    Returns:
        The full CSV document as a string (header row + one row per
        discrepancy), suitable for a downloadable file response.
    """
    value_columns = [f"value_{src}" for src in _SOURCE_ORDER]
    # Human-readable part context columns, placed right after part/lot so the
    # export is readable (what the part IS, not just its number). ``supplier``
    # sits right after ``part_revision`` so a reviewer can see who supplied the
    # part alongside its description/revision. Empty string when the row has no
    # matching part context (null-safe).
    context_columns = ["part_description", "part_revision", "supplier"]
    header = (
        _BASE_COLUMNS[:2]
        + context_columns
        + _BASE_COLUMNS[2:]
        + value_columns
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)

    for row in rows:
        values = row.get("values") or {}
        part_context = row.get("part_context") or {}
        base_head = [row.get(col, "") for col in _BASE_COLUMNS[:2]]
        context_cells = [
            "" if part_context.get("description") is None
            else str(part_context.get("description")),
            "" if part_context.get("revision") is None
            else str(part_context.get("revision")),
            "" if part_context.get("supplier") is None
            else str(part_context.get("supplier")),
        ]
        base_tail = [row.get(col, "") for col in _BASE_COLUMNS[2:]]
        per_source = []
        for src in _SOURCE_ORDER:
            val = values.get(src)
            per_source.append("" if val is None else str(val))
        writer.writerow(base_head + context_cells + base_tail + per_source)

    csv_text = buffer.getvalue()
    logger.info(
        "Report CSV rendered: rows=%d columns=%d", len(rows), len(header)
    )
    return csv_text


def report_header(
    config: ComparisonConfig | None = None,
) -> dict[str, Any]:
    """Return the assumptions / open-items banner data for the report (Req 8.5).

    Surfaces the ``comparison_config.assumptions`` registry — the two
    "assumed — pending client confirmation" items (SHQ numeric benchmark and the
    latency/load target) and any item still ``unresolved`` at a placeholder —
    so they are shown in the report header rather than silently defaulted
    (Req 8.5). Task 6.2 exposes this as ``GET /source-comparison/report/header``.

    Args:
        config: comparison config to read assumptions from; defaults to the
            module-level ``comparison_config`` singleton.

    Returns:
        A serializable dict ``{"assumptions": [...], "total_count": N}`` where
        each assumption item carries ``key``, ``label``, ``status``, ``value``.
    """
    cfg = config or comparison_config
    assumptions = [item.model_dump(mode="json") for item in cfg.assumptions]
    logger.info(
        "Report header assembled: assumption_items=%d", len(assumptions)
    )
    return {"assumptions": assumptions, "total_count": len(assumptions)}
