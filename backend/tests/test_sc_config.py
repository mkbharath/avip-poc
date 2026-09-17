"""Unit tests for the source-comparison config + assumptions registry.

Covers Requirement 8 (Configuration of Comparison Behavior):

  * 8.1 in-scope fields read from config
  * 8.2 per-field numeric thresholds read from config
  * 8.3 common-key definition read from config
  * 8.4 selected LLM provider read from config
  * 8.5 an unresolved placeholder item emits a logged warning naming it and is
        surfaced (returned) rather than silently defaulted

Also asserts the recently-updated registry statuses/labels: the SHQ numeric
benchmark is now ``confirmed`` (CONFIRMED_LABEL) and emits NO warning, while the
latency target, threshold values, and ingestion shape stay ``assumed``
(ASSUMED_LABEL). These tests need no DB — they exercise pure config objects.
"""

import logging

from app.models.source_comparison import FieldType
from app.services.sc_config import (
    ASSUMED_LABEL,
    CONFIRMED_LABEL,
    UNRESOLVED_PLACEHOLDER,
    AssumptionItem,
    ComparisonConfig,
    default_config,
    validate_assumptions,
)

CONFIG_LOGGER = "app.source_comparison.config"


# ── 8.1 in-scope fields read from config ──────────────────────────────────────
def test_in_scope_fields_read_from_config():
    config = default_config()

    # The comprehensive field set is present and readable from config, spanning
    # all four field types (Req 3.1-3.5, surfaced via config per Req 8.1).
    expected_fields = {
        "diameter",
        "thickness",
        "flatness",
        "hardness",
        "material_grade",
        "coating_finish",
        "surface_visual",
        "supplier",
        "part_number",
        "lot_number",
        "serial_number",
        "inspector_notes",
        "comments",
    }
    assert expected_fields.issubset(set(config.fields.keys()))

    # Field types are carried on the config so classify_field can read them.
    assert config.fields["diameter"].type == FieldType.NUMERIC
    assert config.fields["material_grade"].type == FieldType.CATEGORICAL
    assert config.fields["part_number"].type == FieldType.IDENTIFIER
    assert config.fields["inspector_notes"].type == FieldType.FREE_TEXT

    # Fields default to in-scope; the in_scope flag gates comparison (Req 3.7).
    assert all(fc.in_scope for fc in config.fields.values())


def test_out_of_scope_field_gated_via_config():
    config = default_config()
    config.fields["supplier"].in_scope = False
    assert config.fields["supplier"].in_scope is False
    # Other fields remain in scope — the gate is per-field.
    assert config.fields["diameter"].in_scope is True


# ── 8.2 per-field numeric thresholds read from config ─────────────────────────
def test_per_field_numeric_thresholds_read_from_config():
    config = default_config()

    # The threshold map is readable and matches the per-field FieldConfig value.
    assert config.numeric_thresholds["diameter"] == 0.10
    assert config.numeric_thresholds["thickness"] == 0.05
    assert config.numeric_thresholds["flatness"] == 0.02
    assert config.numeric_thresholds["hardness"] == 1.5

    # The numeric FieldConfig carries the same per-field threshold.
    assert config.fields["diameter"].threshold == 0.10
    assert config.fields["hardness"].threshold == 1.5

    # Non-numeric fields carry no threshold.
    assert config.fields["material_grade"].threshold is None


# ── 8.3 common-key definition read from config ────────────────────────────────
def test_common_key_read_from_config():
    config = default_config()
    assert config.common_key == ["part_number", "lot_number"]


# ── 8.4 selected LLM provider read from config ────────────────────────────────
def test_llm_provider_read_from_config():
    config = default_config()
    assert config.llm_provider == "mock"

    # The provider is configurable without code changes.
    custom = ComparisonConfig(llm_provider="openai")
    assert custom.llm_provider == "openai"


# ── 8.5 unresolved placeholder emits a logged warning and is surfaced ─────────
def test_unresolved_placeholder_emits_warning_and_is_surfaced(caplog):
    config = default_config()
    config.assumptions.append(
        AssumptionItem(
            key="open_question",
            label="unresolved",
            status="unresolved",
            value=UNRESOLVED_PLACEHOLDER,
        )
    )

    with caplog.at_level(logging.WARNING, logger=CONFIG_LOGGER):
        returned = validate_assumptions(config)

    # A warning naming the unresolved item is emitted.
    warnings = [r for r in caplog.records if r.levelno == logging.WARNING]
    assert any("open_question" in r.getMessage() for r in warnings)

    # The item is surfaced (returned) rather than silently defaulted away.
    assert any(item.key == "open_question" for item in returned)


def test_unresolved_via_none_value_emits_warning(caplog):
    """A placeholder value can also be represented as ``value is None``."""
    config = ComparisonConfig(
        assumptions=[
            AssumptionItem(key="missing_value", label="unresolved", status="unresolved", value=None)
        ]
    )
    with caplog.at_level(logging.WARNING, logger=CONFIG_LOGGER):
        validate_assumptions(config)

    assert any(
        r.levelno == logging.WARNING and "missing_value" in r.getMessage()
        for r in caplog.records
    )


# ── Seeded assumption items carry correct statuses/labels ─────────────────────
def test_seeded_assumption_labels_and_statuses():
    config = default_config()
    by_key = {item.key: item for item in config.assumptions}

    # SHQ numeric benchmark is now CONFIRMED by the client.
    assert by_key["shq_numeric_benchmark"].status == "confirmed"
    assert by_key["shq_numeric_benchmark"].label == CONFIRMED_LABEL

    # The remaining seeded items stay assumed pending client confirmation.
    for key in ("latency_target", "threshold_values", "ingestion_shape"):
        assert by_key[key].status == "assumed", key
        assert by_key[key].label == ASSUMED_LABEL, key


def test_confirmed_and_assumed_items_emit_no_warning(caplog):
    """The seeded registry (confirmed + assumed only) must produce NO warning."""
    config = default_config()

    with caplog.at_level(logging.WARNING, logger=CONFIG_LOGGER):
        returned = validate_assumptions(config)

    assert [r for r in caplog.records if r.levelno == logging.WARNING] == []

    # All four seeded items are surfaced for the report header banner.
    surfaced = {item.key for item in returned}
    assert {
        "shq_numeric_benchmark",
        "latency_target",
        "threshold_values",
        "ingestion_shape",
    }.issubset(surfaced)
