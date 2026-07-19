"""
Regenerate realistic PCB defect images for scenarios 11 and 12
and kiosk parts 444-027654-003 and 444-027654-004.
"""
import random
import math
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path

DEMO_DIR = Path("demo_data/images")
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)
ANGLES = ["top", "north", "south", "east", "west"]


def make_pcb_base(seed: int = 42) -> Image.Image:
    """Generate a deterministic PCB board base image."""
    random.seed(seed)
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (25, 75, 38))
    draw = ImageDraw.Draw(img)

    # PCB texture
    for y in range(0, h, 2):
        shade = random.randint(-3, 3)
        draw.line([(0, y), (w, y)], fill=(25+shade, 75+shade, 38+shade))

    # Copper traces
    traces_h = [(50, 120), (100, 250), (150, 80), (200, 350), (250, 160),
                (300, 400), (350, 90), (400, 300), (450, 200), (500, 280)]
    for x_start, length in traces_h:
        y = 50 + (x_start * 7) % (h - 100)
        draw.line([(x_start, y), (x_start + length, y)], fill=(185, 155, 55), width=2)
    traces_v = [(80, 150), (180, 200), (320, 180), (420, 250), (550, 120)]
    for x, length in traces_v:
        y = 30 + (x * 3) % (h - 200)
        draw.line([(x, y), (x, y + length)], fill=(185, 155, 55), width=2)

    # ICs at FIXED positions
    ics = [(120, 100, 65, 65), (380, 80, 55, 55), (450, 280, 50, 60),
           (150, 300, 80, 50), (300, 200, 45, 45)]
    for ix, iy, iw, ih in ics:
        draw.rectangle([(ix, iy), (ix+iw, iy+ih)], fill=(18, 18, 22), outline=(35, 35, 40))
        draw.ellipse([(ix+3, iy+3), (ix+8, iy+8)], fill=(60, 60, 65))
        for p in range(iw // 6):
            draw.rectangle([(ix+4+p*6, iy-3), (ix+6+p*6, iy)], fill=(185, 160, 60))
            draw.rectangle([(ix+4+p*6, iy+ih), (ix+6+p*6, iy+ih+3)], fill=(185, 160, 60))
        for p in range(ih // 6):
            draw.rectangle([(ix-3, iy+4+p*6), (ix, iy+6+p*6)], fill=(185, 160, 60))
            draw.rectangle([(ix+iw, iy+4+p*6), (ix+iw+3, iy+6+p*6)], fill=(185, 160, 60))

    # SMD capacitors at FIXED positions
    smd_positions = [(350, 200), (280, 150), (420, 350), (200, 250), (500, 150),
                     (150, 180), (380, 400), (550, 100), (100, 380), (480, 200)]
    for cx, cy in smd_positions:
        draw.rectangle([(cx, cy), (cx+10, cy+5)], fill=(40, 30, 20))
        draw.rectangle([(cx-2, cy), (cx+1, cy+5)], fill=(190, 165, 65))
        draw.rectangle([(cx+9, cy), (cx+12, cy+5)], fill=(190, 165, 65))

    # Connectors
    draw.rectangle([(10, 180), (35, 280)], fill=(35, 35, 40), outline=(70, 70, 75))
    draw.rectangle([(w-40, 150), (w-10, 320)], fill=(35, 35, 40), outline=(70, 70, 75))

    # Silkscreen
    draw.text((20, h-20), "PCB REV E  444-027654", fill=(200, 200, 200))
    draw.text((20, 10), "CircuitPro", fill=(200, 200, 200))

    random.seed()
    return img


def apply_solder_bridge(img: Image.Image) -> Image.Image:
    """
    SOLDER BRIDGE — large, highly visible excess solder shorting two IC pins.
    IC at (380, 80). Target: bottom row of pins.
    """
    draw = ImageDraw.Draw(img)
    ix, iy, iw, ih = 380, 80, 55, 55

    # Pin locations on bottom edge of IC
    pin_y = iy + ih + 2
    pins = [(ix + 4 + p * 9, pin_y) for p in range(6)]

    # Draw all normal pins (bright gold pads)
    for px, py in pins:
        draw.rectangle([(px-2, py), (px+6, py+5)], fill=(190, 165, 55))

    # BRIDGE between pin 3 and pin 4 (index 2 and 3)
    b1x = pins[2][0]
    b2x = pins[3][0] + 6
    by = pin_y

    # Large irregular solder blob covering both pads + gap between them
    # Main blob body (bright molten solder appearance)
    draw.ellipse([(b1x-3, by-4), (b2x+3, by+10)], fill=(220, 200, 80))
    draw.ellipse([(b1x, by-2), (b2x, by+8)], fill=(240, 220, 100))
    # Shiny highlight (reflection of a light source)
    draw.ellipse([(b1x+2, by-1), (b1x+10, by+4)], fill=(255, 250, 190))
    # Irregular edges (realistic solder blob shape)
    pts = [
        (b1x-3, by+2), (b1x, by-4), (b1x+4, by-5),
        (b1x+8, by-4), (b2x-2, by-3), (b2x+3, by),
        (b2x+3, by+6), (b2x, by+10), (b1x+5, by+10), (b1x-2, by+8)
    ]
    draw.polygon(pts, fill=(230, 210, 90))

    # Annotation arrow and label
    draw.line([(b1x+5, by+12), (b1x+5, by+35)], fill=(255, 120, 0), width=2)
    draw.polygon([(b1x+2, by+11), (b1x+8, by+11), (b1x+5, by+8)], fill=(255, 120, 0))
    # No text annotation — bounding box overlay handles identification

    return img


def apply_cold_solder(img: Image.Image) -> Image.Image:
    """
    COLD SOLDER JOINT — shows TWO joints side by side for clear contrast.
    LEFT = good (shiny, golden). RIGHT = cold (dull, grainy, cracked).
    Uses a large through-hole electrolytic capacitor for clear visibility.
    """
    draw = ImageDraw.Draw(img)

    # === LARGE ELECTROLYTIC CAPACITOR in clear area ===
    cx, cy = 320, 240   # center of board, clear area
    r = 32

    # Capacitor body (large black cylinder)
    draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(12, 12, 16), outline=(55, 55, 60), width=3)
    # White polarity stripe
    draw.arc([(cx-r+4, cy-r+4), (cx+r-4, cy+r-4)], 230, 310, fill=(220, 220, 225), width=10)
    # + symbol
    draw.line([(cx-10, cy), (cx+10, cy)], fill=(210, 210, 215), width=2)
    draw.line([(cx, cy-10), (cx, cy+10)], fill=(210, 210, 215), width=2)
    # Vent X marks
    draw.line([(cx-12, cy-12), (cx+12, cy+12)], fill=(25, 25, 30), width=1)
    draw.line([(cx-12, cy+12), (cx+12, cy-12)], fill=(25, 25, 30), width=1)

    # === LEFT PAD — GOOD solder joint (positive lead) ===
    # Large, clear, shiny appearance
    gx, gy = cx - r - 40, cy   # well separated from body
    # Pad base
    draw.ellipse([(gx-18, gy-14), (gx+18, gy+14)], fill=(160, 140, 45), outline=(130, 115, 35), width=1)
    # Solder cone (good wetting)
    draw.ellipse([(gx-14, gy-10), (gx+14, gy+10)], fill=(200, 180, 65))
    draw.ellipse([(gx-9, gy-7), (gx+9, gy+7)], fill=(220, 205, 90))
    draw.ellipse([(gx-5, gy-4), (gx+5, gy+4)], fill=(240, 230, 120))
    # Bright specular highlight
    draw.ellipse([(gx-3, gy-4), (gx+4, gy-1)], fill=(255, 255, 200))
    # "GOOD" label (just a small dot indicator, no text)
    draw.ellipse([(gx-3, gy+16), (gx+3, gy+22)], fill=(50, 200, 80))

    # Right pad — no annotation text (bbox label handles this)
    bx, by = cx + r + 40, cy
    # Pad base (dull)
    draw.ellipse([(bx-18, by-14), (bx+18, by+14)], fill=(110, 100, 85), outline=(90, 82, 70), width=1)
    # Cold solder surface — flat, dull grey, no wetting cone
    draw.ellipse([(bx-14, by-10), (bx+14, by+10)], fill=(125, 115, 98))
    # Crystalline/grainy texture
    import random as rnd
    rnd.seed(99)
    for _ in range(150):
        ox = rnd.randint(-13, 13)
        oy = rnd.randint(-9, 9)
        if ox*ox/169 + oy*oy/81 <= 1.0:
            shade = rnd.randint(90, 145)
            draw.point((bx+ox, by+oy), fill=(shade, shade-10, shade-22))
    # Fracture crack (dark jagged line)
    crack_pts = [(bx-10, by-5), (bx-5, by-1), (bx+1, by-6), (bx+7, by), (bx+11, by+4)]
    draw.line(crack_pts, fill=(28, 25, 18), width=3)
    draw.line(crack_pts, fill=(185, 170, 145), width=1)
    # No text annotation — bounding box overlay handles identification

    # === Connecting traces ===
    draw.line([(gx+18, gy), (cx-r, cy)], fill=(185, 155, 55), width=2)
    draw.line([(bx-18, by), (cx+r, cy)], fill=(185, 155, 55), width=2)

    return img


def save_with_thumb(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), quality=92)
    thumb = img.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(str(path.parent / f"{path.stem}_thumb{path.suffix}"), quality=85)


