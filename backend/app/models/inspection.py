"""Inspection domain models."""

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel


class InspectionStatus(str, Enum):
    IDENTIFIED = "identified"
    CAPTURING = "capturing"
    INSPECTING = "inspecting"
    PASSED = "passed"
    FAILED = "failed"
    IN_REVIEW = "in_review"
    OVERRIDDEN = "overridden"


class DecisionResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    REVIEW = "REVIEW"


class Approach(str, Enum):
    RULE = "rule"
    GOLDEN = "golden"
    MODEL = "model"
    ANOMALY = "anomaly"


class Severity(str, Enum):
    MINOR = "minor"
    MAJOR = "major"
    CRITICAL = "critical"


class BoundingBox(BaseModel):
    x: float
    y: float
    width: float
    height: float


class ImageQualityResult(BaseModel):
    passed: bool
    checks: dict[str, bool]
    failure_reason: str | None = None


class InspectionImage(BaseModel):
    id: str
    camera_angle: str
    file_url: str
    thumbnail_url: str
    quality_result: ImageQualityResult


class Finding(BaseModel):
    id: str
    defect_class: str
    approach: Approach
    confidence: float
    severity: Severity
    bbox: BoundingBox | None = None
    mask_url: str | None = None
    heatmap_url: str | None = None
    description: str
    image_id: str | None = None


class Decision(BaseModel):
    result: DecisionResult
    fusion_rule: str
    findings_count: int
    confidence_summary: dict[str, float]


class Override(BaseModel):
    id: str
    old_decision: DecisionResult
    new_decision: DecisionResult
    reason_code: str
    comment: str
    reviewer: str
    created_at: datetime


class Inspection(BaseModel):
    id: str
    part_id: str
    part_number: str
    family_name: str
    supplier: str
    status: InspectionStatus
    decision: Decision | None = None
    images: list[InspectionImage] = []
    findings: list[Finding] = []
    override: Override | None = None
    certificate_id: str | None = None
    started_at: datetime
    decided_at: datetime | None = None
    scenario_id: str | None = None


# === Request Models ===


class CreateInspectionRequest(BaseModel):
    part_number: str
    identification_method: Literal["barcode", "qr", "ocr", "manual"] = "barcode"


class OverrideRequest(BaseModel):
    new_decision: Literal["PASS", "FAIL"]
    reason_code: str
    comment: str
    reviewer: str


# === Queue Models ===


class ReviewQueueItem(BaseModel):
    id: str
    part_number: str
    family_name: str
    supplier: str
    decision: DecisionResult
    defect_classes: list[str]
    confidence_band: str
    age_seconds: int
    priority: int
    started_at: datetime
