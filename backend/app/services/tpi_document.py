"""Document export for the PCBA TPI Generation feature.

Renders a :class:`~app.services.tpi_generation.DraftTpi` into a downloadable
document that is recognizable as a Test Procedure Instruction (Req 5.1),
reusing the portal's existing ``reportlab`` capability already used by
``certificate_gen`` — same ``BytesIO`` buffer, ``SimpleDocTemplate`` on A4,
``getSampleStyleSheet``, and ``Paragraph`` / ``Spacer`` / ``Table`` platypus
flowables (Req 5.1). No dependency beyond ``reportlab`` is introduced.

Template handling follows the draft's ``template_kind`` (Req 5.2, 5.3): section
content and order already come from the mapped template
(``tpi_mapping.map_to_structure``), so rendering simply walks the draft's
sections in order. Whether the structure came from the client's confirmed
template (Req 5.2) or the documented placeholder used while it is a ``[CONFIRM]``
item (Req 5.3) is surfaced honestly in the metadata block rather than hidden.

Incomplete sections (Req 3.4) are never dropped: a section with
``incomplete=True`` is rendered with a visible ``[INCOMPLETE — pending manual
annotation]`` tag so a reviewer/stakeholder sees exactly which sections still
lean on a flagged input.

The single public entry point is :func:`render_tpi_document`, which returns the
PDF as ``bytes`` (read from the in-memory buffer) so callers — e.g. the
``GET /tpi/final/{pcba_id}/export`` endpoint (task 8.3) — can stream it directly
without touching disk.
"""

from __future__ import annotations

import html
import logging
from datetime import datetime, timezone
from io import BytesIO

