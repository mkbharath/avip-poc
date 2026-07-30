"""
Generate images for 6 Lam-specific cosmetic defect scenarios (13-18).
Each defect drawn on the appropriate base image type.
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


def save_with_thumb(img: Image.Image, path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(path), quality=92)
    thumb = img.copy()
    thumb.thumbnail(THUMB_SIZE)
    thumb.save(str(path.parent / f"{path.stem}_thumb{path.suffix}"), quality=85)


def get_chamber_lid_base():
    """Load existing chamber lid base or generate."""
    p = DEMO_DIR / "metal_plate/clean/top.jpg"
    if p.exists():
        return Image.open(p).copy()
    # Fallback: gray circle
    img = Image.new("RGB", IMG_SIZE, (42, 42, 46))
    draw = ImageDraw.Draw(img)
    cx, cy = 320, 240
    for r in range(200, 0, -1):
        shade = 165 + int(15 * math.sin(r * 0.05))
        draw.ellipse([(cx-r, cy-r), (cx+r, cy+r)], outline=(shade, shade, shade+3))
    return img


def get_screw_base():
    """Load existing screw assembly base."""
    p = DEMO_DIR / "screw/clean/top.jpg"
    if p.exists():
        return Image.open(p).copy()
    return Image.new("RGB", IMG_SIZE, (165, 167, 171))


def apply_porosity(img):
    """Dark pits/voids on machined surface — subsurface material defect."""
    draw = ImageDraw.Draw(img)
    random.seed(55)
    cx, cy = 320, 240
    # Cluster of dark pits in the sealing area
    for _ in range(12):
        px = cx + random.randint(-60, 60)
        py = cy + random.randint(-40, 40)
        size = random.randint(4, 12)
        # Dark void
        draw.ellipse([(px-size, py-size), (px+size, py+size)], fill=(40, 42, 46))
        # Slightly lighter ring (exposed subsurface)
        draw.ellipse([(px-size-2, py-size-2), (px+size+2, py+size+2)],
                     outline=(90, 92, 96), width=1)
    # A few larger voids
    for _ in range(3):
        px = cx + random.randint(-40, 40)
        py = cy + random.randint(-30, 30)
        size = random.randint(8, 16)
        draw.ellipse([(px-size, py-size), (px+size, py+size)], fill=(30, 32, 36))
        draw.ellipse([(px-size+2, py-size+2), (px+size-2, py+size-2)], fill=(50, 52, 56))
    return img


def apply_tool_marks(img):
    """Visible machining lines/tool path marks across the surface."""
    draw = ImageDraw.Draw(img)
    random.seed(66)
    # Parallel diagonal lines (CNC tool path)
    for i in range(15):
        y_base = 180 + i * 8
        x1 = 150 + random.randint(-10, 10)
        x2 = 490 + random.randint(-10, 10)
        # Bright line (raised edge of tool path)
        draw.line([(x1, y_base), (x2, y_base + random.randint(-3, 3))],
                  fill=(200, 202, 208), width=2)
        # Shadow line below
        draw.line([(x1, y_base+2), (x2, y_base+2 + random.randint(-3, 3))],
                  fill=(130, 132, 136), width=1)
    # Deeper gouge marks (3 prominent ones)
    for i in range(3):
        y = 200 + i * 25
        draw.line([(180, y), (460, y + random.randint(-5, 5))],
                  fill=(220, 222, 230), width=3)
        draw.line([(180, y+3), (460, y+3 + random.randint(-5, 5))],
                  fill=(110, 112, 116), width=2)
    return img


def apply_coating_stain(img):
    """Dark stain marks on anodized/coated surface."""
    arr = np.array(img).astype(np.float32)
    w, h = IMG_SIZE
    random.seed(77)
    # Multiple irregular stain patches
    stains = [(280, 220, 50, 40), (360, 260, 35, 30), (310, 300, 45, 25)]
    for sx, sy, rx, ry in stains:
        Y, X = np.ogrid[:h, :w]
        dist = ((X - sx) / rx)**2 + ((Y - sy) / ry)**2
        mask = dist < 1.0
        intensity = np.clip(1.0 - dist, 0, 1)
        # Darken + brownish tint (stain appearance)
        arr[mask, 0] = arr[mask, 0] * (1.0 - intensity[mask] * 0.3)
        arr[mask, 1] = arr[mask, 1] * (1.0 - intensity[mask] * 0.35)
        arr[mask, 2] = arr[mask, 2] * (1.0 - intensity[mask] * 0.45)
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)
    # Stain boundary outlines
    for sx, sy, rx, ry in stains:
        draw.ellipse([(sx-rx, sy-ry), (sx+rx, sy+ry)], outline=(100, 90, 70), width=1)
    return img


def apply_label_mismatch(img):
    """Show part with two conflicting serial numbers — engraving vs label."""
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE
    # Engraved serial on part surface (upper area)
    draw.rectangle([(180, 140), (460, 190)], fill=(155, 157, 161), outline=(130, 132, 136))
    draw.text((195, 148), "S/N: 1034325-0326-0009", fill=(80, 82, 86))
    draw.text((195, 168), "LAM P/N: 839-055678-005  REV A", fill=(90, 92, 96))
    # Attached label (lower area) — DIFFERENT serial
    draw.rectangle([(180, 280), (460, 360)], fill=(245, 245, 248), outline=(180, 182, 186))
    draw.text((195, 288), "SHIP TO: Lam Research", fill=(20, 20, 25))
    draw.text((195, 305), "Lam P/N: 839-055678-005", fill=(20, 20, 25))
    draw.text((195, 322), "S/N: 1034325-0879-0012", fill=(200, 30, 30))
    draw.text((380, 322), "MISMATCH", fill=(200, 30, 30))
    draw.text((195, 340), "REV: A   CoO: USA", fill=(60, 60, 65))
    # Red highlight on mismatching serial
    draw.rectangle([(188, 145), (410, 175)], outline=(220, 40, 40), width=2)
    draw.rectangle([(188, 318), (370, 338)], outline=(220, 40, 40), width=2)
    # Arrow connecting the two
    draw.line([(320, 190), (320, 280)], fill=(220, 40, 40), width=2)
    draw.polygon([(315, 275), (325, 275), (320, 282)], fill=(220, 40, 40))
    return img


def apply_burr(img):
    """Machining burr — raised material on edge of a hole or thread."""
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE
    # Draw a bolt hole with burr
    cx, cy = 320, 240
    # Hole
    draw.ellipse([(cx-25, cy-25), (cx+25, cy+25)], fill=(50, 52, 56), outline=(85, 87, 91), width=2)
    # Thread marks inside
    for r in [8, 14, 20]:
        draw.arc([(cx-r, cy-r), (cx+r, cy+r)], 0, 360, fill=(60, 62, 66), width=1)
    # BURR — irregular raised material on edge (bright, jagged)
    burr_angles = range(30, 120, 5)
    for angle in burr_angles:
        rad = math.radians(angle)
        r_base = 25
        r_burr = r_base + random.randint(5, 15)
        x1 = cx + int(r_base * math.cos(rad))
        y1 = cy + int(r_base * math.sin(rad))
        x2 = cx + int(r_burr * math.cos(rad))
        y2 = cy + int(r_burr * math.sin(rad))
        shade = 200 + random.randint(-10, 20)
        draw.line([(x1, y1), (x2, y2)], fill=(shade, shade, shade+5), width=2)
    # Bright highlight on burr tips
    for angle in range(40, 110, 10):
        rad = math.radians(angle)
        r_tip = 25 + random.randint(8, 14)
        tx = cx + int(r_tip * math.cos(rad))
        ty = cy + int(r_tip * math.sin(rad))
        draw.ellipse([(tx-3, ty-3), (tx+3, ty+3)], fill=(235, 237, 245))
    return img


def apply_paint_peel(img):
    """Paint/coating peeling off — exposed bare substrate visible."""
    draw = ImageDraw.Draw(img)
    arr = np.array(img).astype(np.float32)
    w, h = IMG_SIZE
    # Peeled area near a mounting hole (upper right)
    cx, cy = 380, 200
    # Irregular peel shape
    random.seed(88)
    pts = []
    for a in range(0, 360, 15):
        r = 30 + random.randint(-8, 12)
        rad = math.radians(a)
        pts.append((cx + int(r * math.cos(rad)), cy + int(r * math.sin(rad))))
    # Bare substrate (brighter aluminum underneath)
    img_pil = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img_pil)
    draw.polygon(pts, fill=(195, 197, 201))
    # Texture on exposed area (raw machining marks)
    for i in range(8):
        y = cy - 20 + i * 5
        draw.line([(cx-25, y), (cx+25, y)], fill=(185, 187, 191), width=1)
    # Peeling edge (darker shadow where paint curls)
    draw.line(pts + [pts[0]], fill=(70, 72, 76), width=3)
    # Curled paint fragments
    for i in range(0, len(pts), 4):
        px, py = pts[i]
        draw.arc([(px-5, py-5), (px+5, py+5)], 0, 180, fill=(60, 62, 66), width=2)
    return img_pil


def main():
    print("Generating Lam-specific defect images...")

    scenarios = {
        "scenario-13": ("metal_plate", apply_porosity, "Porosity"),
        "scenario-14": ("metal_plate", apply_tool_marks, "Tool Marks"),
        "scenario-15": ("metal_plate", apply_coating_stain, "Coating Stain"),
        "scenario-16": ("metal_plate", apply_label_mismatch, "Label Mismatch"),
        "scenario-17": ("screw", apply_burr, "Burr"),
        "scenario-18": ("metal_plate", apply_paint_peel, "Paint Peel"),
    }

    kiosk_parts = {
        "839-041322-003": ("metal_plate", apply_porosity),
        "839-041322-004": ("metal_plate", apply_tool_marks),
        "839-055678-004": ("metal_plate", apply_coating_stain),
        "839-055678-005": ("metal_plate", apply_label_mismatch),
        "715-098456-008": ("screw", apply_burr),
        "839-055678-006": ("metal_plate", apply_paint_peel),
    }

    # Generate scenario images
    for sid, (family, defect_fn, label) in scenarios.items():
        out_dir = DEMO_DIR / "scenarios" / sid
        base_fn = get_chamber_lid_base if family == "metal_plate" else get_screw_base
        for angle in ANGLES:
            img = base_fn()
            if angle == "top":
                img = defect_fn(img)
            from PIL import ImageEnhance
            if angle == "north":
                img = ImageEnhance.Brightness(img).enhance(1.08)
            elif angle == "south":
                img = ImageEnhance.Brightness(img).enhance(0.92)
            elif angle == "east":
                img = ImageEnhance.Contrast(img).enhance(1.1)
            elif angle == "west":
                img = ImageEnhance.Contrast(img).enhance(0.9)
            save_with_thumb(img, out_dir / f"{angle}.jpg")
        print(f"  ✓ {sid} ({label})")

    # Generate kiosk images
    print("\n  Kiosk:")
    for part_num, (family, defect_fn) in kiosk_parts.items():
        base_fn = get_chamber_lid_base if family == "metal_plate" else get_screw_base
        for angle in ANGLES:
            img = base_fn()
            if angle == "top":
                img = defect_fn(img)
            from PIL import ImageEnhance
            if angle == "north":
                img = ImageEnhance.Brightness(img).enhance(1.08)
            elif angle == "south":
                img = ImageEnhance.Brightness(img).enhance(0.92)
            elif angle == "east":
                img = ImageEnhance.Contrast(img).enhance(1.1)
            elif angle == "west":
                img = ImageEnhance.Contrast(img).enhance(0.9)
            save_with_thumb(img, DEMO_DIR / f"kiosk/{part_num}/{angle}.jpg")
        print(f"  ✓ kiosk/{part_num}")

    print("\nDone!")


if __name__ == "__main__":
    main()
