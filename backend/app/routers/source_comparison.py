"""Source-comparison router (LAIR / FAIR / SHQ).

FastAPI router for the source-comparison feature, registered in ``main.py`` as::

    app.include_router(source_comparison.router, prefix="/api/v1",
                       tags=["Source Comparison"])

This module owns a single ``router = APIRouter()`` that later tasks (aligned-group
read endpoints, comparison, review gate, report/export, status) append to. Only
the ingestion-facing endpoints belong to task 2.2:

  * ``POST /source-comparison/ingest`` — accept an inbound source record, hand it
    to the ingestion service, and translate the outcome into HTTP: 202 on accept
    (Req 1.3), 422 naming the source + record id + reason on rejection
    (Req 1.6, 1.7).
  * ``GET  /source-comparison/rejected`` — list persisted rejected records, most
    recent first (Req 1.7).

Ingestion design intent (Req 1.6, 1.7): a received record that does not conform
to the schema must still be *retained* (persisted to ``sc_rejected_records``) and
answered with a 422 that names the source and record id — never silently dropped
and never 422'd by FastAPI's own body validation before our handler runs. To
honour that, the ingest endpoint accepts the raw request body (loosely typed)
and routes it through ``ingestion.ingest_payload``, which persists a rejection
for structurally malformed input as well as for schema-valid-but-incomplete
records. FastAPI therefore never rejects the body ahead of us.
"""

import asyncio
import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.db.database import get_db
from app.models.source_comparison import (
    AlignmentState,
    BulkDecideRequest,
    DecideRequest,
)
from app.services import (
    alignment,
    ingestion,
    report,
    sc_review,
    threshold_config,
)
from app.services.part_context import get_part_context_map
from app.services.source_adapters import SimulatorAdapter

logger = logging.getLogger("app.source_comparison.router")

# Single shared router; later tasks (3.2, 5.2, 6.2, 7.3) append their endpoints
# to this same instance. Do not create additional routers in this file.
router = APIRouter()


@router.post("/source-comparison/ingest")
async def ingest_source_record(request: Request):
    """Accept one inbound source record and dispatch it to the ingestion service.

    The body is read loosely (raw JSON) rather than as a typed ``IngestRecord``
    so that FastAPI does not 422 malformed input before our handler runs — the
    design requires malformed records to be *persisted* to
    ``sc_rejected_records`` and answered with a 422 that names the source and
    record id, never silently dropped (Req 1.6, 1.7). ``ingest_payload`` handles
    both structurally malformed payloads and schema-valid-but-incomplete ones.

    Returns:
      * ``202`` with the :class:`~app.services.ingestion.IngestResult` dict on
        acceptance (Req 1.3).
      * ``422`` with a body naming ``source``, ``record_id``, and ``reason`` on
        rejection (Req 1.6, 1.7).
    """
    try:
        raw_payload = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        # A body that is not even valid JSON is still a received record that must
        # be retained and reported, not dropped. Persist the raw bytes' repr and
        # answer 422 with the identifying detail we have (none, in this case).
        raw_bytes = await request.body()
        try:
            reason = "malformed request body: not valid JSON"
            await ingestion._persist_rejected(
                source=None,
                external_record_id=None,
                raw_payload=raw_bytes.decode("utf-8", errors="replace"),
                reason=reason,
            )
        except Exception:  # persistence must never itself surface as a 500 here
            logger.exception("Failed to persist a non-JSON ingest body")
            reason = "malformed request body: not valid JSON"
        logger.warning("Rejected non-JSON ingest body")
        return JSONResponse(
            status_code=422,
            content={"source": None, "record_id": None, "reason": reason},
        )

    try:
        result = await ingestion.ingest_payload(raw_payload)
    except ingestion.IngestionRejected as rejected:
        # The offending record is already persisted to sc_rejected_records; the
        # 422 body names the source + record id + reason (Req 1.6, 1.7).
        return JSONResponse(
            status_code=422,
            content={
                "source": rejected.source,
                "record_id": rejected.record_id,
                "reason": rejected.reason,
            },
        )

    return JSONResponse(status_code=202, content=result.to_dict())


@router.get("/source-comparison/rejected")
async def list_rejected_records():
    """List persisted rejected records, most recent first (Req 1.7).

    Every record that failed ingestion is retained in ``sc_rejected_records``
    with its source, external record id, raw payload, reason, and rejection
    timestamp. The ``raw_payload`` JSON text is parsed back into an object for
    the response when possible, falling back to the raw string otherwise.
    """
    db = await get_db()
    cursor = await db.execute(
        """SELECT id, source, external_record_id, raw_payload, reason, rejected_at
             FROM sc_rejected_records
            ORDER BY rejected_at DESC, id DESC"""
    )
    rows = await cursor.fetchall()

    data = []
    for row in rows:
        raw_payload = row["raw_payload"]
        try:
            parsed_payload = json.loads(raw_payload) if raw_payload is not None else None
        except (json.JSONDecodeError, TypeError):
            parsed_payload = raw_payload
        data.append(
            {
                "id": row["id"],
                "source": row["source"],
                "external_record_id": row["external_record_id"],
                "raw_payload": parsed_payload,
                "reason": row["reason"],
                "rejected_at": row["rejected_at"],
            }
        )

    return {"data": data, "total_count": len(data)}


