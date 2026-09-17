"""Shared enums for the PCBA TPI Generation feature.

``InputType`` and ``InputStatus`` are defined here — a small, dependency-free
module — so the multimodal LLM provider, ingestion, extraction, mapping, and
generation services can all share one definition without importing one another.
Keeping them here avoids a circular dependency between ``tpi_llm_provider`` and
``tpi_ingestion`` (which are built in parallel) while matching the enum shapes
in the design's Ingestion service section.
"""

from __future__ import annotations

from enum import Enum


class InputType(str, Enum):
    """The four confirmed source-document types per PCBA (design: InputType).

    Text inputs (``testing_procedure``, ``operating_procedure``) go through text
    extraction; visual inputs (``circuit_diagram``, ``drawing``) go through the
    multimodal-LLM path.
    """

    testing_procedure = "testing_procedure"
    operating_procedure = "operating_procedure"
    circuit_diagram = "circuit_diagram"
    drawing = "drawing"


class InputStatus(str, Enum):
    """Per-input ingestion/extraction status (design: InputStatus).

    A parse or provider failure is represented as
    ``flagged_for_manual_annotation`` rather than an exception or a silent drop
    (Req 1.2, 1.4, 2.4).
    """

    ingested = "ingested"
    flagged_for_manual_annotation = "flagged_for_manual_annotation"
