"""Generate the two real PNG sample images for the TPI upload-test PCBA.

These are simple, clearly-labeled stand-in images for PCBA-778-100200-050 (RF
Power Amplifier Module) so the review workbench's image-preview panel has a real
raster image to show for the visual inputs (circuit_diagram + drawing). They are
NOT engineering-accurate — they are labeled TEST DATA placeholders that let the
upload → preview flow be demonstrated end to end.

Run from anywhere:

    python backend/sample_data/tpi/_upload_test/generate_images.py

It writes ``circuit_diagram.png`` and ``drawing.png`` next to this script.
Requires Pillow (already present in the backend venv via the vision deps).
"""

from __future__ import annotations

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

OUT_DIR = Path(__file__).resolve().parent
PCBA_ID = "PCBA-778-100200-050"
HEADER = f"TEST DATA — {PCBA_ID}"

# Colors
BG = (248, 250, 252)       # slate-50
INK = (15, 23, 42)         # slate-900
LINE = (51, 65, 85)        # slate-700
ACCENT = (37, 99, 235)     # blue-600
WIRE = (180, 83, 9)        # amber-700 (traces)
HEADER_BG = (30, 41, 59)   # slate-800


def _font(size: int) -> ImageFont.ImageFont:
    """Best-effort truetype font; falls back to the PIL bitmap default."""
    for name in (
        "DejaVuSans-Bold.ttf",
        "Arial.ttf",
        "Helvetica.ttf",
    ):
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            continue
    return ImageFont.load_default()


def _draw_header(draw: ImageDraw.ImageDraw, width: int, title: str) -> None:
    draw.rectangle([0, 0, width, 46], fill=HEADER_BG)
    draw.text((16, 12), HEADER, fill=(226, 232, 240), font=_font(18))
    draw.text((16, 56), title, fill=INK, font=_font(20))


def _box(draw, xy, label, fill=(255, 255, 255)):
    draw.rectangle(xy, outline=LINE, width=3, fill=fill)
    x0, y0, x1, y1 = xy
    draw.text((x0 + 10, y0 + 8), label, fill=INK, font=_font(15))


def generate_circuit_diagram(path: Path) -> None:
    w, h = 720, 460
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    _draw_header(d, w, "Circuit diagram — RF Power Amplifier signal path")

    # Blocks: J1 IN -> U7 -> J2 OUT, with bias into U7.
    _box(d, (40, 210, 150, 270), "J1 IN")
    _box(d, (300, 190, 430, 290), "U7 GaN HEMT", fill=(239, 246, 255))
    _box(d, (580, 210, 690, 270), "J2 OUT")
    _box(d, (300, 60, 430, 120), "28 VDC bias", fill=(254, 249, 195))

    # Wires (traces)
    d.line([(150, 240), (300, 240)], fill=WIRE, width=4)   # J1 -> U7
    d.line([(430, 240), (580, 240)], fill=WIRE, width=4)   # U7 -> J2
    d.line([(365, 120), (365, 190)], fill=WIRE, width=4)   # bias -> U7

    # Match-network hints
    d.text((190, 210), "C1 / L1", fill=ACCENT, font=_font(13))
    d.text((470, 210), "L2 / C4", fill=ACCENT, font=_font(13))
    d.text((375, 150), "R1/R2 divider", fill=ACCENT, font=_font(13))

    d.text(
        (16, h - 30),
        "Illustrative stand-in — not an engineering schematic.",
        fill=(100, 116, 139),
        font=_font(12),
    )
    img.save(path, "PNG")


def generate_drawing(path: Path) -> None:
    w, h = 720, 460
    img = Image.new("RGB", (w, h), BG)
    d = ImageDraw.Draw(img)
    _draw_header(d, w, "Mechanical drawing — board outline")

    # Board outline
    d.rectangle([80, 110, 640, 400], outline=LINE, width=4, fill=(255, 255, 255))
    # Mounting holes (4 corners)
    for cx, cy in [(120, 150), (600, 150), (120, 360), (600, 360)]:
        d.ellipse([cx - 12, cy - 12, cx + 12, cy + 12], outline=ACCENT, width=3)
        d.line([(cx - 16, cy), (cx + 16, cy)], fill=ACCENT, width=1)
        d.line([(cx, cy - 16), (cx, cy + 16)], fill=ACCENT, width=1)

    # Connector cut-outs / labels
    _box(d, (95, 230, 175, 300), "J1")
    _box(d, (545, 230, 625, 300), "J2")
    d.text((330, 250), "U7 flange", fill=INK, font=_font(14))
    d.text((300, 380), "TP4 thermocouple pad", fill=ACCENT, font=_font(12))

    # Dimension hints
    d.text((330, 90), "120.0 mm", fill=(100, 116, 139), font=_font(12))
    d.text((650, 240), "62.0\nmm", fill=(100, 116, 139), font=_font(12))

    d.text(
        (16, h - 30),
        "Illustrative stand-in — not a controlled drawing.",
        fill=(100, 116, 139),
        font=_font(12),
    )
    img.save(path, "PNG")


def main() -> None:
    generate_circuit_diagram(OUT_DIR / "circuit_diagram.png")
    generate_drawing(OUT_DIR / "drawing.png")
    print(f"Wrote circuit_diagram.png and drawing.png to {OUT_DIR}")


if __name__ == "__main__":
    main()
