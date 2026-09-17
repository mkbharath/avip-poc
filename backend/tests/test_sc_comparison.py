"""Unit tests for the source-comparison checks (task 4.4).

Exercises the three pure/effect-isolated comparison checks in
``app/services/comparison.py`` directly — no DB, no persistence:

  * :func:`check_exact` — identical categorical values agree (no flag);
    differing categorical values flag with provenance ``exact-match``.
  * :func:`check_numeric` — a LAIR reading within the per-field threshold of the
    SHQ reference does NOT flag; one just outside the threshold flags with
    provenance ``numeric-threshold``. Deviation is measured against the SHQ
    reference value (SHQ is the assumed source-of-truth).
  * :func:`check_free_text` — a differing free-text pair is routed to the mock
    LLM and flags with provenance ``llm``; a simulated provider failure yields a
    flagged discrepancy with provenance ``llm-unavailable`` entering as pending
    (never treated as agreeing).

_Requirements: 4.1, 4.2, 4.3, 4.5, 5.5_
"""

from datetime import datetime, timezone

import pytest

from app.models.source_comparison import (
    AlignedGroup,
    AlignmentState,
    FieldType,
    Provenance,
    ReviewState,
    SourceRecord,
    SourceType,
)
from app.services.comparison import check_exact, check_free_text, check_numeric
from app.services.llm_provider import LLMComparison, MockLLMProvider


def _record(source: SourceType, fields: dict) -> SourceRecord:
    return SourceRecord(
        id=f"rec-{source.value}",
        source=source,
        external_record_id=f"ext-{source.value}",
        part_number="PART-1",
        lot_number="LOT-1",
        fields=fields,
        received_at=datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat(),
    )


def _group(records: list[SourceRecord]) -> AlignedGroup:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    return AlignedGroup(
        id="group-1",
        part_number="PART-1",
        lot_number="LOT-1",
        present_sources=[r.source for r in records],
        alignment_state=AlignmentState.COMPLETE,
        created_at=now,
        updated_at=now,
        records=records,
    )


# ── check_exact — categorical (Req 4.1, 4.5) ─────────────────────────────────


def test_check_exact_identical_categorical_does_not_flag():
    group = _group(
        [
            _record(SourceType.LAIR, {"material_grade": "A36"}),
            _record(SourceType.SHQ, {"material_grade": "A36"}),
        ]
    )
    assert check_exact(group, "material_grade") is None


def test_check_exact_differing_categorical_flags_with_exact_match_provenance():
    group = _group(
        [
            _record(SourceType.LAIR, {"material_grade": "A36"}),
            _record(SourceType.SHQ, {"material_grade": "A572"}),
        ]
    )
    discrepancy = check_exact(group, "material_grade")

    assert discrepancy is not None
    assert discrepancy.provenance is Provenance.EXACT
    assert discrepancy.field_name == "material_grade"
    assert discrepancy.review_state is ReviewState.PENDING
    assert discrepancy.values == {"LAIR": "A36", "SHQ": "A572"}


# ── check_numeric — vs SHQ reference (Req 4.2, 4.5) ──────────────────────────


def test_check_numeric_within_threshold_does_not_flag():
    # SHQ reference = 10.00; LAIR = 10.05; threshold = 0.10 -> deviation 0.05
    # is within threshold, so no flag.
    group = _group(
        [
            _record(SourceType.LAIR, {"diameter": 10.05}),
            _record(SourceType.SHQ, {"diameter": 10.00}),
        ]
    )
    assert check_numeric(group, "diameter", threshold=0.10) is None


def test_check_numeric_just_outside_threshold_flags_with_numeric_provenance():
    # SHQ reference = 10.00; LAIR = 10.11; threshold = 0.10 -> deviation 0.11
    # exceeds the threshold, so it flags. Deviation is measured vs the SHQ value.
    group = _group(
        [
            _record(SourceType.LAIR, {"diameter": 10.11}),
            _record(SourceType.SHQ, {"diameter": 10.00}),
        ]
    )
    discrepancy = check_numeric(group, "diameter", threshold=0.10)

    assert discrepancy is not None
    assert discrepancy.provenance is Provenance.NUMERIC
    assert discrepancy.field_name == "diameter"
    assert discrepancy.field_type is FieldType.NUMERIC
    assert discrepancy.review_state is ReviewState.PENDING
    assert discrepancy.values == {"LAIR": 10.11, "SHQ": 10.00}


# ── check_free_text — LLM routed (Req 4.3, 5.5) ──────────────────────────────


@pytest.mark.asyncio
async def test_check_free_text_differing_pair_routes_to_mock_llm_and_flags():
    group = _group(
        [
            _record(SourceType.LAIR, {"inspector_notes": "Minor surface scratch."}),
            _record(SourceType.SHQ, {"inspector_notes": "Deep crack near edge."}),
        ]
    )
    discrepancy = await check_free_text(group, "inspector_notes", MockLLMProvider())

    assert discrepancy is not None
    assert discrepancy.provenance is Provenance.LLM
    assert discrepancy.field_type is FieldType.FREE_TEXT
    assert discrepancy.review_state is ReviewState.PENDING


@pytest.mark.asyncio
async def test_check_free_text_equivalent_pair_does_not_flag():
    group = _group(
        [
            _record(SourceType.LAIR, {"inspector_notes": "Surface OK"}),
            _record(SourceType.SHQ, {"inspector_notes": "  surface ok  "}),
        ]
    )
    # Mock provider normalizes (trim + casefold), so these are equivalent.
    assert await check_free_text(group, "inspector_notes", MockLLMProvider()) is None


class _FailingLLMProvider:
    """A provider that always raises, simulating a provider outage (Req 5.5)."""

    name = "failing"

    async def compare_text(self, a, b) -> LLMComparison:  # noqa: ARG002
        raise RuntimeError("simulated provider outage")


@pytest.mark.asyncio
async def test_check_free_text_provider_failure_yields_llm_unavailable_pending():
    group = _group(
        [
            _record(SourceType.LAIR, {"comments": "note A"}),
            _record(SourceType.SHQ, {"comments": "note B"}),
        ]
    )
    discrepancy = await check_free_text(group, "comments", _FailingLLMProvider())

    # A provider failure must NOT be treated as agreeing: it flags as pending
    # with provenance llm-unavailable so the field is routed to manual review.
    assert discrepancy is not None
    assert discrepancy.provenance is Provenance.LLM_UNAVAILABLE
    assert discrepancy.review_state is ReviewState.PENDING
    assert discrepancy.field_type is FieldType.FREE_TEXT