# ── Aligned-group read endpoints (task 3.2) ──────────────────────────────────
#
# Read-only views over the streaming alignment service. The alignment worker
# (task 7.2) reconciles records into ``sc_aligned_groups`` by common key; these
# endpoints expose those groups so the pipeline's alignment state is inspectable
# (Req 2.2, 2.4). Both delegate to the already-built read helpers in
# ``app.services.alignment`` and serialise the Pydantic ``AlignedGroup`` (and its
# nested ``SourceRecord`` list) to JSON-friendly dicts via ``.model_dump()`` —
# keeping ``present_sources`` and ``alignment_state`` visible.


@router.get("/source-comparison/groups")
async def list_aligned_groups(
    part: str | None = Query(default=None, description="Filter by part_number"),
    lot: str | None = Query(default=None, description="Filter by lot_number"),
    state: AlignmentState | None = Query(
        default=None,
        description="Filter by alignment_state (partial | complete | unmatched)",
    ),
):
    """List aligned groups, most recently updated first (Req 2.2, 2.4).

    Optional query filters, all ANDed and each matching all when omitted:

      * ``part`` → ``part_number``
      * ``lot``  → ``lot_number``
      * ``state`` → ``alignment_state`` (``partial`` | ``complete`` | ``unmatched``)

    Delegates to :func:`app.services.alignment.list_groups`. Each returned group
    includes its attached ``records``, with ``present_sources`` and
    ``alignment_state`` visible. The response envelope
    (``{data, total_count}``) matches the other list endpoints (e.g.
    ``/source-comparison/rejected``).
    """
    groups = await alignment.list_groups(
        part_number=part,
        lot_number=lot,
        state=state.value if state is not None else None,
    )
    data = [group.model_dump(mode="json") for group in groups]
    return {"data": data, "total_count": len(data)}


@router.get("/source-comparison/groups/{group_id}")
async def get_aligned_group(group_id: str):
    """Return one aligned group with its attached records (Req 2.2, 2.4).

    Delegates to :func:`app.services.alignment.get_group`. Responds ``404`` when
    no group has the given id. The serialised group keeps ``present_sources`` and
    ``alignment_state`` visible alongside its ``records``.
    """
    group = await alignment.get_group(group_id)
    if group is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Aligned group not found: {group_id}"},
        )
    return group.model_dump(mode="json")

# ── Review-gate endpoints (task 5.2) ─────────────────────────────────────────
#
# The mandatory human review gate every flagged discrepancy passes through
# (Req 6.1, 6.2, 6.3). These endpoints expose the already-built review service
# (``app.services.sc_review``) over HTTP, reusing AVIP's existing review-queue
# response shape (``{data, total_count}`` — see ``routers/review.py`` and
# ``sc_review.get_review_queue``) so the source-comparison workbench UI feels
# native. Discrepancies enter as ``pending`` from the comparison service; the
# decide endpoint is the only path that moves one to ``confirmed``/``dismissed``.


@router.get("/source-comparison/review/queue")
async def get_review_queue(
    limit: int = Query(
        default=sc_review.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=sc_review.MAX_PAGE_LIMIT,
        description=(
            f"Page size (default {sc_review.DEFAULT_PAGE_LIMIT}, "
            f"max {sc_review.MAX_PAGE_LIMIT})"
        ),
    ),
    offset: int = Query(default=0, ge=0, description="Page offset (default 0)"),
):
    """Return a page of the pending discrepancy review queue (Req 6.1, 6.2).

    Delegates to :func:`app.services.sc_review.get_review_queue`, which returns
    a ``{data, total_count, limit, offset}`` envelope shaped like AVIP's
    existing review queue so the workbench UI can reuse the native review
    patterns. Only ``pending`` discrepancies appear — confirmed/dismissed ones
    are excluded so the queue shows exactly the outstanding review work.

    Pagination is the real fix for the queue hanging the frontend: the pending
    set can be very large, so a single page (default ``limit``
    {DEFAULT_PAGE_LIMIT}, capped at {MAX_PAGE_LIMIT}) is returned alongside the
    full ``total_count`` of pending rows for paging controls.
    """
    return await sc_review.get_review_queue(limit=limit, offset=offset)


@router.get("/source-comparison/review/queue-grouped")
async def get_review_queue_grouped(
    limit: int = Query(
        default=sc_review.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=sc_review.MAX_PAGE_LIMIT,
        description=(
            f"Page size in GROUPS (default {sc_review.DEFAULT_PAGE_LIMIT}, "
            f"max {sc_review.MAX_PAGE_LIMIT})"
        ),
    ),
    offset: int = Query(default=0, ge=0, description="Page offset in groups (default 0)"),
):
    """Return the pending review queue GROUPED by part/lot for the accordion UI.

    Delegates to :func:`app.services.sc_review.get_review_queue_grouped`, which
    returns a ``{data, total_count, limit, offset}`` envelope where each ``data``
    entry is one ``(part_number, lot_number)`` group carrying its pending
    ``count``, a per-provenance ``provenance_counts`` breakdown, and the group's
    pending ``discrepancies``. Only ``pending`` discrepancies appear —
    confirmed/dismissed are excluded, consistent with the flat
    ``/review/queue``.

    Pagination is by GROUP: ``limit``/``offset`` page the groups (default
    ``limit`` {DEFAULT_PAGE_LIMIT}, capped at {MAX_PAGE_LIMIT}); ``total_count``
    is the total number of pending groups so the UI can render paging controls.
    Groups are ordered by their earliest pending item so panels stay stable
    across pages.

    This fixed ``/review/queue-grouped`` path is declared **before** the
    ``/review/{discrepancy_id}`` GET route so it is never matched as a
    discrepancy id.
    """
    return await sc_review.get_review_queue_grouped(limit=limit, offset=offset)