from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import mm
from reportlab.platypus import (
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from app.services.tpi_generation import DraftTpi
from app.services.tpi_mapping import TpiSection

logger = logging.getLogger("app.tpi.document")

# Visible marker for sections that lean on a flagged input (Req 3.4). Rendered
# rather than hiding the section, so the reader sees it needs manual attention.
_INCOMPLETE_TAG = "[INCOMPLETE — pending manual annotation]"

# Human labels for the honest template-kind metadata line (Req 5.2, 5.3).
_TEMPLATE_KIND_LABELS = {
    "client": "Client-confirmed template",
    "placeholder": "Placeholder structure (client template pending [CONFIRM])",
}


def _escape(text: str) -> str:
    """Escape text for reportlab's mini-HTML paragraph markup and preserve breaks.

    ``Paragraph`` interprets a small HTML-like grammar, so raw ``&``/``<``/``>``
    from extracted content must be escaped or the build can fail. Newlines in the
    composed section content are turned into ``<br/>`` so multi-line mapped
    content keeps its shape in the PDF. Never raises on non-str input.
    """
    safe = html.escape(str(text or ""))
    return safe.replace("\n", "<br/>")


def _render_section(
    section: TpiSection,
    index: int,
    styles,
    heading_style: ParagraphStyle,
    incomplete_style: ParagraphStyle,
    body_style: ParagraphStyle,
) -> list:
    """Build the flowables for one TPI section, in document order.

    Emits a numbered section heading (``1. Test Steps``), an inline
    ``[INCOMPLETE …]`` tag when the section is incomplete (Req 3.4, never
    hidden), the section body, and a small provenance footnote listing how many
    source inputs fed the section (Req 3.3 spirit — the reader sees the section
    is backed by real inputs). Returns the flowables plus trailing spacing.
    """
    flowables: list = []
    title = _escape(section.title) or f"Section {index}"
    flowables.append(Paragraph(f"{index}. {title}", heading_style))

    if section.incomplete:
        flowables.append(Paragraph(_INCOMPLETE_TAG, incomplete_style))

    flowables.append(Paragraph(_escape(section.content), body_style))

    source_count = len(section.source_input_ids)
    if source_count:
        note = (
            f"Derived from {source_count} source "
            f"input{'s' if source_count != 1 else ''}."
        )
        provenance_style = ParagraphStyle(
            "TpiProvenance",
            parent=styles["Normal"],
            fontSize=7,
            textColor=colors.gray,
            spaceBefore=2,
        )
        flowables.append(Paragraph(_escape(note), provenance_style))

    flowables.append(Spacer(1, 12))
    return flowables


def render_tpi_document(draft: DraftTpi) -> bytes:
    """Render a :class:`DraftTpi` as a recognizable TPI PDF and return the bytes.

    Produces a document that reads like a Test Procedure Instruction (Req 5.1):
    a ``"Test Procedure Instruction"`` title with the PCBA id, a metadata block
    (pcba id, template kind, provider, review state, generated timestamp), then
    each :class:`TpiSection` in the draft's order as a numbered, titled section
    with its content.

    Template handling (Req 5.2, 5.3): the section set and order already reflect
    the mapped template, so this walks ``draft.sections`` as-is; ``template_kind``
    is surfaced in the metadata so the document is honest about whether the
    client-confirmed structure (Req 5.2) or the documented placeholder (Req 5.3)
    was used. Incomplete sections carry a visible ``[INCOMPLETE …]`` tag rather
    than being omitted (Req 3.4).

    Reuses the ``certificate_gen`` reportlab pattern — ``BytesIO`` buffer,
    ``SimpleDocTemplate`` on A4, ``getSampleStyleSheet``, ``Paragraph`` /
    ``Spacer`` / ``Table`` — and introduces no new dependency. Returns the PDF
    content as ``bytes`` read back from the buffer, so the export endpoint can
    stream it without writing to disk.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=20 * mm,
        leftMargin=20 * mm,
        topMargin=20 * mm,
        bottomMargin=20 * mm,
        title=f"Test Procedure Instruction — {draft.pcba_id}",
    )

    styles = getSampleStyleSheet()
    title_style = ParagraphStyle(
        "TpiTitle",
        parent=styles["Heading1"],
        fontSize=18,
        spaceAfter=4,
        textColor=colors.HexColor("#156082"),
    )
    subtitle_style = ParagraphStyle(
        "TpiSubtitle",
        parent=styles["Normal"],
        fontSize=11,
        textColor=colors.gray,
        spaceAfter=2,
    )
    heading_style = ParagraphStyle(
        "TpiSectionHeading",
        parent=styles["Heading2"],
        fontSize=13,
        spaceBefore=6,
        spaceAfter=4,
        textColor=colors.HexColor("#1F3A5F"),
    )
    incomplete_style = ParagraphStyle(
        "TpiIncomplete",
        parent=styles["Normal"],
        fontSize=9,
        textColor=colors.HexColor("#C0392B"),
        spaceAfter=4,
    )
    body_style = ParagraphStyle(
        "TpiBody",
        parent=styles["Normal"],
        fontSize=10,
        leading=14,
    )
    footer_style = ParagraphStyle(
        "TpiFooter",
        parent=styles["Normal"],
        fontSize=8,
        textColor=colors.gray,
        alignment=1,
    )

    elements: list = []

    # Header — makes the document recognizable as a TPI (Req 5.1).
    elements.append(Paragraph("Test Procedure Instruction", title_style))
    elements.append(
        Paragraph(f"PCBA: {_escape(draft.pcba_id)}", subtitle_style)
    )
    elements.append(Spacer(1, 12))

    # Metadata block — honest about which template structure was used
    # (template_kind, Req 5.2/5.3) plus provider, review state, and timestamp.
    generated_at = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    template_label = _TEMPLATE_KIND_LABELS.get(
        draft.template_kind, str(draft.template_kind)
    )
    meta_rows = [
        ["PCBA ID", draft.pcba_id],
        ["Template", template_label],
        ["Generated By", draft.provider],
        ["Review State", draft.review_state],
        ["Generated", generated_at],
    ]
    meta_table = Table(meta_rows, colWidths=[120, 340])
    meta_table.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), colors.HexColor("#f0f4f8")),
                ("FONTNAME", (0, 0), (0, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 10),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.lightgrey),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(meta_table)
    elements.append(Spacer(1, 20))

    # Sections in the draft's order (which is the mapped template's order).
    if not draft.sections:
        elements.append(
            Paragraph(
                "No sections were generated for this TPI.",
                incomplete_style,
            )
        )
    else:
        for index, section in enumerate(draft.sections, start=1):
            elements.extend(
                _render_section(
                    section,
                    index,
                    styles,
                    heading_style,
                    incomplete_style,
                    body_style,
                )
            )

    # Footer — identifies the source system, consistent with certificate_gen.
    elements.append(Spacer(1, 16))
    elements.append(
        Paragraph(
            "This Test Procedure Instruction was drafted by the AI Vision "
            "Inspection Platform (AVIP) and is subject to human review before "
            "it is treated as final.",
            footer_style,
        )
    )

    doc.build(elements)
    pdf_bytes = buffer.getvalue()
    buffer.close()

    logger.info(
        "Rendered TPI document for pcba_id=%s: %d section(s), template_kind=%s, "
        "%d bytes",
        draft.pcba_id,
        len(draft.sections),
        draft.template_kind,
        len(pdf_bytes),
    )
    return pdf_bytes
