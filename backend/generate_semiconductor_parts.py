"""
Generate realistic semiconductor manufacturing equipment part images.
Parts: chamber lids, gas distribution plates, electrode housings, etc.
These look like actual Lam Research inspection targets.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import random
import math

DEMO_DIR = Path("demo_data/images")
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)
ANGLES = ["top", "north", "south", "east", "west"]


def make_chamber_lid_top() -> Image.Image:
    """Top view of a circular aluminum chamber lid with bolt pattern and gas ports."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))  # Dark inspection background
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    radius = 200  # Main circular part

    # Circular aluminum body (machined finish)
    for r in range(radius, 0, -1):
        shade = 165 + int(15 * math.sin(r * 0.05)) + random.randint(-2, 2)
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=(shade, shade, shade+3))

    # Concentric machining marks (turning marks on face)
    for r in range(20, radius, 8):
        alpha = 160 + random.randint(-5, 5)
        draw.arc([(cx-r, cy-r), (cx+r, cy+r)], 0, 360, fill=(alpha, alpha, alpha+2), width=1)

    # Bolt hole pattern (12 holes in a circle)
    bolt_radius = 170
    for i in range(12):
        angle = i * 30 * math.pi / 180
        bx = cx + int(bolt_radius * math.cos(angle))
        by = cy + int(bolt_radius * math.sin(angle))
        draw.ellipse([(bx-6, by-6), (bx+6, by+6)], fill=(40, 42, 46), outline=(100, 102, 106), width=1)
        draw.ellipse([(bx-2, by-2), (bx+2, by+2)], fill=(30, 32, 36))

    # Center gas port (larger hole)
    draw.ellipse([(cx-18, cy-18), (cx+18, cy+18)], fill=(35, 37, 41), outline=(90, 92, 96), width=2)
    draw.ellipse([(cx-8, cy-8), (cx+8, cy+8)], fill=(25, 27, 31))

    # O-ring groove (concentric channel)
    oring_r = 145
    draw.arc([(cx-oring_r, cy-oring_r), (cx+oring_r, cy+oring_r)], 0, 360, fill=(120, 122, 126), width=4)
    draw.arc([(cx-oring_r+2, cy-oring_r+2), (cx+oring_r-2, cy+oring_r-2)], 0, 360, fill=(135, 137, 141), width=1)

    # Small gas distribution holes (inner ring)
    inner_r = 80
    for i in range(8):
        angle = i * 45 * math.pi / 180
        gx = cx + int(inner_r * math.cos(angle))
        gy = cy + int(inner_r * math.sin(angle))
        draw.ellipse([(gx-3, gy-3), (gx+3, gy+3)], fill=(50, 52, 56))

    return img


def make_chamber_lid_side() -> Image.Image:
    """Side view of chamber lid showing thickness, flange, and sealing surface."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)

    # Main lid body (horizontal cross-section)
    body_top = h // 3
    body_bot = h // 3 + 60
    draw.rectangle([(80, body_top), (w-80, body_bot)], fill=(168, 170, 174))

    # Flange (wider at top)
    flange_top = body_top - 20
    draw.rectangle([(50, flange_top), (w-50, body_top)], fill=(172, 174, 178))
    # Flange edge highlight
    draw.line([(50, flange_top), (w-50, flange_top)], fill=(190, 192, 196), width=2)

    # Machining marks on face
    for y in range(body_top + 3, body_bot - 3, 3):
        shade = 162 + random.randint(-3, 3)
        draw.line([(85, y), (w-85, y)], fill=(shade, shade, shade+1))

    # O-ring groove (dark line on sealing face)
    groove_y = body_bot - 5
    draw.line([(120, groove_y), (w-120, groove_y)], fill=(110, 112, 116), width=3)

    # Bolt heads visible on flange
    for bx in range(100, w-80, 70):
        by = flange_top + 10
        draw.ellipse([(bx-5, by-5), (bx+5, by+5)], fill=(130, 132, 136), outline=(110, 112, 116))

    # Surface finish indicator
    draw.text((w-120, body_bot+20), "Ra 0.8", fill=(100, 150, 100))

    return img


def make_chamber_lid_north() -> Image.Image:
    """North view — disc seen from front edge with lifting lug."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    # Disc edge (thin horizontal bar — the lid seen from the side)
    draw.rectangle([(cx-180, cy-20), (cx+180, cy+20)], fill=(170, 172, 176))
    # Flange (wider)
    draw.rectangle([(cx-200, cy-6), (cx+200, cy+6)], fill=(162, 164, 168))
    # Top face (foreshortened)
    draw.rectangle([(cx-180, cy-30), (cx+180, cy-20)], fill=(180, 182, 186))

    # Lifting lug
    lug_x = cx + 80
    draw.rectangle([(lug_x-10, cy-55), (lug_x+10, cy-30)], fill=(158, 160, 164), outline=(130, 132, 136))
    draw.ellipse([(lug_x-5, cy-50), (lug_x+5, cy-40)], fill=(50, 52, 56))

    # Edge machining marks
    for x in range(cx-175, cx+175, 4):
        shade = 166 + random.randint(-2, 2)
        draw.line([(x, cy-18), (x, cy+18)], fill=(shade, shade, shade))

    # Dimension
    draw.line([(cx-180, cy+40), (cx+180, cy+40)], fill=(80, 150, 220), width=1)
    draw.text((cx-20, cy+45), "406mm", fill=(80, 150, 220))

    return img