@router.post("/source-comparison/review/decide-bulk")
async def decide_review_bulk(request: BulkDecideRequest):
    """Apply one reviewer decision to many discrepancies at once (Req 6.3).

    Body is a :class:`~app.models.source_comparison.BulkDecideRequest`
    (``discrepancy_ids`` list, ``decision`` ``"confirmed"``|``"dismissed"``,
    ``reviewer``, optional ``note``). Delegates to
    :func:`app.services.sc_review.decide_many`, which applies the same per-item
    review path to each id — every decided discrepancy still updates its
    ``review_state``, upserts its current-decision row, and appends an immutable
    audit row (full audit trail preserved per item).

    Returns the summary dict ``{"updated", "not_found", "decision"}``. An empty
    ``discrepancy_ids`` is a no-op, not an error, returning
    ``{"updated": 0, "not_found": []}`` (200).

    This fixed-path POST is declared **before** the ``/review/{discrepancy_id}``
    GET route so ``decide-bulk`` is never mistaken for a discrepancy id (they
    also differ by method, so there is no real collision).

    Error mapping:
      * :class:`ValueError` (invalid decision) → ``422`` with the reason.
    """
    try:
        summary = await sc_review.decide_many(
            discrepancy_ids=request.discrepancy_ids,
            decision=request.decision,
            reviewer=request.reviewer,
            note=request.note,
        )
    except ValueError as bad_decision:
        return JSONResponse(
            status_code=422,
            content={"detail": str(bad_decision)},
        )
    return summary


@router.get("/source-comparison/review/{discrepancy_id}")
async def get_review_discrepancy(discrepancy_id: str):
    """Return one discrepancy's detail for the review workbench (Req 6.2).

    Delegates to :func:`app.services.sc_review.get_discrepancy`. Responds
    ``404`` (naming the discrepancy id) when no discrepancy exists so the
    workbench can surface a clear not-found state. The serialised discrepancy
    keeps its per-source ``values`` and ``provenance`` visible.
    """
    discrepancy = await sc_review.get_discrepancy(discrepancy_id)
    if discrepancy is None:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Discrepancy not found: {discrepancy_id}"},
        )
    detail = discrepancy.model_dump(mode="json")
    # Attach human-readable part context (description + revision + material +
    # supplier). A part_number with no matching parts row yields None.
    context_map = await get_part_context_map([discrepancy.part_number])
    detail["part_context"] = context_map.get(discrepancy.part_number)
    return detail


@router.post("/source-comparison/review/{discrepancy_id}/decide")
async def decide_review_discrepancy(discrepancy_id: str, request: DecideRequest):
    """Record a reviewer decision against a discrepancy (Req 6.3).

    Body is a :class:`~app.models.source_comparison.DecideRequest`
    (``decision`` ``"confirmed"``|``"dismissed"``, ``reviewer``, optional
    ``note``). Delegates to :func:`app.services.sc_review.decide`, which records
    the decision + reviewer identity + optional note + timestamp against the
    discrepancy and writes an immutable audit row. On success returns the
    updated discrepancy (reflecting its new ``review_state``).

    Error mapping:
      * :class:`LookupError` (unknown discrepancy id) → ``404`` naming the id.
      * :class:`ValueError` (invalid decision) → ``422`` with the reason.
    """
    try:
        updated = await sc_review.decide(
            discrepancy_id=discrepancy_id,
            decision=request.decision,
            reviewer=request.reviewer,
            note=request.note,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Discrepancy not found: {discrepancy_id}"},
        )
    except ValueError as bad_decision:
        return JSONResponse(
            status_code=422,
            content={"detail": str(bad_decision)},
        )
    return updated.model_dump(mode="json")


@router.post("/source-comparison/review/{discrepancy_id}/reopen")
async def reopen_review_discrepancy(discrepancy_id: str, request: DecideRequest):
    """Return a decided discrepancy to ``pending`` (Req 6.3, 9.3).

    Body reuses :class:`~app.models.source_comparison.DecideRequest` for its
    ``reviewer`` (required) and optional ``note``; the ``decision`` field is
    ignored — reopen always sets the discrepancy back to ``pending``. Delegates
    to :func:`app.services.sc_review.reopen`, which flips ``review_state`` to
    pending, upserts the current-decision row, and writes an immutable
    ``sc_review_audit`` row (decision ``"reopened"``) — the same audit pattern
    as decide. A reopened discrepancy re-enters the pending queue and drops out
    of the confirmed-only report. On success returns the updated discrepancy.

    Error mapping:
      * :class:`LookupError` (unknown discrepancy id) → ``404`` naming the id.
    """
    try:
        updated = await sc_review.reopen(
            discrepancy_id=discrepancy_id,
            reviewer=request.reviewer,
            note=request.note,
        )
    except LookupError:
        return JSONResponse(
            status_code=404,
            content={"detail": f"Discrepancy not found: {discrepancy_id}"},
        )
    return updated.model_dump(mode="json")


