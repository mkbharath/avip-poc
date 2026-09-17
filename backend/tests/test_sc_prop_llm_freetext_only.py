# Feature: avip-source-comparison, Property 4
"""Property 4 — Comparison dispatch uses the LLM for free-text only.

Field-type-directed dispatch must invoke the LLM provider **iff** a field is
free-text: numeric, categorical, and identifier fields are compared by the
exact-match / numeric-threshold checks and MUST NEVER touch the LLM. This test
builds groups carrying a mix of field types, dispatches each field the same way
``compare_group`` does (``classify_field`` → the matching check), and uses a spy
LLM provider that records every ``compare_text`` call. It then asserts the spy
was invoked exactly for the free-text fields that had two or more present source
values, and for no other field type.

_Requirements: 3.3, 4.3_
_Properties: 4_
"""

import asyncio
from datetime import datetime, timezone

from hypothesis import given, settings
from hypothesis import strategies as st

from app.models.source_comparison import (
    AlignedGroup,
    AlignmentState,
    FieldType,
    SourceRecord,
    SourceType,
)
from app.services.comparison import (
    check_exact,
    check_free_text,
    check_numeric,
    classify_field,
)
from app.services.llm_provider import LLMComparison
from app.services.sc_config import comparison_config

# Representative fields, one per configured type, drawn from the default config.
_FIELD_BY_TYPE = {
    FieldType.NUMERIC: "diameter",
    FieldType.CATEGORICAL: "material_grade",
    FieldType.IDENTIFIER: "serial_number",
    FieldType.FREE_TEXT: "inspector_notes",
}
_ALL_FIELDS = list(_FIELD_BY_TYPE.values())


class _SpyLLMProvider:
    """Records every compare_text call so we can assert who invoked the LLM."""

    name = "spy"

    def __init__(self) -> None:
        self.calls: list[tuple] = []

    async def compare_text(self, a, b) -> LLMComparison:
        self.calls.append((a, b))
        return LLMComparison(differ=(a != b), rationale="spy")


def _group(fields_by_source: dict[SourceType, dict]) -> AlignedGroup:
    now = datetime(2024, 1, 1, tzinfo=timezone.utc).isoformat()
    records = [
        SourceRecord(
            id=f"rec-{source.value}",
            source=source,
            external_record_id=f"ext-{source.value}",
            part_number="PART-1",
            lot_number="LOT-1",
            fields=fields,
            received_at=now,
        )
        for source, fields in fields_by_source.items()
    ]
    return AlignedGroup(
        id="group-1",
        part_number="PART-1",
        lot_number="LOT-1",
        present_sources=list(fields_by_source.keys()),
        alignment_state=AlignmentState.COMPLETE,
        created_at=now,
        updated_at=now,
        records=records,
    )


async def _dispatch(group: AlignedGroup, fields: list[str], spy: _SpyLLMProvider):
    """Dispatch each field via classify_field, mirroring compare_group.

    Only free-text fields reach the (spy) LLM; numeric/categorical/identifier
    are handled by check_numeric / check_exact and never touch the provider.
    """
    for field in fields:
        field_type = classify_field(field, comparison_config)
        if field_type is None:
            continue
        if field_type is FieldType.FREE_TEXT:
            await check_free_text(group, field, spy)
        elif field_type is FieldType.NUMERIC:
            check_numeric(group, field, comparison_config.numeric_thresholds.get(field))
        else:  # CATEGORICAL / IDENTIFIER
            check_exact(group, field)


# A value strategy that fits any field type (numbers work for numeric fields,
# and any of these are valid categorical/identifier/free-text values).
_values = st.sampled_from([1.0, 2.5, 10.0, "A36", "A572", "SN-1", "note x", "note y"])


@settings(max_examples=100)
@given(
    lair=st.dictionaries(st.sampled_from(_ALL_FIELDS), _values),
    shq=st.dictionaries(st.sampled_from(_ALL_FIELDS), _values),
)
def test_llm_invoked_only_for_free_text_fields(lair, shq):
    spy = _SpyLLMProvider()
    group = _group({SourceType.LAIR: lair, SourceType.SHQ: shq})

    asyncio.run(_dispatch(group, _ALL_FIELDS, spy))

    free_text_field = _FIELD_BY_TYPE[FieldType.FREE_TEXT]
    non_free_text = [f for f in _ALL_FIELDS if f != free_text_field]

    # The LLM is invoked ONLY when the free-text field has >= 2 present values.
    free_text_present = int(free_text_field in lair) + int(free_text_field in shq)
    if free_text_present >= 2:
        assert len(spy.calls) >= 1
    else:
        assert spy.calls == []

    # No non-free-text field value ever reaches the LLM. Assert none of the
    # numeric/categorical/identifier values appear in the recorded calls.
    non_free_text_values = set()
    for field in non_free_text:
        for source_fields in (lair, shq):
            if field in source_fields:
                non_free_text_values.add(str(source_fields[field]))
    free_text_values = set()
    for source_fields in (lair, shq):
        if free_text_field in source_fields:
            free_text_values.add(str(source_fields[free_text_field]))

    for a, b in spy.calls:
        # Every value passed to the LLM must originate from the free-text field.
        for passed in (a, b):
            if passed is None:
                continue
            # A value that belongs ONLY to a non-free-text field must not appear.
            if passed in non_free_text_values and passed not in free_text_values:
                raise AssertionError(
                    f"non-free-text value {passed!r} was sent to the LLM"
                )


@settings(max_examples=100)
@given(
    numeric=_values,
    categorical=st.sampled_from(["A36", "A572", "SS304"]),
    identifier=st.sampled_from(["SN-1", "SN-2", "SN-3"]),
)
def test_non_free_text_only_never_invokes_llm(numeric, categorical, identifier):
    # A group with NO free-text field must never invoke the LLM at all.
    spy = _SpyLLMProvider()
    fields = ["diameter", "material_grade", "serial_number"]
    group = _group(
        {
            SourceType.LAIR: {
                "diameter": numeric,
                "material_grade": categorical,
                "serial_number": identifier,
            },
            SourceType.SHQ: {
                "diameter": 999.0,
                "material_grade": "DIFFERENT",
                "serial_number": "SN-DIFF",
            },
        }
    )
    asyncio.run(_dispatch(group, fields, spy))
    assert spy.calls == []
