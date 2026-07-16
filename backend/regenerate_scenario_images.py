"""
Generate scenario-specific defective images with HIGHLY VISIBLE defects.
Each defect is large, high-contrast, and unmissable at any display size.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFont, ImageFilter
from pathlib import Path
import random

DEMO_DIR = Path("demo_data/images")
ANGLES = ["top", "north", "south", "east", "west"]
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)

SCENARIOS = {
    "scenario-01": {"family": "metal_plate", "defects": []},
    "scenario-02": {"family": "metal_plate", "defects": [("scratch", "top")]},
    "scenario-03": {"family": "metal_plate", "defects": [("dent", "top")]},
    "scenario-04": {"family": "metal_plate", "defects": [("missing_component", "top")]},
    "scenario-05": {"family": "weldment", "defects": [("contamination", "top")]},
    "scenario-06": {"family": "metal_plate", "defects": [("surface_anomaly", "top")]},
    "scenario-07": {"family": "metal_plate", "defects": [("surface_anomaly", "north")]},
    "scenario-08": {"family": "pcb", "defects": [("missing_component", "top"), ("crack", "top")]},
    "scenario-09": {"family": "weldment", "defects": [("contamination", "north")]},
    "scenario-10": {"family": "metal_plate", "defects": [("scratch", "north")]},
}


def draw_scratch(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """LARGE, bright scratch lines across the surface."""
    # Primary long scratch — spans most of the image
    y_base = h // 3 + idx * 60
    x1, y1 = w // 8, y_base
    x2, y2 = 7 * w // 8, y_base + random.randint(-20, 20)
    
    # Wide shadow underneath
    draw.line([(x1, y1 + 3), (x2, y2 + 3)], fill=(80, 80, 85), width=4)
    # Bright exposed metal (main scratch)
    draw.line([(x1, y1), (x2, y2)], fill=(240, 242, 250), width=3)
    # Highlight edge
    draw.line([(x1, y1 - 2), (x2, y2 - 2)], fill=(255, 255, 255), width=1)
    
    # Secondary scratch nearby
    y3 = y_base + 30
    x3 = w // 5
    x4 = 3 * w // 4
    draw.line([(x3, y3 + 2), (x4, y3 + random.randint(-10, 10) + 2)], fill=(85, 85, 90), width=3)
    draw.line([(x3, y3), (x4, y3 + random.randint(-10, 10))], fill=(230, 232, 240), width=2)

    # Third minor scratch
    y4 = y_base + 55
    draw.line([(w // 3, y4), (2 * w // 3, y4 + 5)], fill=(220, 222, 230), width=2)


def draw_dent(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """LARGE, obvious impact dent with clear shadow/highlight."""
    cx = w // 2 + idx * 50
    cy = h // 2
    r = 55  # Large radius

    # Dark shadow around the dent
    draw.ellipse([(cx - r - 5, cy - r - 5), (cx + r + 5, cy + r + 5)],
                 outline=(70, 72, 76), width=5)
    # Dent depression (much darker than surface)
    draw.ellipse([(cx - r, cy - r), (cx + r, cy + r)], fill=(120, 122, 126))
    # Deepest center
    draw.ellipse([(cx - r // 2, cy - r // 2), (cx + r // 2, cy + r // 2)], fill=(100, 102, 106))
    # Very center — darkest
    draw.ellipse([(cx - 12, cy - 12), (cx + 12, cy + 12)], fill=(85, 87, 91))
    # Bright rim (displaced metal)
    draw.arc([(cx - r, cy - r), (cx + r, cy + r)], start=200, end=340, fill=(230, 232, 240), width=4)
    # Radial stress cracks from impact
    for angle_deg in range(0, 360, 30):
        rad = np.radians(angle_deg)
        x1 = cx + int((r + 5) * np.cos(rad))
        y1 = cy + int((r + 5) * np.sin(rad))
        x2 = cx + int((r + 20) * np.cos(rad))
        y2 = cy + int((r + 20) * np.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(110, 112, 116), width=2)


def draw_contamination(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """LARGE, dark contamination splotch — unmissable."""
    cx = w // 2 + idx * 40
    cy = h // 2

    # Large irregular dark patch
    pts = []
    for i in range(12):
        angle = i * 30 + random.randint(-10, 10)
        r = random.randint(40, 70)
        pts.append((cx + int(r * np.cos(np.radians(angle))),
                    cy + int(r * np.sin(np.radians(angle)))))
    draw.polygon(pts, fill=(40, 35, 30))
    
    # Slightly lighter inner area (depth/texture)
    inner_pts = []
    for i in range(8):
        angle = i * 45 + random.randint(-15, 15)
        r = random.randint(20, 40)
        inner_pts.append((cx + int(r * np.cos(np.radians(angle))),
                          cy + int(r * np.sin(np.radians(angle)))))
    draw.polygon(inner_pts, fill=(55, 50, 45))

    # Scattered particles around
    for _ in range(40):
        px = cx + random.randint(-90, 90)
        py = cy + random.randint(-70, 70)
        size = random.randint(3, 10)
        draw.ellipse([(px, py), (px + size, py + size)], fill=(30 + random.randint(0, 30), 28, 25))
    
    # Stain ring
    draw.ellipse([(cx - 80, cy - 65), (cx + 80, cy + 65)], outline=(60, 55, 50), width=2)


def draw_missing_component(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """LARGE empty hole with prominent red annotation."""
    cx = w // 3 + idx * 80
    cy = h // 3

    # Large empty socket hole
    draw.ellipse([(cx - 25, cy - 25), (cx + 25, cy + 25)], fill=(25, 27, 31), outline=(80, 82, 86), width=3)
    # Thread marks
    for r in [8, 15, 22]:
        draw.arc([(cx - r, cy - r), (cx + r, cy + r)], start=0, end=360, fill=(50, 52, 56), width=1)

    # BIG red circle annotation
    draw.ellipse([(cx - 40, cy - 40), (cx + 40, cy + 40)], outline=(255, 40, 40), width=4)
    # Red X through it
    draw.line([(cx - 28, cy - 28), (cx + 28, cy + 28)], fill=(255, 40, 40), width=3)
    draw.line([(cx - 28, cy + 28), (cx + 28, cy - 28)], fill=(255, 40, 40), width=3)
    
    # Arrow and label
    draw.line([(cx + 40, cy - 40), (cx + 90, cy - 80)], fill=(255, 40, 40), width=3)
    # Label background
    draw.rectangle([(cx + 70, cy - 100), (cx + 200, cy - 70)], fill=(255, 40, 40))
    draw.text((cx + 78, cy - 95), "MISSING", fill=(255, 255, 255))

    # Ghost outline showing what should be there
    draw.ellipse([(cx - 18, cy - 18), (cx + 18, cy + 18)], outline=(255, 40, 40), width=2)


def draw_crack(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """LARGE, clearly visible crack with branching."""
    x = w // 4 + idx * 100
    y = h // 2

    # Main crack — long jagged path
    points = [(x, y)]
    cur_x, cur_y = x, y
    for _ in range(25):
        cur_x += random.randint(8, 18)
        cur_y += random.randint(-8, 8)
        points.append((cur_x, cur_y))

    # Dark crack line (wide)
    draw.line(points, fill=(30, 30, 35), width=4)
    # Inner darker line
    draw.line(points, fill=(15, 15, 20), width=2)
    # White stress edge on one side
    offset_pts = [(px, py - 3) for px, py in points]
    draw.line(offset_pts, fill=(220, 222, 230), width=1)

    # Branch from 1/3 point
    branch_start = points[len(points) // 3]
    bx, by = branch_start
    branch_pts = [(bx, by)]
    for _ in range(12):
        bx += random.randint(4, 12)
        by += random.randint(3, 10)
        branch_pts.append((bx, by))
    draw.line(branch_pts, fill=(30, 30, 35), width=3)
    draw.line(branch_pts, fill=(15, 15, 20), width=1)

    # Branch from 2/3 point going up
    branch_start2 = points[2 * len(points) // 3]
    bx2, by2 = branch_start2
    branch_pts2 = [(bx2, by2)]
    for _ in range(8):
        bx2 += random.randint(3, 10)
        by2 -= random.randint(3, 10)
        branch_pts2.append((bx2, by2))
    draw.line(branch_pts2, fill=(35, 35, 40), width=2)


def draw_surface_anomaly(draw: ImageDraw.Draw, w: int, h: int, idx: int = 0):
    """Visible but subtle surface irregularity — discoloration patch."""
    cx = w // 2 + idx * 30
    cy = h // 2

    # Visible discoloration — brownish/yellowish tint
    for dx in range(-50, 50):
        for dy in range(-35, 35):
            dist = (dx * dx + dy * dy)
            if dist < 2500:
                intensity = max(0, 1.0 - dist / 2500)
                if random.random() < 0.7:
                    base_r = 175 + int(30 * intensity)
                    base_g = 160 + int(10 * intensity)
                    base_b = 130
                    draw.point((cx + dx, cy + dy), fill=(base_r, base_g, base_b))

    # Outline ring to make it more visible
    draw.ellipse([(cx - 50, cy - 35), (cx + 50, cy + 35)], outline=(180, 150, 100), width=2)
    # Question mark annotation (ambiguous defect)
    draw.text((cx + 55, cy - 15), "?", fill=(200, 150, 50))


DEFECT_DRAWERS = {
    "scratch": draw_scratch,
    "dent": draw_dent,
    "contamination": draw_contamination,
    "missing_component": draw_missing_component,
    "crack": draw_crack,
    "surface_anomaly": draw_surface_anomaly,
}


def load_clean_base(family: str, angle: str) -> Image.Image:
    """Load the clean base image."""
    path = DEMO_DIR / family / "clean" / f"{angle}.jpg"
    if path.exists():
        return Image.open(path).copy()
    return Image.new("RGB", IMG_SIZE, (170, 172, 176))


def generate_scenario_images(scenario_id: str, config: dict):
    """Generate images for one scenario."""
    family = config["family"]
    defects = config["defects"]
    out_dir = DEMO_DIR / "scenarios" / scenario_id
    out_dir.mkdir(parents=True, exist_ok=True)

    for angle in ANGLES:
        img = load_clean_base(family, angle)
        draw = ImageDraw.Draw(img)
        w, h = img.size

        # Draw ONLY the defects for this angle
        defect_idx = 0
        for defect_type, defect_angle in defects:
            if defect_angle == angle:
                drawer = DEFECT_DRAWERS.get(defect_type)
                if drawer:
                    drawer(draw, w, h, idx=defect_idx)
                    defect_idx += 1

        img.save(out_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(out_dir / f"{angle}_thumb.jpg", quality=85)

    print(f"  ✓ {scenario_id}: {[d[0] for d in defects] or ['CLEAN']}")


def main():
    for scenario_id, config in SCENARIOS.items():
        generate_scenario_images(scenario_id, config)
    print("\nDone!")


if __name__ == "__main__":
    main()
