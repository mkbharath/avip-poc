# Feature: avip-source-comparison, Property 3
"""Property 3 — Every flag carries its provenance.

Whenever a comparison check produces a discrepancy, that discrepancy MUST carry
a non-empty provenance identifying which check flagged it (``exact-match``,
``numeric-threshold``, ``llm``, or ``llm-unavailable``). This test generates
arbitrary groups across the categorical, numeric, and free-text checks and
asserts that every produced discrepancy has a non-empty provenance value (and a
non-empty per-source values dict).

_Requirements: 4.4_
_Properties: 3_
"""

import asyncio
from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.source_comparison import (
    AlignedGroup,
    AlignmentState,
    Provenance,
    SourceRecord,
    SourceType,
)
from app.services.comparison import check_exact, check_free_text, check_numeric
from app.services.llm_provider import LLMComparison, MockLLMProvider

_ALL_PROVENANCE_VALUES = {p.value for p in Provenance}


def _group(field: str, values_by_source: dict[SourceType, object]) -> AlignedGroup:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    records = [
        SourceRecord(
            id=f"rec-{source.value}",
            source=source,
            external_record_id=f"ext-{source.value}",
            part_number="PART-1",
            lot_number="LOT-1",
            fields={field: value},
            received_at=now,
        )
        for source, value in values_by_source.items()
    ]
    return AlignedGroup(
        id="group-1",
        part_number="PART-1",
        lot_number="LOT-1",
        present_sources=list(values_by_source.keys()),
        alignment_state=AlignmentState.COMPLETE,
        created_at=now,
        updated_at=now,
        records=records,
    )


def _assert_carries_provenance(discrepancy) -> None:
    assert discrepancy is not None
    # provenance is a non-empty, recognized enum value.
    assert discrepancy.provenance is not None
    assert discrepancy.provenance.value
    assert discrepancy.provenance.value in _ALL_PROVENANCE_VALUES
    # a produced flag always carries the per-source values that disagree.
    assert discrepancy.values


_sources = st.lists(
    st.sampled_from(list(SourceType)), min_size=2, max_size=3, unique=True
)
_categoricals = st.sampled_from(["A36", "A572", "SS304", "Ti", "Inconel"])
_numbers = st.floats(min_value=-1e5, max_value=1e5, allow_nan=False, allow_infinity=False)
_texts = st.text(min_size=0, max_size=40)


@settings(max_examples=100)
@given(sources=_sources, values=st.lists(_categoricals, min_size=2, max_size=3))
def test_categorical_flags_carry_provenance(sources, values):
    values_by_source = {s: values[i % len(values)] for i, s in enumerate(sources)}
    result = check_exact(_group("material_grade", values_by_source), "material_grade")
    if result is not None:
        _assert_carries_provenance(result)
        assert result.provenance is Provenance.EXACT


@settings(max_examples=100)
@given(
    sources=_sources,
    values=st.lists(_numbers, min_size=2, max_size=3),
    threshold=st.one_of(
        st.none(),
        st.floats(min_value=1e-3, max_value=1e3, allow_nan=False, allow_infinity=False),
    ),
)
def test_numeric_flags_carry_provenance(sources, values, threshold):
    values_by_source = {s: values[i % len(values)] for i, s in enumerate(sources)}
    result = check_numeric(_group("diameter", values_by_source), "diameter", threshold)
    if result is not None:
        _assert_carries_provenance(result)
        assert result.provenance is Provenance.NUMERIC


@settings(max_examples=100)
@given(sources=_sources, values=st.lists(_texts, min_size=2, max_size=3))
def test_free_text_flags_carry_provenance(sources, values):
    values_by_source = {s: values[i % len(values)] for i, s in enumerate(sources)}
    result = asyncio.run(
        check_free_text(
            _group("inspector_notes", values_by_source),
            "inspector_notes",
            MockLLMProvider(),
        )
    )
    if result is not None:
        _assert_carries_provenance(result)
        # mock provider succeeds, so a produced flag is an llm judgement.
        assert result.provenance is Provenance.LLM


class _FailingLLMProvider:
    name = "failing"

    async def compare_text(self, a, b) -> LLMComparison:  # noqa: ARG002
        raise RuntimeError("simulated provider outage")


@settings(max_examples=100)
@given(sources=_sources, values=st.lists(_texts, min_size=2, max_size=3))
def test_free_text_provider_failure_flags_carry_provenance(sources, values):
    values_by_source = {s: values[i % len(values)] for i, s in enumerate(sources)}
    result = asyncio.run(
        check_free_text(
            _group("comments", values_by_source),
            "comments",
            _FailingLLMProvider(),
        )
    )
    # A provider failure always produces a flag routed to review, and it carries
    # the llm-unavailable provenance (never empty, never treated as agreeing).
    _assert_carries_provenance(result)
    assert result.provenance is Provenance.LLM_UNAVAILABLE