def make_chamber_lid_east() -> Image.Image:
    """East view — right side showing gas inlet port."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    # Disc edge
    draw.rectangle([(cx-150, cy-20), (cx+150, cy+20)], fill=(168, 170, 174))
    # Flange
    draw.rectangle([(cx-165, cy-8), (cx+165, cy+8)], fill=(160, 162, 166))

    # Gas inlet port (protruding tube on right)
    draw.rectangle([(cx+150, cy-10), (cx+195, cy+10)], fill=(165, 167, 171), outline=(130, 132, 136))
    draw.ellipse([(cx+190, cy-8), (cx+200, cy+8)], fill=(55, 57, 61))
    # VCR hex nut
    draw.rectangle([(cx+165, cy-12), (cx+180, cy+12)], outline=(140, 142, 146))

    # Bolt pattern on face
    for bx in range(cx-140, cx+150, 35):
        draw.ellipse([(bx-3, cy-3), (bx+3, cy+3)], fill=(140, 142, 146))

    return img


def make_chamber_lid_west() -> Image.Image:
    """West view — left side showing thermocouple port and part number."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    # Disc edge
    draw.rectangle([(cx-150, cy-20), (cx+150, cy+20)], fill=(168, 170, 174))
    # Flange
    draw.rectangle([(cx-165, cy-8), (cx+165, cy+8)], fill=(160, 162, 166))

    # Thermocouple port (smaller tube on left)
    draw.rectangle([(cx-190, cy-5), (cx-150, cy+5)], fill=(162, 164, 168), outline=(130, 132, 136))
    draw.ellipse([(cx-195, cy-4), (cx-188, cy+4)], fill=(50, 52, 56))

    # Part number engraved on edge
    draw.text((cx-40, cy+25), "839-041322", fill=(130, 132, 136))
    draw.text((cx-25, cy+38), "REV C", fill=(130, 132, 136))

    # Edge texture
    for x in range(cx-145, cx+145, 4):
        shade = 164 + random.randint(-2, 2)
        draw.line([(x, cy-18), (x, cy+18)], fill=(shade, shade, shade))

    return img


