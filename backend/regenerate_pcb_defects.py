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
    draw.rectangle([(b1x-12, by+35), (b1x+35, by+52)], fill=(255, 120, 0))
    draw.text((b1x-8, by+38), "SOLDER BRIDGE", fill=(255, 255, 255))

    return img


def apply_cold_solder(img: Image.Image) -> Image.Image:
    """
    COLD SOLDER JOINT — dull, grainy, fractured solder on electrolytic cap.
    Very common real defect in power boards. Highly distinctive appearance.
    """
    draw = ImageDraw.Draw(img)
    arr = None  # Will convert when needed

    # Draw a prominent electrolytic capacitor (large, cylindrical)
    cx, cy = 200, 240
    r = 28

    # Capacitor body (black with stripe)
    draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], fill=(12, 12, 16), outline=(50, 50, 55), width=3)
    # Polarity stripe (lighter band)
    draw.arc([(cx-r+3, cy-r+3), (cx+r-3, cy+r-3)], 240, 300, fill=(60, 60, 65), width=8)
    # + marker
    draw.line([(cx-8, cy), (cx+8, cy)], fill=(180, 180, 185), width=2)
    draw.line([(cx, cy-8), (cx, cy+8)], fill=(180, 180, 185), width=2)
    # Capacitor top vent (X mark)
    draw.line([(cx-10, cy-10), (cx+10, cy+10)], fill=(30, 30, 35), width=1)
    draw.line([(cx-10, cy+10), (cx+10, cy-10)], fill=(30, 30, 35), width=1)

    # Solder pads
    # Left pad (positive — GOOD solder, shiny)
    lpad_x, lpad_y = cx - r - 20, cy
    draw.ellipse([(lpad_x-12, lpad_y-10), (lpad_x+12, lpad_y+10)], fill=(185, 165, 60), outline=(155, 140, 50))
    draw.ellipse([(lpad_x-7, lpad_y-5), (lpad_x+7, lpad_y+5)], fill=(210, 195, 85))
    draw.ellipse([(lpad_x-3, lpad_y-3), (lpad_x+3, lpad_y+3)], fill=(235, 225, 120))

    # Right pad (negative — COLD solder, dull grey/grainy)
    rpad_x, rpad_y = cx + r + 20, cy
    # Cold joint base (dull, not golden)
    draw.ellipse([(rpad_x-12, rpad_y-10), (rpad_x+12, rpad_y+10)], fill=(130, 120, 105), outline=(110, 100, 88))
    # Grainy texture (cold solder has crystalline structure)
    import random as rnd
    rnd.seed(99)
    for _ in range(120):
        ox = rnd.randint(-11, 11)
        oy = rnd.randint(-9, 9)
        if ox*ox/121 + oy*oy/81 <= 1.0:
            shade = rnd.randint(95, 145)
            draw.point((rpad_x+ox, rpad_y+oy), fill=(shade, shade-8, shade-18))
    # Fracture crack (dark jagged line through joint)
    draw.line([(rpad_x-8, rpad_y-4), (rpad_x-2, rpad_y+2), (rpad_x+5, rpad_y-3), (rpad_x+9, rpad_y+6)],
              fill=(30, 28, 22), width=2)
    draw.line([(rpad_x-7, rpad_y-5), (rpad_x-1, rpad_y+1), (rpad_x+6, rpad_y-4)],
              fill=(180, 165, 140), width=1)

    # Annotation
    draw.line([(rpad_x+15, rpad_y), (rpad_x+55, rpad_y-20)], fill=(255, 120, 0), width=2)
    draw.polygon([(rpad_x+14, rpad_y-3), (rpad_x+14, rpad_y+3), (rpad_x+18, rpad_y)], fill=(255, 120, 0))
    draw.rectangle([(rpad_x+52, rpad_y-35), (rpad_x+145, rpad_y-18)], fill=(255, 120, 0))
    draw.text((rpad_x+56, rpad_y-32), "COLD JOINT", fill=(255, 255, 255))

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
