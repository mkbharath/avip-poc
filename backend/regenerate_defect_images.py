"""
Regenerate defective demo images with realistic, visible defects per part family.
Defects are drawn on top of the clean base images to look like real inspection findings.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import random

DEMO_DIR = Path("demo_data/images")
ANGLES = ["top", "north", "south", "east", "west"]
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)


def add_scratch(draw: ImageDraw.Draw, img: Image.Image, w: int, h: int):
    """Add a visible linear scratch — bright line with edge shadow."""
    # Random diagonal scratch
    x1 = random.randint(w // 6, w // 2)
    y1 = random.randint(h // 6, h // 3)
    length = random.randint(120, 220)
    angle_offset = random.randint(-30, 30)
    x2 = x1 + length
    y2 = y1 + angle_offset

    # Shadow edge (dark line slightly offset)
    draw.line([(x1 - 1, y1 + 1), (x2 - 1, y2 + 1)], fill=(90, 92, 96), width=2)
    # Main scratch (bright/reflective)
    draw.line([(x1, y1), (x2, y2)], fill=(220, 222, 230), width=1)
    # A second shorter scratch nearby
    x3, y3 = x1 + 20, y1 + 40
    x4, y4 = x3 + random.randint(60, 100), y3 + random.randint(-15, 15)
    draw.line([(x3 - 1, y3 + 1), (x4 - 1, y4 + 1)], fill=(95, 97, 100), width=1)
    draw.line([(x3, y3), (x4, y4)], fill=(215, 217, 225), width=1)


def add_dent(draw: ImageDraw.Draw, img: Image.Image, w: int, h: int):
    """Add a visible dent — circular depression with shadow/highlight ring."""
    cx = random.randint(w // 3, 2 * w // 3)
    cy = random.randint(h // 3, 2 * h // 3)
    radius = random.randint(20, 40)

    # Outer shadow ring (darker)
    draw.ellipse([(cx - radius - 3, cy - radius - 3), (cx + radius + 3, cy + radius + 3)],
                 fill=None, outline=(110, 112, 116), width=3)
    # Dent center (slightly darker than surface)
    draw.ellipse([(cx - radius, cy - radius), (cx + radius, cy + radius)],
                 fill=(145, 147, 151))
    # Highlight on edge (light reflection on rim)
    draw.arc([(cx - radius, cy - radius), (cx + radius, cy + radius)],
             start=200, end=320, fill=(200, 202, 210), width=2)
    # Inner depth indication
    draw.ellipse([(cx - radius // 2, cy - radius // 2), (cx + radius // 2, cy + radius // 2)],
                 fill=(135, 137, 141))


def add_contamination(draw: ImageDraw.Draw, img: Image.Image, w: int, h: int):
    """Add particulate contamination — dark spots/splotches."""
    cx = random.randint(w // 4, 3 * w // 4)
    cy = random.randint(h // 3, 2 * h // 3)

    # Multiple small dark particles
    for _ in range(random.randint(8, 20)):
        px = cx + random.randint(-40, 40)
        py = cy + random.randint(-30, 30)
        size = random.randint(2, 7)
        darkness = random.randint(50, 90)
        draw.ellipse([(px, py), (px + size, py + size)], fill=(darkness, darkness + 2, darkness - 2))

    # A larger smudge/splotch
    smudge_points = []
    for i in range(8):
        angle = i * (360 / 8) + random.randint(-20, 20)
        r = random.randint(15, 35)
        sx = cx + int(r * np.cos(np.radians(angle)))
        sy = cy + int(r * np.sin(np.radians(angle)))
        smudge_points.append((sx, sy))
    if len(smudge_points) >= 3:
        draw.polygon(smudge_points, fill=(70, 65, 60))


def add_missing_component(draw: ImageDraw.Draw, img: Image.Image, w: int, h: int):
    """Add a missing component indicator — empty hole/socket where something should be."""
    # Draw a socket/mounting point that's clearly empty
    cx = random.randint(w // 5, 2 * w // 5)
    cy = random.randint(h // 5, 2 * h // 5)

    # Socket outline (where a fastener/component should be)
    draw.ellipse([(cx - 15, cy - 15), (cx + 15, cy + 15)], fill=(40, 42, 46), outline=(100, 102, 106), width=2)
    # Thread marks inside
    for r in [5, 10]:
        draw.arc([(cx - r, cy - r), (cx + r, cy + r)], start=0, end=360, fill=(60, 62, 66), width=1)
    # Red annotation circle (inspection marking)
    draw.ellipse([(cx - 22, cy - 22), (cx + 22, cy + 22)], outline=(220, 50, 50), width=2)
    # Arrow pointing to it
    draw.line([(cx + 25, cy - 25), (cx + 50, cy - 50)], fill=(220, 50, 50), width=2)
    draw.text((cx + 52, cy - 58), "MISSING", fill=(220, 50, 50))


def add_crack(draw: ImageDraw.Draw, img: Image.Image, w: int, h: int):
    """Add a crack — jagged dark line with branching."""
    x = random.randint(w // 3, 2 * w // 3)
    y = random.randint(h // 4, h // 2)

    # Main crack path (jagged)
    points = [(x, y)]
    for _ in range(12):
        x += random.randint(3, 12)
        y += random.randint(-5, 8)
        points.append((x, y))

    # Draw crack with dark line
    draw.line(points, fill=(50, 52, 56), width=2)
    # Highlight edge (stress whitening)
    highlight_points = [(px + 1, py - 1) for px, py in points]
    draw.line(highlight_points, fill=(200, 200, 205), width=1)

    # Branch
    branch_start = points[len(points) // 2]
    bx, by = branch_start
    branch_points = [(bx, by)]
    for _ in range(5):
        bx += random.randint(2, 8)
        by += random.randint(2, 8)
        branch_points.append((bx, by))
    draw.line(branch_points, fill=(55, 57, 61), width=1)


def make_defective_metal_plate(angle: str) -> Image.Image:
    """Load clean metal plate image and add defects appropriate to the angle."""
    clean_path = DEMO_DIR / "metal_plate" / "clean" / f"{angle}.jpg"
    img = Image.open(clean_path).copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size

    if angle == "top":
        # Top view: scratch + contamination
        add_scratch(draw, img, w, h)
        add_contamination(draw, img, w, h)
    elif angle == "north":
        # North side: dent on the face
        add_dent(draw, img, w, h)
    elif angle == "south":
        # South side: missing component (e.g., missing fastener)
        add_missing_component(draw, img, w, h)
    elif angle == "east":
        # East edge: crack
        add_crack(draw, img, w, h)
    elif angle == "west":
        # West edge: scratch on label area
        add_scratch(draw, img, w, h)

    return img


def make_defective_pcb(angle: str) -> Image.Image:
    """PCB with electronic defects."""
    img = Image.new("RGB", IMG_SIZE, (35, 85, 45))  # PCB green base
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE

    # PCB texture - traces and pads
    for _ in range(30):
        tx = random.randint(0, w)
        ty = random.randint(0, h)
        tw = random.randint(80, 200)
        draw.line([(tx, ty), (tx + tw, ty)], fill=(40, 100, 55), width=2)
    for _ in range(20):
        tx = random.randint(0, w)
        ty = random.randint(0, h)
        th = random.randint(60, 150)
        draw.line([(tx, ty), (tx, ty + th)], fill=(40, 100, 55), width=2)

    # Component pads
    for _ in range(15):
        px = random.randint(50, w - 50)
        py = random.randint(50, h - 50)
        draw.rectangle([(px, py), (px + 8, py + 4)], fill=(180, 160, 80))

    # IC packages
    for ix, iy in [(200, 150), (400, 250), (150, 350)]:
        draw.rectangle([(ix, iy), (ix + 50, iy + 50)], fill=(25, 25, 30), outline=(60, 60, 65))
        # Pins
        for p in range(6):
            draw.rectangle([(ix - 4, iy + 5 + p * 8), (ix, iy + 8 + p * 8)], fill=(180, 160, 80))
            draw.rectangle([(ix + 50, iy + 5 + p * 8), (ix + 54, iy + 8 + p * 8)], fill=(180, 160, 80))

    if angle == "top":
        # Missing capacitor
        cx, cy = 320, 180
        draw.rectangle([(cx, cy), (cx + 12, cy + 8)], outline=(220, 50, 50), width=2)
        draw.text((cx + 15, cy - 5), "C14 MISSING", fill=(220, 50, 50))
        # Solder bridge
        draw.rectangle([(410, 255), (420, 275)], fill=(180, 160, 80))  # Bridge
        draw.ellipse([(408, 253), (422, 277)], outline=(220, 150, 50), width=2)
    elif angle in ("north", "south"):
        # Contamination / flux residue
        add_contamination(draw, img, w, h)
    else:
        # Board edge damage
        add_crack(draw, img, w, h)

    return img


def make_defective_weldment(angle: str) -> Image.Image:
    """Welded stainless component with weld defects."""
    img = Image.new("RGB", IMG_SIZE, (160, 162, 168))  # Stainless steel
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE

    # Brushed stainless texture
    for y in range(h):
        noise = random.randint(-3, 3)
        gray = 160 + noise + int(5 * np.sin(y * 0.05))
        draw.line([(0, y), (w, y)], fill=(gray, gray, gray + 3))

    # Weld bead (raised textured line)
    weld_y = h // 2
    for x in range(80, w - 80):
        wy = weld_y + random.randint(-2, 2)
        shade = random.randint(130, 145)
        draw.ellipse([(x - 1, wy - 4), (x + 1, wy + 4)], fill=(shade, shade, shade + 3))

    # Heat-affected zone (discoloration)
    for x in range(80, w - 80):
        for dy in range(6, 15):
            alpha = max(0, 200 - dy * 15)
            if random.random() > 0.3:
                draw.point((x, weld_y + dy), fill=(180, 150 + random.randint(0, 20), 100))
                draw.point((x, weld_y - dy), fill=(180, 150 + random.randint(0, 20), 100))

    if angle == "top":
        # Contamination on surface
        add_contamination(draw, img, w, h)
    elif angle in ("north", "south"):
        # Heat tint / discoloration near weld
        for x in range(150, 350):
            for y in range(weld_y + 15, weld_y + 45):
                if random.random() > 0.5:
                    draw.point((x, y), fill=(160, 130, 80))
    else:
        # Porosity in weld
        for _ in range(8):
            px = random.randint(100, w - 100)
            py = weld_y + random.randint(-3, 3)
            size = random.randint(2, 5)
            draw.ellipse([(px, py), (px + size, py + size)], fill=(60, 62, 66))

    return img


def make_defective_generic(angle: str, family: str) -> Image.Image:
    """Generic defective part."""
    img = Image.new("RGB", IMG_SIZE, (165, 167, 171))
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE

    # Add texture
    for _ in range(300):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        shade = random.randint(155, 180)
        draw.point((x, y), fill=(shade, shade, shade))

    # Add defects
    if angle in ("top", "north"):
        add_scratch(draw, img, w, h)
    elif angle in ("south",):
        add_dent(draw, img, w, h)
    else:
        add_contamination(draw, img, w, h)

    draw.text((20, h - 30), f"{family}/{angle} [DEFECTIVE]", fill=(200, 60, 60))
    return img


def main():
    families_generators = {
        "metal_plate": make_defective_metal_plate,
        "pcb": make_defective_pcb,
        "weldment": make_defective_weldment,
        "screw": lambda angle: make_defective_generic(angle, "screw"),
        "cable": lambda angle: make_defective_generic(angle, "cable"),
    }

    for family, generator in families_generators.items():
        out_dir = DEMO_DIR / family / "defective"
        out_dir.mkdir(parents=True, exist_ok=True)

        for angle in ANGLES:
            img = generator(angle)

            img.save(out_dir / f"{angle}.jpg", quality=92)
            thumb = img.copy()
            thumb.thumbnail(THUMB_SIZE)
            thumb.save(out_dir / f"{angle}_thumb.jpg", quality=85)

            print(f"  ✓ {family}/defective/{angle}.jpg")

    print("\nDone! All defective demo images regenerated.")


if __name__ == "__main__":
    main()