def make_gas_distribution_plate() -> Image.Image:
    """Top view of gas distribution plate — hundreds of tiny holes in a pattern."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2
    radius = 190

    # Circular plate body (anodized - slightly darker/bluer aluminum)
    for r in range(radius, 0, -1):
        shade = 145 + int(10 * math.sin(r * 0.03))
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=(shade, shade, shade+5))

    # Hundreds of gas distribution holes in concentric rings
    for ring_r in range(30, 160, 15):
        num_holes = max(8, int(ring_r * 0.4))
        for i in range(num_holes):
            angle = (i * 360 / num_holes + ring_r * 3) * math.pi / 180
            hx = cx + int(ring_r * math.cos(angle))
            hy = cy + int(ring_r * math.sin(angle))
            draw.ellipse([(hx-2, hy-2), (hx+2, hy+2)], fill=(50, 52, 56))

    # Outer bolt ring
    bolt_r = 175
    for i in range(16):
        angle = i * 22.5 * math.pi / 180
        bx = cx + int(bolt_r * math.cos(angle))
        by = cy + int(bolt_r * math.sin(angle))
        draw.ellipse([(bx-5, by-5), (bx+5, by+5)], fill=(45, 47, 51), outline=(90, 92, 96))

    # Center alignment pin
    draw.ellipse([(cx-4, cy-4), (cx+4, cy+4)], fill=(60, 62, 66), outline=(100, 102, 106))

    return img


def make_electrode_housing() -> Image.Image:
    """Anodized housing — darker, with precision features."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = w // 2, h // 2

    # Anodized surface (darker, slightly warm tone)
    radius = 195
    for r in range(radius, 0, -1):
        shade = 95 + int(10 * math.sin(r * 0.04))
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=(shade, shade+2, shade-2))

    # RF contact ring (bright copper ring)
    rf_r = 150
    draw.arc([(cx-rf_r, cy-rf_r), (cx+rf_r, cy+rf_r)], 0, 360, fill=(180, 140, 60), width=6)
    draw.arc([(cx-rf_r+3, cy-rf_r+3), (cx+rf_r-3, cy+rf_r-3)], 0, 360, fill=(200, 160, 70), width=2)

    # Cooling channels visible (machined grooves)
    for ring_r in range(60, 130, 20):
        draw.arc([(cx-ring_r, cy-ring_r), (cx+ring_r, cy+ring_r)], 0, 360, fill=(80, 82, 76), width=3)

    # Mounting inserts (helicoils)
    for i in range(8):
        angle = i * 45 * math.pi / 180
        bx = cx + int(175 * math.cos(angle))
        by = cy + int(175 * math.sin(angle))
        draw.ellipse([(bx-7, by-7), (bx+7, by+7)], fill=(55, 57, 51), outline=(75, 77, 71), width=2)
        # Helicoil thread (spiral hint)
        draw.arc([(bx-5, by-5), (bx+5, by+5)], 0, 270, fill=(65, 67, 61), width=1)

    return img


