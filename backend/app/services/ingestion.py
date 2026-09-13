"""Ingestion service for the source-comparison feature (LAIR / FAIR / SHQ).

Entry point for every inbound source record. A source adapter (the simulator by
default, task 7.1) or a real source system pushes an ``IngestRecord`` here via
the router (task 2.2). This service:

  * validates the record against the ingestion schema — Pydantic model validity
    plus the required common-key fields (per config) being present and non-empty
    (Req 1.3, 1.6);
  * on SUCCESS persists it to ``sc_source_records`` (new uuid id, ISO
    ``received_at``, ``fields`` stored as JSON text, ``group_id`` NULL until the
    alignment worker attaches it) and enqueues the persisted ``SourceRecord`` on
    an in-process ``asyncio.Queue`` for the background worker to drain
    (Req 1.4, 1.5, task 7.2);
  * on FAILURE persists the offending record to ``sc_rejected_records`` with its
    source, external record id, raw payload (JSON), reason, and ISO
    ``rejected_at``, then raises ``IngestionRejected`` naming the source and
    record id — a record is NEVER discarded (Req 1.6, 1.7, 9.2).

The HTTP concern stays in the router: this service raises a clean domain error
(``IngestionRejected``) or returns a structured ``IngestResult`` the router
translates into a 202 (accepted) or 422 (rejected, naming source + record id).

Structured logs are emitted for accepted and rejected records (Req 9.4).
"""

import asyncio
import json
import logging
import uuid
from datetime import datetime, timezone

from pydantic import ValidationError

from app.db.database import get_db
from app.models.source_comparison import IngestRecord, SourceRecord
from app.services.sc_config import ComparisonConfig, comparison_config

logger = logging.getLogger("app.source_comparison.ingestion")


# ── In-process ingest queue (shared with the background worker, task 7.2) ─────
# A module-level singleton so the router (producer) and the worker (consumer)
# share exactly one queue. Lazily created so it binds to the running event loop.
_ingest_queue: "asyncio.Queue[SourceRecord] | None" = None


def get_ingest_queue() -> "asyncio.Queue[SourceRecord]":
    """Return the shared in-process ingest queue, creating it on first use.

    The background worker (task 7.2) consumes ``SourceRecord`` items enqueued
    here by :func:`ingest`. Kept as a singleton so producer and consumer share
    one queue within the process.
    """
    global _ingest_queue
    if _ingest_queue is None:
        _ingest_queue = asyncio.Queue()
    return _ingest_queue


# ── Domain error + result the router translates into HTTP status ──────────────


class IngestionRejected(Exception):
    """Raised when a record fails ingestion validation.

    Carries the identifying detail the router surfaces as a 422 body: the
    ``source`` and ``record_id`` (external record id) that were rejected, plus
    the human-readable ``reason``. The rejected record is already persisted to
    ``sc_rejected_records`` before this is raised (Req 1.6, 1.7).
    """

    def __init__(self, source: str | None, record_id: str | None, reason: str):
        self.source = source
        self.record_id = record_id
        self.reason = reason
        super().__init__(
            f"Ingestion rejected for source={source!r} record_id={record_id!r}: {reason}"
        )


class IngestResult:
    """Structured success result for an accepted record.

    The router translates this into a 202 response body. ``record_id`` is the
    new persisted uuid; ``external_record_id`` echoes the source's own id.
    """

    def __init__(self, record_id: str, external_record_id: str, source: str):
        self.record_id = record_id
        self.external_record_id = external_record_id
        self.source = source
        self.accepted = True

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "external_record_id": self.external_record_id,
            "source": self.source,
            "accepted": True,
        }


def _now_iso() -> str:
    """Current UTC time as an ISO 8601 string (matches AVIP timestamp style)."""
    return datetime.now(timezone.utc).isoformat()


def _validate_common_key(record: IngestRecord, config: ComparisonConfig) -> None:
    """Ensure the required common-key fields are present and non-empty.

    The common-key definition is read from config (Req 8.3) — by default
    ``part_number`` + ``lot_number``. A blank or whitespace-only value for any
    common-key field is a schema violation because the record could never be
    aligned. Raises ``ValueError`` with a clear reason on failure.
    """
    missing: list[str] = []
    for key in config.common_key:
        value = getattr(record, key, None)
        if not isinstance(value, str) or not value.strip():
            missing.append(key)
    if missing:
        raise ValueError(
            f"missing or empty required common-key field(s): {', '.join(missing)}"
        )


