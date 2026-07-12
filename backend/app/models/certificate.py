"""Certificate models."""

from datetime import datetime

from pydantic import BaseModel

from .inspection import DecisionResult


class Certificate(BaseModel):
    id: str
    inspection_id: str
    token: str
    pdf_url: str
    created_at: datetime


class CertificateVerification(BaseModel):
    valid: bool
    part_number: str
    decision: DecisionResult
    decided_at: datetime
