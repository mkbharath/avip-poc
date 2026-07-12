"""Part domain models."""

from pydantic import BaseModel


class FamilyThresholds(BaseModel):
    """Decision thresholds per part family."""

    confidence_high: float = 0.85
    confidence_low: float = 0.55
    severity_threshold: str = "major"
    max_findings_pass: int = 0


class CaptureProfile(BaseModel):
    """Camera/lighting configuration per family."""

    cameras: list[str] = ["top", "north", "south", "east", "west"]
    lighting: str = "diffuse-standard"
    exposure_mode: str = "auto"
    polarization: bool = False


class PartFamily(BaseModel):
    """Part family grouping."""

    id: str
    name: str
    display_name: str
    material: str
    surface_finish: str
    thresholds: FamilyThresholds
    capture_profile: CaptureProfile


class Part(BaseModel):
    """Individual part with its family context."""

    id: str
    part_number: str
    revision: str
    family_id: str
    family: PartFamily | None = None
    description: str
    material: str
    surface_finish: str
    supplier: str
    drawing_url: str | None = None
    placement_guide_url: str | None = None