def main():
    print("Regenerating PCB defect images...")

    # Scenario-11: Solder Bridge
    out_dir = DEMO_DIR / "scenarios/scenario-11"
    out_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_base(seed=42)
        if angle == "top":
            img = apply_solder_bridge(img)
        save_with_thumb(img, out_dir / f"{angle}.jpg")
    print("  ✓ scenario-11 (Solder Bridge)")

    # Scenario-12: Cold Solder Joint
    out_dir = DEMO_DIR / "scenarios/scenario-12"
    out_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_base(seed=42)
        if angle == "top":
            img = apply_cold_solder(img)
        save_with_thumb(img, out_dir / f"{angle}.jpg")
    print("  ✓ scenario-12 (Cold Solder Joint)")

    # Kiosk 444-027654-003: Solder Bridge
    out_dir = DEMO_DIR / "kiosk/444-027654-003"
    out_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_base(seed=42)
        if angle == "top":
            img = apply_solder_bridge(img)
        save_with_thumb(img, out_dir / f"{angle}.jpg")
    print("  ✓ kiosk/444-027654-003 (Solder Bridge)")

    # Kiosk 444-027654-004: Cold Solder Joint
    out_dir = DEMO_DIR / "kiosk/444-027654-004"
    out_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_base(seed=42)
        if angle == "top":
            img = apply_cold_solder(img)
        save_with_thumb(img, out_dir / f"{angle}.jpg")
    print("  ✓ kiosk/444-027654-004 (Cold Solder Joint)")

    print("\nDone!")


if __name__ == "__main__":
    main()
