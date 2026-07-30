"""
Generate XAI Heatmap and Golden Diff overlay images for each scenario.
These are semi-transparent PNG overlays shown on top of the inspection image.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter
from pathlib import Path
import math

DEMO_DIR = Path("demo_data/images")
IMG_SIZE = (640, 480)

# Defect centers per scenario (matching where defects are drawn)
SCENARIO_DEFECTS = {
    "scenario-01": None,  # PASS — no overlays
    "scenario-02": {"cx": 320, "cy": 240, "rx": 150, "ry": 30},   # scratch
    "scenario-03": {"cx": 400, "cy": 180, "rx": 50, "ry": 50},    # dent
    "scenario-04": {"cx": 390, "cy": 160, "rx": 30, "ry": 30},    # missing
    "scenario-05": {"cx": 340, "cy": 230, "rx": 50, "ry": 40},    # contamination
    "scenario-06": {"cx": 280, "cy": 290, "rx": 40, "ry": 30},    # unknown anomaly (lower-left)
    "scenario-07": {"cx": 320, "cy": 240, "rx": 110, "ry": 110},    # golden deviation (ring pattern)
    "scenario-08": [
        {"cx": 353, "cy": 203, "rx": 25, "ry": 18},   # missing cap C14
        {"cx": 407, "cy": 105, "rx": 35, "ry": 25},   # crack on U7
    ],
    "scenario-09": {"cx": 335, "cy": 230, "rx": 50, "ry": 35},    # anomaly
    "scenario-10": {"cx": 320, "cy": 240, "rx": 150, "ry": 30},   # scratch
    "scenario-11": {"cx": 420, "cy": 149, "rx": 40, "ry": 18},    # solder bridge on IC pins
    "scenario-12": {"cx": 392, "cy": 240, "rx": 25, "ry": 20},    # cold solder joint (right pad)
    "scenario-13": {"cx": 320, "cy": 240, "rx": 70, "ry": 50},    # porosity (center cluster)
    "scenario-14": {"cx": 320, "cy": 230, "rx": 150, "ry": 50},   # tool marks (wide horizontal)
    "scenario-15": {"cx": 310, "cy": 250, "rx": 80, "ry": 70},    # coating stain (multiple patches)
    "scenario-16": {"cx": 320, "cy": 240, "rx": 150, "ry": 110},  # label mismatch (full area)
    "scenario-17": {"cx": 320, "cy": 240, "rx": 40, "ry": 40},    # burr (on hole edge)
    "scenario-18": {"cx": 380, "cy": 200, "rx": 40, "ry": 40},    # paint peel (upper right)
}

# Kiosk defects
KIOSK_DEFECTS = {
    "839-041322-002": {"cx": 320, "cy": 240, "rx": 150, "ry": 30},
    "715-098456-003": {"cx": 390, "cy": 160, "rx": 30, "ry": 30},
    "444-027654-002": [
        {"cx": 353, "cy": 203, "rx": 25, "ry": 18},   # missing cap
        {"cx": 407, "cy": 105, "rx": 35, "ry": 25},   # crack
    ],
    "622-073891-001": {"cx": 335, "cy": 240, "rx": 65, "ry": 45},   # heat tint near weld
    "839-055678-003": {"cx": 335, "cy": 240, "rx": 65, "ry": 45},   # surface deviation
    "444-027654-003": {"cx": 420, "cy": 149, "rx": 40, "ry": 18},
    "444-027654-004": {"cx": 392, "cy": 240, "rx": 25, "ry": 20},
    "839-041322-003": {"cx": 320, "cy": 240, "rx": 70, "ry": 50},
    "839-041322-004": {"cx": 320, "cy": 230, "rx": 150, "ry": 50},
    "839-055678-004": {"cx": 310, "cy": 250, "rx": 80, "ry": 70},
    "839-055678-005": {"cx": 320, "cy": 240, "rx": 150, "ry": 110},
    "715-098456-008": {"cx": 320, "cy": 240, "rx": 40, "ry": 40},
    "839-055678-006": {"cx": 380, "cy": 200, "rx": 40, "ry": 40},
}


def generate_heatmap(defect: dict, filename: Path):
    """Generate XAI heatmap — red/yellow gradient. Supports single defect or list."""
    w, h = IMG_SIZE
    arr = np.zeros((h, w, 4), dtype=np.float32)

    # Support both single defect dict and list of defects
    defects = defect if isinstance(defect, list) else [defect]

    for d in defects:
        cx, cy = d["cx"], d["cy"]
        rx, ry = d["rx"], d["ry"]
        Y, X = np.ogrid[:h, :w]
        dist = ((X - cx) / (rx * 1.5)) ** 2 + ((Y - cy) / (ry * 1.5)) ** 2
        intensity = np.clip(1.0 - dist, 0, 1) ** 1.5
        # Accumulate
        for y in range(h):
            for x in range(w):
                val = float(intensity[y, x])
                if val > 0.01:
                    if val > 0.8:
                        r, g, b = 255, int(255 * (val - 0.8) / 0.2), 50
                    elif val > 0.4:
                        r, g, b = int(255 * (val - 0.4) / 0.4), 0, 0
                    else:
                        r, g, b = int(180 * val / 0.4), 0, 0
                    alpha = val * 160
                    # Take max intensity for overlapping regions
                    if alpha > arr[y, x, 3]:
                        arr[y, x] = [r, g, b, alpha]

    img = Image.fromarray(arr.astype(np.uint8), "RGBA")
    img = img.filter(ImageFilter.GaussianBlur(radius=3))
    filename.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(filename), "PNG")


def generate_golden_diff(defect: dict, filename: Path):
    """Generate golden comparison diff. Supports single defect or list."""
    w, h = IMG_SIZE
    arr = np.zeros((h, w, 4), dtype=np.uint8)

    # Light green tint everywhere (part matches golden reference)
    arr[:, :, 1] = 40
    arr[:, :, 3] = 25

    # Support multiple defects
    defects = defect if isinstance(defect, list) else [defect]

    for d in defects:
        cx, cy = d["cx"], d["cy"]
        rx, ry = d["rx"], d["ry"]
        Y, X = np.ogrid[:h, :w]
        dist = ((X - cx) / (rx * 1.2)) ** 2 + ((Y - cy) / (ry * 1.2)) ** 2
        deviation_mask = dist < 1.0
        arr[deviation_mask, 0] = 220
        arr[deviation_mask, 1] = 40
        arr[deviation_mask, 2] = 80
        deviation_strength = np.clip(1.0 - dist, 0, 1)
        arr[:, :, 3] = np.where(deviation_mask, np.maximum(arr[:, :, 3], (deviation_strength * 140).astype(np.uint8)[:, :]), arr[:, :, 3])

    img = Image.fromarray(arr, "RGBA")
    img = img.filter(ImageFilter.GaussianBlur(radius=4))

    filename.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(filename), "PNG")


def main():
    print("Generating overlay images...")

    # Scenario overlays
    for sid, defect in SCENARIO_DEFECTS.items():
        if defect is None:
            continue
        out_dir = DEMO_DIR / "scenarios" / sid
        generate_heatmap(defect, out_dir / "heatmap.png")
        generate_golden_diff(defect, out_dir / "golden_diff.png")
        print(f"  ✓ {sid}")

    # Kiosk overlays
    for part_num, defect in KIOSK_DEFECTS.items():
        out_dir = DEMO_DIR / "kiosk" / part_num
        generate_heatmap(defect, out_dir / "heatmap.png")
        generate_golden_diff(defect, out_dir / "golden_diff.png")
        print(f"  ✓ kiosk/{part_num}")

    print("\nDone!")


if __name__ == "__main__":
    main()
