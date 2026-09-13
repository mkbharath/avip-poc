"""Source-comparison configuration + assumptions registry.

Extends the `app/config.py` Settings pattern for the source-comparison feature.
Everything the comparison behavior depends on is read from configuration rather
than hardcoded (Req 8.1-8.4): the in-scope field set with types, per-field
numeric thresholds, the common-key definition, and the selected LLM provider.

Two previously-open items are resolved **by explicit assumption** and are never
silently defaulted (Req 8.5). They are seeded into the `assumptions` registry
with status ``"assumed"`` and label ``"assumed — pending client confirmation"``:

  (a) ``shq_numeric_benchmark`` — SHQ is the numeric reference / source-of-truth
      for numeric-threshold checks (deviation measured against SHQ's value).
  (b) ``latency_target`` — ~5s per record end-to-end under a simulated feed of a
      few records/second.

``validate_assumptions`` emits a logged warning for any assumption still
``"unresolved"`` at a placeholder value and returns the registry so it can be
surfaced in the report header banner — a default is never substituted silently.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.models.source_comparison import FieldType

logger = logging.getLogger("app.source_comparison.config")

# Human-facing label for items resolved by assumption pending client sign-off.
ASSUMED_LABEL = "assumed — pending client confirmation"

# Placeholder sentinel: an assumption still carrying this value is unresolved.
UNRESOLVED_PLACEHOLDER = "[CONFIRM]"


class FieldConfig(BaseModel):
    """Per-field comparison configuration.

    ``type`` drives ``classify_field`` dispatch (Req 3.6); ``in_scope`` gates the
    field out of comparison when false (Req 3.7); ``threshold`` is the per-field
    numeric deviation threshold, used only for numeric fields (Req 8.2).
    """

    type: FieldType
    in_scope: bool = True
    threshold: float | None = None


class AssumptionItem(BaseModel):
    """A registry entry surfacing an open item resolved by assumption (Req 8.5).

    ``status="assumed"`` items are decided pending client confirmation and carry
    ``ASSUMED_LABEL``. ``status="unresolved"`` items are still at a placeholder
    value and MUST be logged and surfaced rather than silently defaulted.
    """

    key: str
    label: str
    status: Literal["assumed", "unresolved"]
    value: str | None = None


class ComparisonConfig(BaseModel):
    """Top-level, configurable comparison behavior (Req 8.1-8.5)."""

    common_key: list[str] = ["part_number", "lot_number"]
    fields: dict[str, FieldConfig] = {}
    numeric_thresholds: dict[str, float] = {}
    llm_provider: str = "mock"
    assumptions: list[AssumptionItem] = []


# ── Default comprehensive field set (Req 3.1-3.5) ─────────────────────────────
# Field types are set so classify_field can read them directly. Numeric fields
# carry a per-field deviation threshold (Req 8.2). SHQ is the numeric reference
# (assumed — see shq_numeric_benchmark).
DEFAULT_NUMERIC_THRESHOLDS: dict[str, float] = {
    "diameter": 0.05,    # mm
    "thickness": 0.02,   # mm
    "flatness": 0.01,    # mm
    "hardness": 2.0,     # HRC
}

DEFAULT_FIELDS: dict[str, FieldConfig] = {
    # Numeric (Req 3.2)
    "diameter": FieldConfig(type=FieldType.NUMERIC, threshold=DEFAULT_NUMERIC_THRESHOLDS["diameter"]),
    "thickness": FieldConfig(type=FieldType.NUMERIC, threshold=DEFAULT_NUMERIC_THRESHOLDS["thickness"]),
    "flatness": FieldConfig(type=FieldType.NUMERIC, threshold=DEFAULT_NUMERIC_THRESHOLDS["flatness"]),
    "hardness": FieldConfig(type=FieldType.NUMERIC, threshold=DEFAULT_NUMERIC_THRESHOLDS["hardness"]),
    # Categorical (Req 3.3)
    "material_grade": FieldConfig(type=FieldType.CATEGORICAL),
    "coating_finish": FieldConfig(type=FieldType.CATEGORICAL),
    "surface_visual": FieldConfig(type=FieldType.CATEGORICAL),
    "supplier": FieldConfig(type=FieldType.CATEGORICAL),
    # Identifier (Req 3.4)
    "part_number": FieldConfig(type=FieldType.IDENTIFIER),
    "lot_number": FieldConfig(type=FieldType.IDENTIFIER),
    "serial_number": FieldConfig(type=FieldType.IDENTIFIER),
    # Free-text (Req 3.5)
    "inspector_notes": FieldConfig(type=FieldType.FREE_TEXT),
    "comments": FieldConfig(type=FieldType.FREE_TEXT),
}


def default_assumptions() -> list[AssumptionItem]:
    """The two resolved-by-assumption items, seeded as ``"assumed"`` (Req 8.5).

    Never silently defaulted: both are surfaced in the report header banner and
    emitted in structured logs.
    """
    return [
        AssumptionItem(
            key="shq_numeric_benchmark",
            label=ASSUMED_LABEL,
            status="assumed",
            value=(
                "SHQ is the numeric reference / source-of-truth; numeric "
                "deviation is measured against SHQ's value and flagged when it "
                "exceeds the per-field threshold."
            ),
        ),
        AssumptionItem(
            key="latency_target",
            label=ASSUMED_LABEL,
            status="assumed",
            value=(
                "~5s per record end-to-end under a simulated feed of a few "
                "records/second."
            ),
        ),
    ]


def default_config() -> ComparisonConfig:
    """Build the default comparison configuration with the comprehensive field
    set, per-field numeric thresholds, mock LLM provider, and seeded
    assumptions."""
    return ComparisonConfig(
        common_key=["part_number", "lot_number"],
        fields=dict(DEFAULT_FIELDS),
        numeric_thresholds=dict(DEFAULT_NUMERIC_THRESHOLDS),
        llm_provider="mock",
        assumptions=default_assumptions(),
    )


def validate_assumptions(config: ComparisonConfig) -> list[AssumptionItem]:
    """Startup validation for the assumptions registry (Req 8.5).

    Emits a logged warning for any assumption still ``"unresolved"`` at a
    placeholder value, naming the item — never substituting a default silently.
    Returns the assumptions so callers (e.g. the report header) can surface
    them. Items with status ``"assumed"`` are logged at info level so the
    resolved-by-assumption decisions remain observable.
    """
    for item in config.assumptions:
        is_placeholder = item.value is None or item.value == UNRESOLVED_PLACEHOLDER
        if item.status == "unresolved" or (is_placeholder and item.status != "assumed"):
            logger.warning(
                "Unresolved configuration item '%s' at placeholder value; "
                "surfacing in report header rather than substituting a default.",
                item.key,
            )
        else:
            logger.info(
                "Assumption '%s' resolved by assumption (%s): %s",
                item.key,
                item.label,
                item.value,
            )
    return config.assumptions


# Module-level default instance, mirroring the `settings` singleton in config.py.
comparison_config: ComparisonConfig = default_config()