# ── Report + export + header endpoints (task 6.2) ────────────────────────────
#
# The confirmed-only discrepancy report screen and its CSV export (Req 7.1–7.5),
# plus the assumptions/open-items banner (Req 8.5). These expose the already-
# built report service (``app.services.report``) over HTTP. The report is
# confirmed-only by construction — ``report.build_report`` delegates to
# ``sc_review.list_confirmed`` so pending/dismissed discrepancies never surface
# (Property 5). All filters are optional and ANDed; omitted filters match all.


def _report_filters(
    part: str | None,
    lot: str | None,
    source: str | None,
    field: str | None,
    provenance: str | None,
    supplier: str | None = None,
) -> dict[str, str]:
    """Build the ``build_report`` filter dict from optional query params.

    Only non-``None`` filters are included so omitted params match everything
    (Req 7.3). The service accepts the requirement's short filter names
    (``part``, ``lot``, ``field``) directly. ``supplier`` is joined from the
    ``parts`` table (via part_context) and applied in Python by the service.
    """
    filters: dict[str, str] = {}
    if part is not None:
        filters["part"] = part
    if lot is not None:
        filters["lot"] = lot
    if source is not None:
        filters["source"] = source
    if field is not None:
        filters["field"] = field
    if provenance is not None:
        filters["provenance"] = provenance
    if supplier is not None:
        filters["supplier"] = supplier
    return filters


