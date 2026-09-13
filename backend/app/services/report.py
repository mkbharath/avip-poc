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

from app.models.source_comparison import Discrepancy, SourceType
from app.services import sc_review
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
) -> list[dict[str, Any]]:
    """Assemble the confirmed-only discrepancy report (Req 7.1, 7.2, 7.3).

    Delegates to :func:`sc_review.list_confirmed` so **only** confirmed
    discrepancies are included — pending and dismissed never reach the report
    (Property 5). Each returned row is complete: part+lot, field name + type,
    the per-source ``values`` dict, and provenance (Property 8, Req 7.2).

    Args:
        filters: optional mapping of any of ``part_number`` / ``part``,
            ``lot_number`` / ``lot``, ``source``, ``field_name`` / ``field``,
            and ``provenance`` (Req 7.3). Omitted or ``None`` filters match
            everything. Both the short (``part``) and long (``part_number``)
            aliases are accepted so callers and the endpoint (6.2) can use the
            requirement's filter names directly.

    Returns:
        A list of serializable row dicts, ordered by part, lot, then field.
    """
    filters = filters or {}
    part_number = filters.get("part_number") or filters.get("part")
    lot_number = filters.get("lot_number") or filters.get("lot")
    field_name = filters.get("field_name") or filters.get("field")
    source = filters.get("source")
    provenance = filters.get("provenance")

    confirmed = await sc_review.list_confirmed(
        part_number=part_number,
        lot_number=lot_number,
        source=source,
        field_name=field_name,
        provenance=provenance,
    )
    rows = [_discrepancy_to_row(d) for d in confirmed]

    logger.info(
        "Report assembled: confirmed_only rows=%d filters part=%s lot=%s "
        "source=%s field=%s provenance=%s",
        len(rows),
        part_number,
        lot_number,
        source,
        field_name,
        provenance,
    )
    return rows


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
    header = _BASE_COLUMNS + value_columns

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(header)

    for row in rows:
        values = row.get("values") or {}
        base = [row.get(col, "") for col in _BASE_COLUMNS]
        per_source = []
        for src in _SOURCE_ORDER:
            val = values.get(src)
            per_source.append("" if val is None else str(val))
        writer.writerow(base + per_source)

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
