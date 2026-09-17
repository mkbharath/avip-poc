"""Source-comparison configuration + assumptions registry.

Extends the `app/config.py` Settings pattern for the source-comparison feature.
Everything the comparison behavior depends on is read from configuration rather
than hardcoded (Req 8.1-8.4): the in-scope field set with types, per-field
numeric thresholds, the common-key definition, and the selected LLM provider.

The `assumptions` registry surfaces open items rather than silently defaulting
them (Req 8.5). Each item carries a ``status`` and a human-facing ``label``:

  (a) ``shq_numeric_benchmark`` — **confirmed by client**: SHQ is the client's
      statistical tool and the confirmed numeric reference / source-of-truth.
      (The per-field numeric threshold *values* themselves remain assumed —
      see ``threshold_values``.)
  (b) ``latency_target`` — assumed: ~5s per record end-to-end under a simulated
      feed of a few records/second.
  (c) ``threshold_values`` — assumed: the per-field numeric deviation thresholds
      (diameter 0.10mm, thickness 0.05mm, flatness 0.02mm, hardness 1.5 HRC) are
      working assumptions pending client confirmation.
  (d) ``ingestion_shape`` — assumed: the honest hybrid ingestion reality — SHQ
      (statistical tool) is near-real-time capable, while FAIR and LAIR are
      inspection reports ingested on report submission (event-on-submission).

``validate_assumptions`` logs ``"assumed"`` and ``"confirmed"`` items at info
level and emits a logged warning only for items still ``"unresolved"`` at a
placeholder value. It returns the registry so it can be surfaced in the report
header banner — a default is never substituted silently.
"""

import logging
from typing import Literal

from pydantic import BaseModel

from app.models.source_comparison import FieldType

logger = logging.getLogger("app.source_comparison.config")

# Human-facing label for items resolved by assumption pending client sign-off.
ASSUMED_LABEL = "assumed — pending client confirmation"

# Human-facing label for items the client has explicitly confirmed.
CONFIRMED_LABEL = "confirmed by client"

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
    ``ASSUMED_LABEL``. ``status="confirmed"`` items have been explicitly
    confirmed by the client and carry ``CONFIRMED_LABEL``. ``status="unresolved"``
    items are still at a placeholder value and MUST be logged and surfaced rather
    than silently defaulted.
    """

    key: str
    label: str
    status: Literal["assumed", "confirmed", "unresolved"]
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
# Per-field numeric deviation thresholds (Req 8.2), sized to be sensible for
# real machined-part dimensions relative to the simulator baselines
# (diameter ~10-150mm, thickness ~1-20mm, flatness ~0.00-0.20mm, hardness
# ~35-60 HRC). A LAIR/FAIR reading is flagged only when it deviates from the
# SHQ baseline by more than the field's threshold below.
DEFAULT_NUMERIC_THRESHOLDS: dict[str, float] = {
    "diameter": 0.10,    # mm
    "thickness": 0.05,   # mm
    "flatness": 0.02,    # mm
    "hardness": 1.5,     # HRC
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
    """The seeded registry of open/confirmed items (Req 8.5).

    Never silently defaulted: every item is surfaced in the report header banner
    and emitted in structured logs. ``shq_numeric_benchmark`` is now confirmed by
    the client; the remaining items stay assumed pending client confirmation.
    """
    return [
        AssumptionItem(
            key="shq_numeric_benchmark",
            label=CONFIRMED_LABEL,
            status="confirmed",
            value=(
                "SHQ is the client's statistical tool and the confirmed numeric "
                "reference / source-of-truth; numeric deviation is measured "
                "against SHQ's value. The per-field numeric threshold VALUES used "
                "for that comparison remain assumed pending client confirmation "
                "(see threshold_values)."
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
        AssumptionItem(
            key="threshold_values",
            label=ASSUMED_LABEL,
            status="assumed",
            value=(
                "The per-field numeric deviation thresholds (diameter 0.10mm, "
                "thickness 0.05mm, flatness 0.02mm, hardness 1.5 HRC) are working "
                "assumptions pending client confirmation."
            ),
        ),
        AssumptionItem(
            key="ingestion_shape",
            label=ASSUMED_LABEL,
            status="assumed",
            value=(
                "Hybrid ingestion: SHQ (the client's statistical tool) is "
                "near-real-time capable via pull/push, while FAIR and LAIR are "
                "inspection reports ingested on report submission "
                "(event-on-submission), not a continuous stream."
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
    them. Items with status ``"assumed"`` or ``"confirmed"`` are logged at info
    level so the resolved / confirmed decisions remain observable.
    """
    non_warning = {"assumed", "confirmed"}
    for item in config.assumptions:
        is_placeholder = item.value is None or item.value == UNRESOLVED_PLACEHOLDER
        if item.status == "unresolved" or (is_placeholder and item.status not in non_warning):
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