async def _persist_rejected(
    source: str | None,
    external_record_id: str | None,
    raw_payload: object,
    reason: str,
) -> str:
    """Persist an offending record to ``sc_rejected_records`` (never discard).

    ``raw_payload`` is stored as JSON text; anything not JSON-serializable is
    coerced to its string form so persistence never itself fails (Req 1.7).
    Returns the new rejected-record uuid.
    """
    rejected_id = str(uuid.uuid4())
    try:
        payload_json = json.dumps(raw_payload, default=str)
    except (TypeError, ValueError):
        payload_json = json.dumps({"repr": repr(raw_payload)})

    db = await get_db()
    await db.execute(
        """INSERT INTO sc_rejected_records
               (id, source, external_record_id, raw_payload, reason, rejected_at)
           VALUES (?, ?, ?, ?, ?, ?)""",
        (rejected_id, source, external_record_id, payload_json, reason, _now_iso()),
    )
    await db.commit()
    return rejected_id


async def _persist_source_record(record: IngestRecord) -> SourceRecord:
    """Persist a validated record to ``sc_source_records`` and return it.

    Assigns a new uuid id and ISO ``received_at``; stores ``fields`` as JSON
    text; leaves ``group_id`` NULL (the alignment worker attaches it later).
    """
    record_id = str(uuid.uuid4())
    received_at = _now_iso()
    fields_json = json.dumps(record.fields, default=str)

    db = await get_db()
    await db.execute(
        """INSERT INTO sc_source_records
               (id, source, external_record_id, part_number, lot_number,
                serial_number, fields, group_id, received_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, NULL, ?)""",
        (
            record_id,
            record.source.value,
            record.external_record_id,
            record.part_number,
            record.lot_number,
            record.serial_number,
            fields_json,
            received_at,
        ),
    )
    await db.commit()

    return SourceRecord(
        id=record_id,
        source=record.source,
        external_record_id=record.external_record_id,
        part_number=record.part_number,
        lot_number=record.lot_number,
        serial_number=record.serial_number,
        fields=dict(record.fields),
        group_id=None,
        received_at=received_at,
    )


async def ingest(
    record: IngestRecord,
    *,
    config: ComparisonConfig | None = None,
) -> IngestResult:
    """Validate, persist, and enqueue a single inbound source record.

    On success the record is written to ``sc_source_records`` and the persisted
    ``SourceRecord`` is enqueued for the background worker; an ``IngestResult``
    is returned (Req 1.4, 1.5). On a validation failure the offending record is
    written to ``sc_rejected_records`` and ``IngestionRejected`` is raised naming
    the source and record id (Req 1.6, 1.7). A record is never discarded.

    ``config`` defaults to the module-level ``comparison_config`` and is
    injectable for testing.
    """
    cfg = config or comparison_config

    # The record has already passed Pydantic model validation to be an
    # IngestRecord instance; the remaining schema requirement is the common key.
    try:
        _validate_common_key(record, cfg)
    except ValueError as exc:
        reason = str(exc)
        source = record.source.value if record.source is not None else None
        external_id = record.external_record_id
        await _persist_rejected(source, external_id, record.model_dump(), reason)
        logger.warning(
            "Rejected record: source=%s external_record_id=%s reason=%s",
            source,
            external_id,
            reason,
        )
        raise IngestionRejected(source, external_id, reason) from exc

    persisted = await _persist_source_record(record)
    await get_ingest_queue().put(persisted)

    logger.info(
        "Accepted record: id=%s source=%s external_record_id=%s part_number=%s lot_number=%s",
        persisted.id,
        persisted.source.value,
        persisted.external_record_id,
        persisted.part_number,
        persisted.lot_number,
    )
    return IngestResult(
        record_id=persisted.id,
        external_record_id=persisted.external_record_id,
        source=persisted.source.value,
    )


async def ingest_payload(raw_payload: object) -> IngestResult:
    """Validate an untyped inbound payload, then delegate to :func:`ingest`.

    Useful for the router when the body may not parse into an ``IngestRecord``
    (e.g. wrong types, missing required fields). A Pydantic ``ValidationError``
    is turned into a persisted rejection + ``IngestionRejected`` naming whatever
    source / record id can be recovered from the raw payload (Req 1.6, 1.7), so
    even structurally malformed records are retained rather than dropped.
    """
    try:
        record = IngestRecord.model_validate(raw_payload)
    except ValidationError as exc:
        source = None
        external_id = None
        if isinstance(raw_payload, dict):
            raw_source = raw_payload.get("source")
            source = raw_source if isinstance(raw_source, str) else None
            raw_ext = raw_payload.get("external_record_id")
            external_id = raw_ext if isinstance(raw_ext, str) else None
        reason = f"schema validation failed: {exc.error_count()} error(s)"
        await _persist_rejected(source, external_id, raw_payload, reason)
        logger.warning(
            "Rejected record (schema): source=%s external_record_id=%s reason=%s",
            source,
            external_id,
            reason,
        )
        raise IngestionRejected(source, external_id, reason) from exc

    return await ingest(record)