def make_pcb_top() -> Image.Image:
    """Realistic ESC controller board — DETERMINISTIC layout for consistent bbox alignment."""
    random.seed(42)
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (25, 75, 38))  # FR-4 green
    draw = ImageDraw.Draw(img)

    # PCB texture
    for y in range(0, h, 2):
        shade = random.randint(-3, 3)
        draw.line([(0, y), (w, y)], fill=(25+shade, 75+shade, 38+shade))

    # Copper traces (golden lines)
    for _ in range(40):
        x1 = random.randint(0, w)
        y1 = random.randint(0, h)
        if random.random() > 0.5:
            x2, y2 = x1 + random.randint(50, 250), y1
        else:
            x2, y2 = x1, y1 + random.randint(50, 200)
        draw.line([(x1, y1), (x2, y2)], fill=(185, 155, 55), width=1+random.randint(0,1))

    # ICs (black QFP packages)
    ics = [(120, 100, 65, 65), (380, 80, 55, 55), (450, 280, 50, 60),
           (150, 300, 80, 50), (300, 200, 45, 45)]
    for ix, iy, iw, ih in ics:
        draw.rectangle([(ix, iy), (ix+iw, iy+ih)], fill=(18, 18, 22), outline=(35, 35, 40))
        draw.ellipse([(ix+3, iy+3), (ix+8, iy+8)], fill=(60, 60, 65))  # Pin 1
        for p in range(iw // 6):
            draw.rectangle([(ix+4+p*6, iy-3), (ix+6+p*6, iy)], fill=(185, 160, 60))
            draw.rectangle([(ix+4+p*6, iy+ih), (ix+6+p*6, iy+ih+3)], fill=(185, 160, 60))
        for p in range(ih // 6):
            draw.rectangle([(ix-3, iy+4+p*6), (ix, iy+6+p*6)], fill=(185, 160, 60))
            draw.rectangle([(ix+iw, iy+4+p*6), (ix+iw+3, iy+6+p*6)], fill=(185, 160, 60))

    # Capacitors and resistors (0402/0603 SMDs)
    for _ in range(60):
        cx = random.randint(30, w-30)
        cy = random.randint(30, h-30)
        cw = random.choice([4, 6, 8])
        ch = random.choice([2, 3, 4])
        body_color = random.choice([(40, 30, 20), (90, 70, 50), (20, 20, 60)])
        draw.rectangle([(cx, cy), (cx+cw, cy+ch)], fill=body_color)
        draw.rectangle([(cx-1, cy), (cx+1, cy+ch)], fill=(190, 165, 65))
        draw.rectangle([(cx+cw-1, cy), (cx+cw+1, cy+ch)], fill=(190, 165, 65))

    # Connectors
    draw.rectangle([(10, 180), (35, 280)], fill=(35, 35, 40), outline=(70, 70, 75))
    draw.rectangle([(w-40, 150), (w-10, 320)], fill=(35, 35, 40), outline=(70, 70, 75))

    # Silkscreen
    draw.text((20, h-20), "PCB REV E  444-027654-002", fill=(200, 200, 200))
    draw.text((20, 10), "CircuitPro", fill=(200, 200, 200))

    random.seed()  # Reset seed
    return img


def make_weldment_top() -> Image.Image:
    """Top of welded stainless gas manifold — electropolished with weld seam."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)

    # Rectangular stainless body (bright, reflective)
    margin = 60
    for y in range(margin, h-margin):
        shade = 190 + int(8 * math.sin(y * 0.02)) + random.randint(-2, 2)
        draw.line([(margin, y), (w-margin, y)], fill=(shade, shade, shade+2))

    # Weld seam across the middle (slightly raised, different texture)
    weld_y = h // 2
    for x in range(margin+10, w-margin-10):
        wy = weld_y + int(2 * math.sin(x * 0.1))
        for dy in range(-4, 5):
            shade = 155 + abs(dy) * 6 + random.randint(-3, 3)
            draw.point((x, wy+dy), fill=(shade, shade-2, shade-5))

    # Gas ports (4 VCR fittings)
    ports = [(200, 180), (440, 180), (200, 320), (440, 320)]
    for px, py in ports:
        draw.ellipse([(px-15, py-15), (px+15, py+15)], fill=(175, 177, 181), outline=(140, 142, 146), width=2)
        draw.ellipse([(px-8, py-8), (px+8, py+8)], fill=(50, 52, 56))
        # Hex fitting
        for i in range(6):
            angle = i * 60 * math.pi / 180
            x1 = px + int(13 * math.cos(angle))
            y1 = py + int(13 * math.sin(angle))
            x2 = px + int(13 * math.cos(angle + math.pi/3))
            y2 = py + int(13 * math.sin(angle + math.pi/3))
            draw.line([(x1, y1), (x2, y2)], fill=(145, 147, 151), width=1)

    return img


def make_weldment_side(angle: str) -> Image.Image:
    """Side view of welded gas manifold — showing pipe connections and weld."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)

    # Main rectangular body from the side
    body_top = h // 3
    body_bot = 2 * h // 3
    draw.rectangle([(80, body_top), (w-80, body_bot)], fill=(185, 187, 191))

    # Machining marks
    for y in range(body_top+3, body_bot-3, 3):
        shade = 180 + random.randint(-3, 3)
        draw.line([(85, y), (w-85, y)], fill=(shade, shade, shade+1))

    # Weld seam visible on side
    weld_x = w // 2 if angle in ("north", "south") else w // 3
    for y in range(body_top+5, body_bot-5):
        wx = weld_x + random.randint(-1, 1)
        draw.line([(wx-3, y), (wx+3, y)], fill=(145+random.randint(-5,5), 147, 151))

    # Pipe stub (VCR fitting from the side)
    if angle in ("north", "east"):
        pipe_y = h // 2
        draw.rectangle([(w-80, pipe_y-15), (w-40, pipe_y+15)], fill=(180, 182, 186), outline=(150, 152, 156))
        draw.ellipse([(w-45, pipe_y-12), (w-35, pipe_y+12)], fill=(50, 52, 56))

    return img


def make_screw_assembly_side(angle: str) -> Image.Image:
    """Side view of screw assembly plate — showing plate edge with screw heads."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)

    # Plate body from the side (horizontal bar)
    plate_top = h // 3 + 20
    plate_bot = 2 * h // 3 - 20
    draw.rectangle([(60, plate_top), (w-60, plate_bot)], fill=(168, 170, 174))

    # Chamfered edges
    for i in range(5):
        shade = 180 + i * 2
        draw.line([(60, plate_top+i), (w-60, plate_top+i)], fill=(shade, shade, shade))
        draw.line([(60, plate_bot-i), (w-60, plate_bot-i)], fill=(shade, shade, shade))

    # Screw heads visible as bumps on top surface
    num_screws = 4
    for i in range(num_screws):
        sx = 120 + i * 130
        # Screw head protruding from surface
        draw.arc([(sx-8, plate_top-8), (sx+8, plate_top+4)], 180, 360, fill=(140, 142, 146), width=3)
        draw.line([(sx-5, plate_top-2), (sx+5, plate_top-2)], fill=(110, 112, 116), width=1)

    # Bottom edge — machining marks
    for y in range(plate_top+5, plate_bot-5, 4):
        shade = 162 + random.randint(-2, 2)
        draw.line([(65, y), (w-65, y)], fill=(shade, shade, shade))

    # Dimension annotations
    if angle in ("north", "south"):
        draw.line([(50, plate_top), (50, plate_bot)], fill=(80, 150, 220), width=1)
        draw.text((20, h//2-5), "12.7", fill=(80, 150, 220))

    return img


def make_screw_assembly_top() -> Image.Image:
    """RF feed assembly plate with 8 screw positions."""
    w, h = IMG_SIZE
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)

    # Rectangular mounting plate
    plate = (80, 60, w-80, h-60)
    draw.rectangle(plate, fill=(165, 167, 171))

    # Machining marks
    for y in range(65, h-65, 3):
        shade = 160 + random.randint(-3, 3)
        draw.line([(85, y), (w-85, y)], fill=(shade, shade, shade+1))

    # 8 screw positions (2 rows of 4)
    positions = [
        (170, 160), (280, 160), (390, 160), (500, 160),
        (170, 340), (280, 340), (390, 340), (500, 340),
    ]
    for sx, sy in positions:
        # Countersunk screw head
        draw.ellipse([(sx-14, sy-14), (sx+14, sy+14)], fill=(140, 142, 146), outline=(110, 112, 116), width=2)
        # Phillips cross
        draw.line([(sx-6, sy), (sx+6, sy)], fill=(95, 97, 101), width=2)
        draw.line([(sx, sy-6), (sx, sy+6)], fill=(95, 97, 101), width=2)
        # Highlight
        draw.arc([(sx-12, sy-12), (sx+12, sy+12)], 200, 320, fill=(175, 177, 181), width=1)

    # Center alignment feature
    cx, cy = w//2, h//2
    draw.rectangle([(cx-35, cy-20), (cx+35, cy+20)], outline=(130, 132, 136), width=1)
    draw.line([(cx-5, cy), (cx+5, cy)], fill=(130, 132, 136))
    draw.line([(cx, cy-5), (cx, cy+5)], fill=(130, 132, 136))

    return img


def get_family_image(family: str, angle: str) -> Image.Image:
    """Get the correct image for a family + angle combination.
    All angles show the same part surface with slight lighting/perspective variations."""
    if family == "metal_plate":
        img = make_chamber_lid_top()
    elif family == "pcb":
        img = make_pcb_top()
    elif family == "weldment":
        img = make_weldment_top()
    elif family == "screw":
        img = make_screw_assembly_top()
    else:
        img = make_chamber_lid_top()

    # Apply slight variations per angle (simulates different lighting angles)
    from PIL import ImageEnhance
    if angle == "north":
        img = ImageEnhance.Brightness(img).enhance(1.08)
    elif angle == "south":
        img = ImageEnhance.Brightness(img).enhance(0.92)
    elif angle == "east":
        img = ImageEnhance.Contrast(img).enhance(1.1)
    elif angle == "west":
        img = ImageEnhance.Contrast(img).enhance(0.9)

    return img


# Map scenarios to their family (for angle images)
SCENARIO_FAMILIES = {
    "scenario-01": "metal_plate",
    "scenario-02": "metal_plate",
    "scenario-03": "metal_plate",
    "scenario-04": "screw",
    "scenario-05": "weldment",
    "scenario-06": "metal_plate",
    "scenario-07": "metal_plate",
    "scenario-08": "pcb",
    "scenario-09": "weldment",
    "scenario-10": "metal_plate",
    "scenario-11": "pcb",
    "scenario-12": "pcb",
}

SCENARIO_DEFECTS = {
    "scenario-01": None,
    "scenario-02": "scratch",
    "scenario-03": "dent",
    "scenario-04": "missing",
    "scenario-05": "contamination",
    "scenario-06": "anomaly",
    "scenario-07": "anomaly",
    "scenario-08": "pcb_defects",
    "scenario-09": "anomaly",
    "scenario-10": "scratch",
    "scenario-11": "lifted_pad",
    "scenario-12": "tombstone",
}


def save_with_thumb(img: Image.Image, path: Path):
    """Save image and its thumbnail."""
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), quality=92)
    thumb = img.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(str(path.parent / f"{path.stem}_thumb{path.suffix}"), quality=85)


def main():
    print("Generating semiconductor part images...")

    # Clean family images (for kiosk capture)
    for family in ["metal_plate", "pcb", "weldment", "screw"]:
        print(f"\n  {family}/clean:")
        for angle in ANGLES:
            img = get_family_image(family, angle)
            save_with_thumb(img, DEMO_DIR / f"{family}/clean/{angle}.jpg")
        print("    ✓ 5 unique angles")

    # Scenario images
    print("\n  Scenarios:")
    for sid, family in SCENARIO_FAMILIES.items():
        defect = SCENARIO_DEFECTS[sid]
        out_dir = DEMO_DIR / "scenarios" / sid
        for angle in ANGLES:
            img = get_family_image(family, angle)
            if defect and angle == "top":
                if defect == "lifted_pad":
                    from regenerate_pcb_defects import apply_solder_bridge
                    img = apply_solder_bridge(img)
                elif defect == "tombstone":
                    from regenerate_pcb_defects import apply_cold_solder
                    img = apply_cold_solder(img)
                else:
                    img = apply_defect(img, defect)
            save_with_thumb(img, out_dir / f"{angle}.jpg")
        print(f"    ✓ {sid} ({family}, defect={defect or 'clean'})")

    # Kiosk-specific defective
    print("\n  Kiosk defective:")
    # Scratched plate
    for angle in ANGLES:
        img = get_family_image("metal_plate", angle)
        if angle == "top":
            img = apply_defect(img, "scratch")
        save_with_thumb(img, DEMO_DIR / f"kiosk/839-041322-002/{angle}.jpg")
    print("    ✓ 839-041322-002 (scratch)")

    # Missing screw
    for angle in ANGLES:
        img = get_family_image("screw", angle)
        if angle == "top":
            img = apply_defect(img, "missing")
        save_with_thumb(img, DEMO_DIR / f"kiosk/715-098456-003/{angle}.jpg")
    print("    ✓ 715-098456-003 (missing)")

    # PCB defects
    for angle in ANGLES:
        img = get_family_image("pcb", angle)
        if angle == "top":
            img = apply_defect(img, "pcb_defects")
        save_with_thumb(img, DEMO_DIR / f"kiosk/444-027654-002/{angle}.jpg")
    print("    ✓ 444-027654-002 (PCB)")

    # RF Driver Board — solder bridge
    for angle in ANGLES:
        img = get_family_image("pcb", angle)
        if angle == "top":
            from regenerate_pcb_defects import apply_solder_bridge
            img = apply_solder_bridge(img)
        save_with_thumb(img, DEMO_DIR / f"kiosk/444-027654-003/{angle}.jpg")
    print("    ✓ 444-027654-003 (Solder Bridge)")

    # Power Distribution Board — cold solder joint
    for angle in ANGLES:
        img = get_family_image("pcb", angle)
        if angle == "top":
            from regenerate_pcb_defects import apply_cold_solder
            img = apply_cold_solder(img)
        save_with_thumb(img, DEMO_DIR / f"kiosk/444-027654-004/{angle}.jpg")
    print("    ✓ 444-027654-004 (Cold Solder Joint)")

    # Gas manifold with heat tint (REVIEW)
    for angle in ANGLES:
        img = get_family_image("weldment", angle)
        if angle == "top":
            img = apply_defect(img, "anomaly")
        save_with_thumb(img, DEMO_DIR / f"kiosk/622-073891-001/{angle}.jpg")
    print("    ✓ 622-073891-001 (heat tint)")

    # Lower Chamber Shield with surface deviation (REVIEW)
    for angle in ANGLES:
        img = get_family_image("metal_plate", angle)
        if angle == "top":
            img = apply_defect(img, "anomaly")
        save_with_thumb(img, DEMO_DIR / f"kiosk/839-055678-003/{angle}.jpg")
    print("\nDone!")


def apply_defect(img: Image.Image, defect_type: str) -> Image.Image:
    """Apply a specific defect to an image."""
    draw = ImageDraw.Draw(img)
    w, h = img.size

    if defect_type == "scratch":
        # Bright scratches across the circular part
        cx, cy = w // 2, h // 2
        for offset in [0, 25, 45]:
            y = cy - 40 + offset
            draw.line([(cx-150, y), (cx+150, y+random.randint(-10, 10))],
                      fill=(235, 237, 245), width=2)
            draw.line([(cx-150, y+2), (cx+150, y+random.randint(-10, 10)+2)],
                      fill=(90, 92, 96), width=1)

    elif defect_type == "dent":
        cx, cy = w // 2 + 30, h // 2 - 20
        r = 45
        # Darken circular area
        arr = np.array(img)
        Y, X = np.ogrid[:h, :w]
        dist = np.sqrt((X - cx)**2 + (Y - cy)**2)
        mask = dist < r
        arr[mask] = (arr[mask] * 0.65).astype(np.uint8)
        img = Image.fromarray(arr)
        draw = ImageDraw.Draw(img)
        draw.arc([(cx-r, cy-r), (cx+r, cy+r)], 200, 340, fill=(220, 222, 230), width=4)
        draw.arc([(cx-r, cy-r), (cx+r, cy+r)], 20, 160, fill=(80, 82, 86), width=3)

    elif defect_type == "missing":
        # Remove one screw — show empty hole at position 3 (390, 160)
        sx, sy = 390, 160
        draw.ellipse([(sx-16, sy-16), (sx+16, sy+16)], fill=(165, 167, 171))
        draw.ellipse([(sx-14, sy-14), (sx+14, sy+14)], fill=(40, 42, 46), outline=(75, 77, 81), width=2)
        for r in [5, 9, 12]:
            draw.arc([(sx-r, sy-r), (sx+r, sy+r)], 0, 360, fill=(55, 57, 61), width=1)

    elif defect_type == "contamination":
        cx, cy = w // 2 + 20, h // 2 - 10
        arr = np.array(img)
        for _ in range(3000):
            px = cx + int(random.gauss(0, 35))
            py = cy + int(random.gauss(0, 25))
            if 0 <= px < w and 0 <= py < h:
                arr[py, px] = [random.randint(20, 50), random.randint(15, 40), random.randint(10, 35)]
        img = Image.fromarray(arr)
        img = img.filter(ImageFilter.GaussianBlur(radius=0.5))

    elif defect_type == "anomaly":
        cx, cy = w // 2 + 15, h // 2
        arr = np.array(img).astype(np.float32)
        Y, X = np.ogrid[:h, :w]
        # Realistic heat tint — gradient from center, brownish-amber
        dist = ((X - cx) / 60.0)**2 + ((Y - cy) / 40.0)**2
        mask = dist < 1.0
        intensity = np.clip(1.0 - dist, 0, 1)
        # Subtle but visible: warm amber shift, not solid orange
        arr[mask, 0] = np.minimum(arr[mask, 0] + intensity[mask] * 30, 255)
        arr[mask, 1] = arr[mask, 1] * (1.0 - intensity[mask] * 0.18)
        arr[mask, 2] = arr[mask, 2] * (1.0 - intensity[mask] * 0.40)
        img = Image.fromarray(arr.astype(np.uint8))
        draw = ImageDraw.Draw(img)
        draw.ellipse([(cx-60, cy-40), (cx+60, cy+40)], outline=(175, 125, 60), width=1)

    elif defect_type == "pcb_defects":
        # Missing capacitor (empty pads — larger, clearly visible)
        cx, cy = 350, 200
        # Clear the area (show bare board where component should be)
        draw.rectangle([(cx-8, cy-6), (cx+20, cy+10)], fill=(25, 75, 38))
        # Exposed copper pads (bright gold, clearly empty)
        draw.rectangle([(cx-8, cy-4), (cx-1, cy+8)], fill=(210, 180, 60), outline=(170, 140, 40))
        draw.rectangle([(cx+13, cy-4), (cx+20, cy+8)], fill=(210, 180, 60), outline=(170, 140, 40))

        # Solder crack on IC (bright white jagged line on dark IC body)
        ix, iy = 380, 80
        # The IC is at (380, 80, 55, 55) in make_pcb_top
        crack_pts = [(ix, iy+25), (ix+8, iy+22), (ix+16, iy+28),
                     (ix+24, iy+23), (ix+32, iy+27), (ix+40, iy+24), (ix+50, iy+26)]
        draw.line(crack_pts, fill=(240, 240, 245), width=3)
        draw.line(crack_pts, fill=(255, 255, 255), width=1)
        # Shadow
        shadow_pts = [(px, py+2) for px, py in crack_pts]
        draw.line(shadow_pts, fill=(10, 10, 12), width=2)

    return img


if __name__ == "__main__":
    main()
