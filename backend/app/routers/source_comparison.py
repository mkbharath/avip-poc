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

import json
import logging

from fastapi import APIRouter, Query, Request
from fastapi.responses import JSONResponse, Response

from app.db.database import get_db
from app.models.source_comparison import AlignmentState, DecideRequest
from app.services import alignment, ingestion, report, sc_review

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
async def get_review_queue():
    """Return the pending discrepancy review queue (Req 6.1, 6.2).

    Delegates to :func:`app.services.sc_review.get_review_queue`, which returns
    the ``{data, total_count}`` envelope shaped like AVIP's existing review
    queue so the workbench UI can reuse the native review patterns. Only
    ``pending`` discrepancies appear — confirmed/dismissed ones are excluded so
    the queue shows exactly the outstanding review work.
    """
    return await sc_review.get_review_queue()


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
    return discrepancy.model_dump(mode="json")


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
) -> dict[str, str]:
    """Build the ``build_report`` filter dict from optional query params.

    Only non-``None`` filters are included so omitted params match everything
    (Req 7.3). The service accepts the requirement's short filter names
    (``part``, ``lot``, ``field``) directly.
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
):
    """Return the confirmed-only discrepancy report (Req 7.1, 7.2, 7.3).

    Optional query filters (all ANDed, each matching all when omitted):
    ``part`` → ``part_number``, ``lot`` → ``lot_number``, ``source`` (keep only
    rows carrying a value from that source), ``field`` → ``field_name``, and
    ``provenance``. Delegates to :func:`app.services.report.build_report`, which
    returns **confirmed-only** rows (Property 5) each complete with part+lot,
    field name + type, the per-source ``values`` dict, and provenance
    (Property 8, Req 7.2).

    Response envelope ``{data, total_count}`` matches the other list endpoints.
    """
    rows = await report.build_report(
        _report_filters(part, lot, source, field, provenance)
    )
    return {"data": rows, "total_count": len(rows)}


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

    rows = await report.build_report(
        _report_filters(part, lot, source, field, provenance)
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


@router.get("/source-comparison/status")
async def get_status():
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

    logger.info(
        "status snapshot: ingested=%d rejected=%d groups_partial=%d "
        "groups_complete=%d assumptions=%d",
        ingested,
        rejected,
        groups_partial,
        groups_complete,
        len(assumptions),
    )

    return {
        "ingested": ingested,
        "rejected": rejected,
        "groups_partial": groups_partial,
        "groups_complete": groups_complete,
        "assumptions": assumptions,
    }
