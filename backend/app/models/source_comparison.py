"""Source-comparison domain models (LAIR / FAIR / SHQ).

Mirrors the `models/inspection.py` style: `str, Enum` enums + `BaseModel`
domain and request/response models. Enum string values are used verbatim in the
`sc_*` DB columns and the frontend TypeScript types, so they must not change.
"""

from enum import Enum
from typing import Literal

from pydantic import BaseModel


class SourceType(str, Enum):
    LAIR = "LAIR"
    FAIR = "FAIR"
    SHQ = "SHQ"


class FieldType(str, Enum):
    NUMERIC = "numeric"
    CATEGORICAL = "categorical"
    IDENTIFIER = "identifier"
    FREE_TEXT = "free_text"


class Provenance(str, Enum):
    EXACT = "exact-match"
    NUMERIC = "numeric-threshold"
    LLM = "llm"
    LLM_UNAVAILABLE = "llm-unavailable"


class ReviewState(str, Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    DISMISSED = "dismissed"


class AlignmentState(str, Enum):
    PARTIAL = "partial"
    COMPLETE = "complete"
    UNMATCHED = "unmatched"


# === Domain / Request Models ===


class IngestRecord(BaseModel):
    """A single inbound source record pushed through the Ingestion API."""

    source: SourceType
    external_record_id: str
    part_number: str
    lot_number: str
    serial_number: str | None = None
    fields: dict[str, object] = {}


class SourceRecord(BaseModel):
    """A persisted source record, once accepted and stored."""

    id: str
    source: SourceType
    external_record_id: str
    part_number: str
    lot_number: str
    serial_number: str | None = None
    fields: dict[str, object] = {}
    group_id: str | None = None
    received_at: str


class AlignedGroup(BaseModel):
    """A group of source records reconciled by common key (part + lot)."""

    id: str
    part_number: str
    lot_number: str
    present_sources: list[SourceType] = []
    alignment_state: AlignmentState
    created_at: str
    updated_at: str
    records: list[SourceRecord] = []


class Discrepancy(BaseModel):
    """A per-part/lot, per-field finding that source values differ."""

    id: str
    group_id: str
    part_number: str
    lot_number: str
    field_name: str
    field_type: FieldType
    values: dict[str, object] = {}
    provenance: Provenance
    review_state: ReviewState = ReviewState.PENDING


class DecideRequest(BaseModel):
    """Review-gate decision recorded against a discrepancy."""

    decision: Literal["confirmed", "dismissed"]
    reviewer: str
    note: str | None = None