@router.get("/source-comparison/report")
async def get_report(
    part: str | None = Query(default=None, description="Filter by part_number"),
    lot: str | None = Query(default=None, description="Filter by lot_number"),
    source: str | None = Query(
        default=None, description="Keep rows carrying a value from this source"
    ),
    field: str | None = Query(default=None, description="Filter by field_name"),
    provenance: str | None = Query(
        default=None,
        description="Filter by provenance "
        "(exact-match | numeric-threshold | llm | llm-unavailable)",
    ),
    supplier: str | None = Query(
        default=None,
        description="Filter by the part's supplier (joined from the parts "
        "table; case-insensitive exact match). Applied in Python after "
        "attaching part context.",
    ),
    review_state: str | None = Query(
        default=None,
        description="Review status to view (confirmed | dismissed | pending | "
        "all). Omitted = confirmed-only (default report behaviour).",
    ),
    limit: int = Query(
        default=sc_review.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=sc_review.MAX_PAGE_LIMIT,
        description=(
            f"Page size (default {sc_review.DEFAULT_PAGE_LIMIT}, "
            f"max {sc_review.MAX_PAGE_LIMIT})"
        ),
    ),
    offset: int = Query(default=0, ge=0, description="Page offset (default 0)"),
):
    """Return a page of the discrepancy report (Req 7.1, 7.2, 7.3).

    By DEFAULT (``review_state`` omitted) this is the confirmed-only report
    (Property 5). Supplying ``review_state`` (``confirmed`` | ``dismissed`` |
    ``pending`` | ``all``) is an opt-in that surfaces the requested review
    status instead, with each row also carrying ``review_state`` + ``id`` so the
    UI can offer a Reopen action.

    Optional query filters (all ANDed, each matching all when omitted):
    ``part`` → ``part_number``, ``lot`` → ``lot_number``, ``source`` (keep only
    rows carrying a value from that source), ``field`` → ``field_name``, and
    ``provenance``. Delegates to :func:`app.services.report.build_report`, which
    returns **confirmed-only** rows (Property 5) each complete with part+lot,
    field name + type, the per-source ``values`` dict, and provenance
    (Property 8, Req 7.2).

    Pagination (default ``limit`` {DEFAULT_PAGE_LIMIT}, capped at
    {MAX_PAGE_LIMIT}) works alongside every filter; the response envelope
    ``{data, total_count, limit, offset}`` carries the full match count so the
    UI can page. The CSV export path deliberately stays un-paginated.
    """
    # DEFAULT behaviour (review_state omitted) is confirmed-only: delegate to
    # the existing build_report path so current behaviour, Property 5, and the
    # existing tests are unchanged.
    if review_state is None:
        rows, total_count = await report.build_report(
            _report_filters(part, lot, source, field, provenance, supplier),
            limit=limit,
            offset=offset,
        )
        return {
            "data": rows,
            "total_count": total_count,
            "limit": limit,
            "offset": offset,
        }

    # Opt-in path: an explicit review_state routes through list_by_state, which
    # returns rows shaped identically to the confirmed report. We enrich each
    # row with review_state + id so the UI can drive the Reopen action.
    #
    # Supplier lives in the parts table (via part_context), not in
    # sc_discrepancies, so — exactly like build_report's supplier path — when a
    # supplier filter is present we must fetch the FULL matching set (limit=None),
    # attach part_context, filter by supplier in Python, then slice the page so
    # pages/counts are correct. Without a supplier filter we keep the efficient
    # SQL-paginated path unchanged.
    fetch_limit = None if supplier is not None else limit
    fetch_offset = None if supplier is not None else offset
    try:
        discrepancies, total_count = await sc_review.list_by_state(
            review_state,
            part_number=part,
            lot_number=lot,
            source=source,
            field_name=field,
            provenance=provenance,
            limit=fetch_limit,
            offset=fetch_offset,
        )
    except ValueError as bad_state:
        return JSONResponse(status_code=422, content={"detail": str(bad_state)})

    # Batch-fetch human-readable part context for the distinct part numbers on
    # this page (one query, no N+1) and attach it to each row, consistent with
    # the confirmed-only report path. A part_number with no matching parts row
    # yields part_context = None.
    context_map = await get_part_context_map([d.part_number for d in discrepancies])
    rows = [
        {
            "id": d.id,
            "group_id": d.group_id,
            "part_number": d.part_number,
            "lot_number": d.lot_number,
            "field_name": d.field_name,
            "field_type": d.field_type.value,
            "values": dict(d.values),
            "provenance": d.provenance.value,
            "review_state": d.review_state.value,
            "part_context": context_map.get(d.part_number),
        }
        for d in discrepancies
    ]

    if supplier is not None:
        supplier_key = supplier.strip().casefold()
        rows = [
            r
            for r in rows
            if (r["part_context"] or {}).get("supplier") is not None
            and str((r["part_context"] or {}).get("supplier")).strip().casefold()
            == supplier_key
        ]
        total_count = len(rows)
        page_offset = offset if (offset is not None and offset > 0) else 0
        rows = rows[page_offset : page_offset + limit]

    return {
        "data": rows,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


@router.get("/source-comparison/report/export")
async def export_report(
    format: str = Query(default="csv", description="Export format (csv)"),
    part: str | None = Query(default=None, description="Filter by part_number"),
    lot: str | None = Query(default=None, description="Filter by lot_number"),
    source: str | None = Query(
        default=None, description="Keep rows carrying a value from this source"
    ),
    field: str | None = Query(default=None, description="Filter by field_name"),
    provenance: str | None = Query(
        default=None,
        description="Filter by provenance "
        "(exact-match | numeric-threshold | llm | llm-unavailable)",
    ),
    supplier: str | None = Query(
        default=None,
        description="Filter by the part's supplier (joined from the parts "
        "table; case-insensitive exact match).",
    ),
):
    """Export the confirmed-only report as a downloadable CSV (Req 7.4, 7.5).

    Applies the same optional filters as ``GET /source-comparison/report``, then
    renders the rows to CSV via :func:`app.services.report.render_report_csv`
    (per-source ``values`` flattened into stable ``value_LAIR`` / ``value_FAIR``
    / ``value_SHQ`` columns so a non-technical reviewer can read it — Req 7.5).
    The rows are confirmed-only because they come from ``build_report``
    (Property 5).

    Only ``format=csv`` is supported (the default); any other value yields a
    ``400``. The response carries ``Content-Type: text/csv`` and a
    ``Content-Disposition: attachment`` header so browsers download it as
    ``source-comparison-report.csv``.
    """
    if format != "csv":
        return JSONResponse(
            status_code=400,
            content={
                "detail": f"Unsupported export format {format!r}; only 'csv' is "
                "supported."
            },
        )

    # The export is a download, not a page: pass limit=None so build_report
    # returns ALL matching confirmed rows and the CSV stays complete regardless
    # of the queue/report default page size.
    rows, _total_count = await report.build_report(
        _report_filters(part, lot, source, field, provenance, supplier),
        limit=None,
    )
    csv_text = report.render_report_csv(rows)
    return Response(
        content=csv_text,
        media_type="text/csv",
        headers={
            "Content-Disposition": "attachment; "
            "filename=source-comparison-report.csv"
        },
    )


@router.get("/source-comparison/report/header")
async def get_report_header():
    """Return the assumptions / open-items banner data for the report (Req 8.5).

    Delegates to :func:`app.services.report.report_header`, surfacing the
    "assumed — pending client confirmation" items (SHQ numeric benchmark and the
    latency/load target) and any still-unresolved placeholder so they are shown
    in the report header rather than silently defaulted. Returns
    ``{"assumptions": [...], "total_count": N}``.
    """
    return report.report_header()


@router.get("/source-comparison/report/supplier-summary")
async def get_supplier_summary(
    part: str | None = Query(default=None, description="Filter by part_number"),
    lot: str | None = Query(default=None, description="Filter by lot_number"),
    source: str | None = Query(
        default=None, description="Keep rows carrying a value from this source"
    ),
    field: str | None = Query(default=None, description="Filter by field_name"),
    provenance: str | None = Query(
        default=None,
        description="Filter by provenance "
        "(exact-match | numeric-threshold | llm | llm-unavailable)",
    ),
):
    """Return the confirmed-only discrepancy rollup grouped by supplier (Req 7).

    Delegates to :func:`app.services.report.supplier_summary`, which rolls up
    the **confirmed-only** discrepancies (Property 5) by the supplier joined
    from the ``parts`` table (via part_context). It respects the same optional
    filters as ``GET /source-comparison/report`` — ``part`` → ``part_number``,
    ``lot`` → ``lot_number``, ``source``, ``field`` → ``field_name``, and
    ``provenance`` — but deliberately NOT a supplier filter (the rollup is what
    surfaces every supplier). Rows whose part has no supplier are grouped under
    ``"(unknown)"``.

    Returns ``{"data": [...supplier rollup...], "total_count": N}`` where each
    entry carries ``supplier``, ``discrepancy_count``, ``part_count`` (distinct
    part numbers), and a per-provenance ``provenance_counts`` breakdown, sorted
    by ``discrepancy_count`` descending.
    """
    data = await report.supplier_summary(
        _report_filters(part, lot, source, field, provenance),
    )
    return {"data": data, "total_count": len(data)}


# ── Threshold-configuration endpoints (Req 8.1, 8.2) ─────────────────────────
#
# Runtime-editable numeric-threshold configuration over HTTP. These expose the
# already-built ``app.services.threshold_config`` service so the effective
# per-field default and per-part overrides can be edited from the app and every
# change is auditable (Req 8.1, 8.2; full auditability). The service layer is
# the single source of truth for the effective threshold; these endpoints only
# translate between HTTP and the service's functions + errors.
#
# ``changed_by`` is a typed reviewer-identity string supplied by the caller —
# the portal-wide auth story is intentionally deferred, so ``changed_by`` is the
# self-declared editor identity recorded in the audit trail and must NOT be
# mistaken for an authenticated principal. Every config endpoint that mutates
# requires a non-empty ``changed_by`` and 422s naming the problem when it is
# missing, matching the review-gate error convention.


@router.get("/source-comparison/config")
async def get_config():
    """Return the current effective comparison config (Req 8.1, 8.2).

    Delegates to :func:`app.services.threshold_config.load_config`, which loads
    the persisted config row (seeding it from the defaults on first access), and
    returns the in-scope field set as a list of
    ``{field_name, type, in_scope, threshold}`` entries. ``threshold`` is the
    per-field default (``None`` for non-numeric fields). Fields are ordered by
    name for stable output. Per-part overrides are exposed separately via
    ``/config/overrides`` — this endpoint reports the field defaults only.
    """
    config = await threshold_config.load_config()
    fields = [
        {
            "field_name": name,
            "type": fc.type.value,
            "in_scope": fc.in_scope,
            "threshold": fc.threshold,
        }
        for name, fc in sorted(config.fields.items())
    ]
    return {"fields": fields, "total_count": len(fields)}


@router.put("/source-comparison/config/field/{field_name}")
async def put_field_default(field_name: str, request: Request):
    """Edit a field's default ``threshold`` and/or ``in_scope`` (Req 8.1, 8.2).

    Body: ``{threshold?: number, in_scope?: boolean, changed_by: string,
    note?: string}``. Both ``threshold`` and ``in_scope`` are optional edits —
    pass a value to change it, omit (or ``null``) to leave that aspect untouched.
    Delegates to :func:`app.services.threshold_config.set_field_default`, which
    validates a supplied ``threshold`` as a positive number, persists the edit,
    and appends an immutable config-audit row per changed aspect (full audit
    trail).

    ``changed_by`` is the self-declared editor identity recorded in the audit
    trail (portal-wide auth is intentionally deferred — this is NOT an
    authenticated principal). It is required.

    Error mapping (422 with a ``detail`` naming the problem):
      * missing / blank ``changed_by``.
      * malformed JSON body.
      * invalid ``threshold`` or unknown ``field_name`` (:class:`ValueError`
        from the service).

    On success returns the updated field config
    ``{field_name, type, in_scope, threshold}``.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JSONResponse(
            status_code=422,
            content={"detail": "malformed request body: not valid JSON"},
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=422,
            content={"detail": "request body must be a JSON object"},
        )

    changed_by = body.get("changed_by")
    if not isinstance(changed_by, str) or not changed_by.strip():
        return JSONResponse(
            status_code=422,
            content={"detail": "changed_by is required and must be a non-empty string"},
        )

    try:
        updated = await threshold_config.set_field_default(
            field_name=field_name,
            threshold=body.get("threshold"),
            in_scope=body.get("in_scope"),
            changed_by=changed_by,
            note=body.get("note"),
        )
    except ValueError as bad:
        return JSONResponse(status_code=422, content={"detail": str(bad)})

    return {
        "field_name": field_name,
        "type": updated.type.value,
        "in_scope": updated.in_scope,
        "threshold": updated.threshold,
    }


@router.get("/source-comparison/config/overrides")
async def list_config_overrides(
    part_number: str | None = Query(
        default=None, description="Filter overrides to a single part_number"
    ),
):
    """List per-part threshold overrides — all, or one part (Req 8.1, 8.2).

    Delegates to :func:`app.services.threshold_config.list_overrides`. When
    ``part_number`` is omitted every override is returned; when supplied only
    that part's overrides are returned. Each item is
    ``{id, part_number, field_name, threshold, updated_at}``. The response
    envelope ``{data, total_count}`` matches the other list endpoints.
    """
    overrides = await threshold_config.list_overrides(part_number=part_number)
    return {"data": overrides, "total_count": len(overrides)}


@router.post("/source-comparison/config/overrides")
async def post_config_override(request: Request):
    """Create / update a per-part threshold override (Req 8.1, 8.2).

    Body: ``{part_number, field_name, threshold, changed_by, note?}``. A per-part
    override wins over the field default for that part during resolution.
    Delegates to :func:`app.services.threshold_config.set_part_override`, which
    validates ``threshold`` as a positive number, upserts the override keyed
    ``(part_number, field_name)``, and appends an immutable config-audit row.

    ``changed_by`` is the self-declared editor identity recorded in the audit
    trail (portal-wide auth is intentionally deferred — NOT an authenticated
    principal). It is required.

    Error mapping (422 with a ``detail`` naming the problem):
      * malformed JSON body.
      * missing / blank ``part_number``, ``field_name``, or ``changed_by``.
      * invalid ``threshold`` (:class:`ValueError` from the service).

    On success returns the created/updated override
    ``{part_number, field_name, threshold, changed_by, note}``.
    """
    try:
        body = await request.json()
    except (json.JSONDecodeError, UnicodeDecodeError, ValueError):
        return JSONResponse(
            status_code=422,
            content={"detail": "malformed request body: not valid JSON"},
        )
    if not isinstance(body, dict):
        return JSONResponse(
            status_code=422,
            content={"detail": "request body must be a JSON object"},
        )

    part_number = body.get("part_number")
    field_name = body.get("field_name")
    changed_by = body.get("changed_by")
    for name, value in (
        ("part_number", part_number),
        ("field_name", field_name),
        ("changed_by", changed_by),
    ):
        if not isinstance(value, str) or not value.strip():
            return JSONResponse(
                status_code=422,
                content={"detail": f"{name} is required and must be a non-empty string"},
            )

    try:
        await threshold_config.set_part_override(
            part_number=part_number,
            field_name=field_name,
            threshold=body.get("threshold"),
            changed_by=changed_by,
            note=body.get("note"),
        )
    except ValueError as bad:
        return JSONResponse(status_code=422, content={"detail": str(bad)})

    return {
        "part_number": part_number,
        "field_name": field_name,
        "threshold": float(body.get("threshold")),
        "changed_by": changed_by,
        "note": body.get("note"),
    }


@router.delete("/source-comparison/config/overrides")
async def delete_config_override(
    part_number: str = Query(description="Part number of the override to delete"),
    field_name: str = Query(description="Field name of the override to delete"),
    changed_by: str = Query(
        description="Self-declared editor identity recorded in the audit trail "
        "(portal-wide auth is intentionally deferred — NOT an authenticated "
        "principal)"
    ),
    note: str | None = Query(default=None, description="Optional audit note"),
):
    """Delete a per-part threshold override (Req 8.1, 8.2).

    The override identifiers (``part_number``, ``field_name``) plus
    ``changed_by`` and the optional ``note`` are taken as **query params** to
    keep the delete simple and cache-safe. Delegates to
    :func:`app.services.threshold_config.delete_part_override`, which removes the
    override row (if present) and appends an immutable config-audit row only when
    a row is actually removed.

    ``changed_by`` is the self-declared editor identity recorded in the audit
    trail (portal-wide auth is intentionally deferred — NOT an authenticated
    principal). It is required.

    Returns ``{"deleted": true}`` when an override existed and was removed,
    ``{"deleted": false}`` when there was nothing to delete.
    """
    deleted = await threshold_config.delete_part_override(
        part_number=part_number,
        field_name=field_name,
        changed_by=changed_by,
        note=note,
    )
    return {"deleted": deleted}


@router.get("/source-comparison/config/audit")
async def get_config_audit(
    limit: int = Query(
        default=sc_review.DEFAULT_PAGE_LIMIT,
        ge=1,
        le=sc_review.MAX_PAGE_LIMIT,
        description=(
            f"Page size (default {sc_review.DEFAULT_PAGE_LIMIT}, "
            f"max {sc_review.MAX_PAGE_LIMIT})"
        ),
    ),
    offset: int = Query(default=0, ge=0, description="Page offset (default 0)"),
):
    """Return a page of the append-only config-audit trail, newest first.

    Delegates to :func:`app.services.threshold_config.list_audit`, which returns
    the ``sc_config_audit`` rows ordered by ``changed_at`` descending. Each row
    captures who (``changed_by``) / when (``changed_at``) / old→new for every
    field-default, part-override, and field-scope change (full auditability).

    Pagination matches the review queue: ``limit`` defaults to
    {DEFAULT_PAGE_LIMIT}, is capped at {MAX_PAGE_LIMIT} by the query validator,
    and ``offset`` defaults to 0. The response envelope
    ``{data, total_count, limit, offset}`` mirrors the review-queue envelope;
    ``total_count`` is the count of ALL audit rows so the UI can page.
    """
    total_count = await threshold_config.count_audit()
    data = await threshold_config.list_audit(limit=limit, offset=offset)
    return {
        "data": data,
        "total_count": total_count,
        "limit": limit,
        "offset": offset,
    }


# ── Status endpoint (task 7.3) ───────────────────────────────────────────────
#
# A small dashboard/monitor snapshot of the streaming pipeline (Req 9.4): how
# many records have been ingested vs rejected, how many aligned groups are
# partial vs complete, and the assumptions banner (the "assumed — pending client
# confirmation" items). The counts are queried directly from the sc_* tables so
# the snapshot reflects the persisted pipeline state regardless of whether the
# worker/simulator are currently running. The assumptions come from
# report.report_header() (i.e. comparison_config.assumptions) so the same items
# shown in the report banner are shown here.


def _simulator_running(request: Request) -> bool:
    """True if a simulator task exists on ``app.state`` and is not yet done.

    Reads ``app.state.sc_simulator_task`` via the request (never imports the
    app). Treats a missing/None task as "not running". Used by ``/status`` and
    the start/stop endpoints to decide idempotently.
    """
    task = getattr(request.app.state, "sc_simulator_task", None)
    return task is not None and not task.done()


async def _stop_simulator(request: Request) -> None:
    """Stop the running simulator (if any) and clear its ``app.state`` handles.

    Signals the adapter to stop, cancels the background task, awaits it, then
    clears ``sc_simulator`` / ``sc_simulator_task`` so the pipeline reports
    stopped. Idempotent: safe to call when nothing is running. Each step is
    guarded so a failure in one does not leave stale state behind. Shared by the
    stop endpoint and reused for a clean restart.
    """
    state = request.app.state
    simulator = getattr(state, "sc_simulator", None)
    sim_task = getattr(state, "sc_simulator_task", None)

    if simulator is not None:
        try:
            simulator.stop()
        except Exception:  # noqa: BLE001
            logger.exception("Failed to signal source-comparison simulator stop")

    if sim_task is not None:
        try:
            sim_task.cancel()
            await asyncio.gather(sim_task, return_exceptions=True)
            logger.info("Source-comparison simulator stopped via API")
        except Exception:  # noqa: BLE001
            logger.exception("Failed to stop source-comparison simulator task")

    state.sc_simulator = None
    state.sc_simulator_task = None


@router.post("/source-comparison/simulator/stop")
async def stop_simulator(request: Request):
    """Stop the running simulator so ingestion can be halted from the app.

    Signals the adapter and cancels its background task, then clears the
    ``app.state`` handles so ``/status`` reports ``simulator_running: false``.
    Idempotent — stopping when already stopped is a no-op that still returns
    ``{running: false}``.
    """
    await _stop_simulator(request)
    return {"running": False}


@router.post("/source-comparison/simulator/start")
async def start_simulator(request: Request):
    """(Re)start the simulator, pushing records through the ingestion path.

    Idempotent / guarded against double-start: if a simulator task is already
    running, this is a no-op returning ``{running: true}``. Otherwise it creates
    a fresh :class:`SimulatorAdapter`, launches
    ``asyncio.create_task(sim.run_forever(push_fn=ingestion.ingest))``, and
    stores the adapter + task on ``app.state`` so ``/status`` and the stop
    endpoint can reach them.
    """
    state = request.app.state

    if _simulator_running(request):
        logger.info("Simulator start requested but already running (no-op)")
        return {"running": True}

    # Clear any finished/stale handles before starting a fresh run.
    await _stop_simulator(request)

    try:
        simulator = SimulatorAdapter()
        sim_task = asyncio.create_task(
            simulator.run_forever(push_fn=ingestion.ingest),
            name="sc-simulator",
        )
        state.sc_simulator = simulator
        state.sc_simulator_task = sim_task
        logger.info("Source-comparison simulator started via API")
    except Exception:  # noqa: BLE001 — a failed start must not 500 the endpoint
        logger.exception("Failed to start source-comparison simulator via API")
        state.sc_simulator = None
        state.sc_simulator_task = None
        return {"running": False}

    return {"running": True}


@router.get("/source-comparison/status")
async def get_status(request: Request):
    """Return a pipeline status snapshot for the ingestion monitor (Req 9.4).

    Fields (matching the design's ``SCStatus`` shape):

      * ``ingested`` — count of persisted, accepted source records
        (``sc_source_records``).
      * ``rejected`` — count of retained rejected records
        (``sc_rejected_records``).
      * ``groups_partial`` — aligned groups whose ``alignment_state`` is
        ``partial``.
      * ``groups_complete`` — aligned groups whose ``alignment_state`` is
        ``complete``.
      * ``simulator_running`` — ``true`` when a simulator task exists on
        ``app.state`` and has not finished, so the monitor can show/toggle the
        feed.
      * ``assumptions`` — the assumptions/open-items snapshot (same items as the
        report header banner), so the monitor can surface the
        "assumed — pending client confirmation" items.

    Counts are read straight from the ``sc_*`` tables, so the snapshot is valid
    even if the background worker or simulator are disabled/stopped.
    """
    db = await get_db()

    async def _count(sql: str, params: tuple = ()) -> int:
        cursor = await db.execute(sql, params)
        row = await cursor.fetchone()
        # row is a single-column count; support both Row mapping and tuple.
        try:
            return int(row[0]) if row is not None else 0
        except (TypeError, KeyError, IndexError):
            return 0

    ingested = await _count("SELECT COUNT(*) FROM sc_source_records")
    rejected = await _count("SELECT COUNT(*) FROM sc_rejected_records")
    groups_partial = await _count(
        "SELECT COUNT(*) FROM sc_aligned_groups WHERE alignment_state = ?",
        (AlignmentState.PARTIAL.value,),
    )
    groups_complete = await _count(
        "SELECT COUNT(*) FROM sc_aligned_groups WHERE alignment_state = ?",
        (AlignmentState.COMPLETE.value,),
    )

    # Reuse the report header so the monitor's assumptions banner matches the
    # report banner exactly (comparison_config.assumptions).
    assumptions = report.report_header().get("assumptions", [])

    simulator_running = _simulator_running(request)

    logger.info(
        "status snapshot: ingested=%d rejected=%d groups_partial=%d "
        "groups_complete=%d simulator_running=%s assumptions=%d",
        ingested,
        rejected,
        groups_partial,
        groups_complete,
        simulator_running,
        len(assumptions),
    )

    return {
        "ingested": ingested,
        "rejected": rejected,
        "groups_partial": groups_partial,
        "groups_complete": groups_complete,
        "simulator_running": simulator_running,
        "assumptions": assumptions,
    }
