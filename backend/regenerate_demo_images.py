"""
Regenerate demo capture images with distinct, realistic-looking views per camera angle.
Each angle shows a different perspective of a machined aluminum part.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from pathlib import Path
import random

DEMO_DIR = Path("demo_data/images")
FAMILIES = ["metal_plate", "screw", "pcb", "weldment", "cable"]
ANGLES = ["top", "north", "south", "east", "west"]
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)


def make_metal_plate(angle: str, variant: str = "clean") -> Image.Image:
    """Generate a realistic-looking machined aluminum plate from different angles."""
    img = Image.new("RGB", IMG_SIZE)
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE

    # Base: brushed aluminum gradient
    for y in range(h):
        base_gray = 175 + int(20 * np.sin(y * 0.02))
        noise = random.randint(-5, 5)
        gray = max(0, min(255, base_gray + noise))
        # Slight blue tint for aluminum
        r, g, b = gray - 3, gray, gray + 4
        draw.line([(0, y), (w, y)], fill=(r, g, b))

    # Add brushed texture lines
    for _ in range(200):
        y_pos = random.randint(0, h - 1)
        x_start = random.randint(0, w // 2)
        length = random.randint(40, 200)
        alpha = random.randint(160, 190)
        draw.line([(x_start, y_pos), (x_start + length, y_pos)], fill=(alpha, alpha, alpha + 2), width=1)

    if angle == "top":
        # Top view: circular mounting holes pattern, center pocket
        # Center rectangular pocket
        pocket = (w // 4, h // 4, 3 * w // 4, 3 * h // 4)
        draw.rectangle(pocket, outline=(130, 132, 136), width=2)
        # Inner pocket floor (slightly darker)
        draw.rectangle((pocket[0] + 8, pocket[1] + 8, pocket[2] - 8, pocket[3] - 8), fill=(155, 157, 161))
        # Mounting holes (4 corners)
        hole_positions = [(w // 6, h // 6), (5 * w // 6, h // 6), (w // 6, 5 * h // 6), (5 * w // 6, 5 * h // 6)]
        for hx, hy in hole_positions:
            draw.ellipse([(hx - 12, hy - 12), (hx + 12, hy + 12)], fill=(60, 62, 66), outline=(90, 92, 96))
            draw.ellipse([(hx - 5, hy - 5), (hx + 5, hy + 5)], fill=(40, 42, 46))
        # Center alignment mark
        draw.line([(w // 2 - 20, h // 2), (w // 2 + 20, h // 2)], fill=(100, 102, 106), width=1)
        draw.line([(w // 2, h // 2 - 20), (w // 2, h // 2 + 20)], fill=(100, 102, 106), width=1)
        # Part number engraving
        draw.text((w - 180, h - 40), "839-041322-001", fill=(130, 130, 134))
        draw.text((w - 180, h - 25), "REV C  AL6061", fill=(140, 140, 144))

    elif angle == "north":
        # North view: side profile showing edge thickness, chamfer
        # Main plate body (rectangle from side)
        plate_top = h // 3
        plate_bot = 2 * h // 3
        draw.rectangle([(60, plate_top), (w - 60, plate_bot)], fill=(165, 167, 171), outline=(130, 132, 136))
        # Top chamfer
        for i in range(8):
            y_off = plate_top + i
            shade = 180 + i * 2
            draw.line([(60, y_off), (w - 60, y_off)], fill=(shade, shade, shade + 2))
        # Bottom chamfer
        for i in range(8):
            y_off = plate_bot - i
            shade = 180 + i * 2
            draw.line([(60, y_off), (w - 60, y_off)], fill=(shade, shade, shade + 2))
        # Surface finish lines (horizontal machining marks)
        for y in range(plate_top + 10, plate_bot - 10, 3):
            alpha = random.randint(155, 170)
            draw.line([(70, y), (w - 70, y)], fill=(alpha, alpha, alpha + 2), width=1)
        # Pocket opening visible from this side
        pocket_left = w // 4
        pocket_right = 3 * w // 4
        pocket_depth = 15
        draw.rectangle([(pocket_left, plate_top), (pocket_right, plate_top + pocket_depth)], fill=(145, 147, 151))
        # Dimension line
        draw.line([(80, plate_bot + 30), (w - 80, plate_bot + 30)], fill=(100, 100, 200), width=1)
        draw.text((w // 2 - 20, plate_bot + 35), "254.0mm", fill=(100, 100, 200))

    elif angle == "south":
        # South view: opposite side, showing connector/slot features
        plate_top = h // 3
        plate_bot = 2 * h // 3
        draw.rectangle([(60, plate_top), (w - 60, plate_bot)], fill=(168, 170, 174), outline=(130, 132, 136))
        # Slot features (keyway slots on bottom edge)
        slot_width = 30
        for sx in [w // 4, w // 2, 3 * w // 4]:
            draw.rectangle([(sx - slot_width // 2, plate_bot - 20), (sx + slot_width // 2, plate_bot)], fill=(80, 82, 86))
        # Mounting tab
        tab_w = 40
        draw.rectangle([(w // 2 - tab_w, plate_bot), (w // 2 + tab_w, plate_bot + 25)], fill=(160, 162, 166), outline=(130, 132, 136))
        draw.ellipse([(w // 2 - 8, plate_bot + 5), (w // 2 + 8, plate_bot + 21)], fill=(60, 62, 66))
        # Surface machining marks
        for y in range(plate_top + 5, plate_bot - 5, 4):
            alpha = random.randint(158, 172)
            draw.line([(70, y), (w - 70, y)], fill=(alpha, alpha, alpha), width=1)
        # Edge break visible
        draw.line([(60, plate_top), (60, plate_bot)], fill=(140, 142, 146), width=3)
        draw.line([(w - 60, plate_top), (w - 60, plate_bot)], fill=(140, 142, 146), width=3)

    elif angle == "east":
        # East view: narrow side, showing thickness and bolt pattern
        plate_left = w // 3
        plate_right = 2 * w // 3
        draw.rectangle([(plate_left, 40), (plate_right, h - 40)], fill=(162, 164, 168), outline=(128, 130, 134))
        # Bolt holes visible from edge
        for by in [h // 5, 2 * h // 5, 3 * h // 5, 4 * h // 5]:
            draw.ellipse([(w // 2 - 8, by - 8), (w // 2 + 8, by + 8)], fill=(55, 57, 61), outline=(90, 92, 96))
        # Chamfer lines on edges
        for i in range(5):
            shade = 175 + i * 3
            draw.line([(plate_left + i, 40), (plate_left + i, h - 40)], fill=(shade, shade, shade))
            draw.line([(plate_right - i, 40), (plate_right - i, h - 40)], fill=(shade, shade, shade))
        # Thickness dimension
        draw.line([(plate_left - 25, 60), (plate_left - 25, h - 60)], fill=(100, 100, 200), width=1)
        draw.text((plate_left - 55, h // 2 - 5), "12.7", fill=(100, 100, 200))
        # Surface texture from edge
        for x in range(plate_left + 5, plate_right - 5, 2):
            alpha = random.randint(155, 168)
            draw.line([(x, 50), (x, h - 50)], fill=(alpha, alpha, alpha), width=1)

    elif angle == "west":
        # West view: opposite narrow side, showing label area and QC stamp
        plate_left = w // 3
        plate_right = 2 * w // 3
        draw.rectangle([(plate_left, 40), (plate_right, h - 40)], fill=(165, 167, 171), outline=(128, 130, 134))
        # Label/etching area
        label_area = (plate_left + 20, h // 3, plate_right - 20, h // 3 + 60)
        draw.rectangle(label_area, fill=(155, 157, 161), outline=(140, 142, 146))
        draw.text((label_area[0] + 10, label_area[1] + 8), "P/N: 839-041322", fill=(110, 112, 116))
        draw.text((label_area[0] + 10, label_area[1] + 25), "REV: C", fill=(110, 112, 116))
        draw.text((label_area[0] + 10, label_area[1] + 42), "MAT: AL6061-T6", fill=(110, 112, 116))
        # QC stamp circle
        qc_center = (w // 2, 2 * h // 3 + 20)
        draw.ellipse([(qc_center[0] - 25, qc_center[1] - 25), (qc_center[0] + 25, qc_center[1] + 25)], outline=(80, 140, 80), width=2)
        draw.text((qc_center[0] - 12, qc_center[1] - 8), "QC", fill=(80, 140, 80))
        # Vertical machining marks
        for x in range(plate_left + 5, plate_right - 5, 3):
            alpha = random.randint(158, 170)
            draw.line([(x, 50), (x, h - 50)], fill=(alpha, alpha, alpha), width=1)

    return img


def make_generic(angle: str, family: str) -> Image.Image:
    """Generate a generic placeholder for other part families."""
    img = Image.new("RGB", IMG_SIZE, (170, 172, 176))
    draw = ImageDraw.Draw(img)
    w, h = IMG_SIZE

    # Add some texture
    for _ in range(500):
        x, y = random.randint(0, w - 1), random.randint(0, h - 1)
        shade = random.randint(160, 185)
        draw.point((x, y), fill=(shade, shade, shade))

    # Central shape varies by angle
    cx, cy = w // 2, h // 2
    if angle == "top":
        draw.rectangle([(cx - 100, cy - 80), (cx + 100, cy + 80)], outline=(120, 122, 126), width=2)
    elif angle in ("north", "south"):
        draw.rectangle([(80, cy - 30), (w - 80, cy + 30)], outline=(120, 122, 126), width=2)
    else:
        draw.rectangle([(cx - 40, 60), (cx + 40, h - 60)], outline=(120, 122, 126), width=2)

    # Label
    draw.text((20, h - 30), f"{family}/{angle}", fill=(100, 102, 106))

    return img


def main():
    for family in FAMILIES:
        for variant in ["clean"]:
            out_dir = DEMO_DIR / family / variant
            out_dir.mkdir(parents=True, exist_ok=True)

            for angle in ANGLES:
                if family == "metal_plate":
                    img = make_metal_plate(angle, variant)
                else:
                    img = make_generic(angle, family)

                # Save full size
                img.save(out_dir / f"{angle}.jpg", quality=92)
                # Save thumbnail
                thumb = img.copy()
                thumb.thumbnail(THUMB_SIZE)
                thumb.save(out_dir / f"{angle}_thumb.jpg", quality=85)

                print(f"  ✓ {family}/{variant}/{angle}.jpg")

    print("\nDone! All demo images regenerated.")


if __name__ == "__main__":
    main()
