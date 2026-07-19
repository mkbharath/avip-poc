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
    "scenario-03": {"cx": 350, "cy": 220, "rx": 50, "ry": 50},    # dent
    "scenario-04": {"cx": 390, "cy": 160, "rx": 30, "ry": 30},    # missing
    "scenario-05": {"cx": 340, "cy": 230, "rx": 50, "ry": 40},    # contamination
    "scenario-06": {"cx": 335, "cy": 240, "rx": 50, "ry": 35},    # anomaly
    "scenario-07": {"cx": 335, "cy": 240, "rx": 50, "ry": 35},    # anomaly
    "scenario-08": {"cx": 370, "cy": 160, "rx": 60, "ry": 50},    # pcb multi
    "scenario-09": {"cx": 335, "cy": 230, "rx": 50, "ry": 35},    # anomaly
    "scenario-10": {"cx": 320, "cy": 240, "rx": 150, "ry": 30},   # scratch
    "scenario-11": {"cx": 320, "cy": 323, "rx": 30, "ry": 25},    # lifted pad
    "scenario-12": {"cx": 353, "cy": 182, "rx": 20, "ry": 20},    # tombstone
}

# Kiosk defects
KIOSK_DEFECTS = {
    "839-041322-002": {"cx": 320, "cy": 240, "rx": 150, "ry": 30},
    "715-098456-003": {"cx": 390, "cy": 160, "rx": 30, "ry": 30},
    "444-027654-002": {"cx": 370, "cy": 160, "rx": 60, "ry": 50},
    "444-027654-003": {"cx": 320, "cy": 323, "rx": 30, "ry": 25},
    "444-027654-004": {"cx": 353, "cy": 182, "rx": 20, "ry": 20},
}


def generate_heatmap(defect: dict, filename: Path):
    """Generate XAI heatmap — red/yellow gradient centered on defect location."""
    w, h = IMG_SIZE
    cx, cy = defect["cx"], defect["cy"]
    rx, ry = defect["rx"], defect["ry"]

    # Create RGBA image (transparent background)
    img = Image.new("RGBA", IMG_SIZE, (0, 0, 0, 0))
    arr = np.zeros((h, w, 4), dtype=np.uint8)

    # Generate gaussian-like heatmap
    Y, X = np.ogrid[:h, :w]
    dist = ((X - cx) / (rx * 1.5)) ** 2 + ((Y - cy) / (ry * 1.5)) ** 2

    # Intensity falls off with distance
    intensity = np.clip(1.0 - dist, 0, 1) ** 1.5

    # Color: hot colormap (black → red → yellow → white)
    for y in range(h):
        for x in range(w):
            val = intensity[y, x]
            if val > 0.01:
                if val > 0.8:
                    r, g, b = 255, int(255 * (val - 0.8) / 0.2), 50
                elif val > 0.4:
                    r, g, b = int(255 * (val - 0.4) / 0.4), 0, 0
                else:
                    r, g, b = int(180 * val / 0.4), 0, 0
                alpha = int(val * 160)  # Semi-transparent
                arr[y, x] = [r, g, b, alpha]

    img = Image.fromarray(arr, "RGBA")
    # Slight blur for smoothness
    img = img.filter(ImageFilter.GaussianBlur(radius=3))

    filename.parent.mkdir(parents=True, exist_ok=True)
    img.save(str(filename), "PNG")


def generate_golden_diff(defect: dict, filename: Path):
    """Generate golden comparison diff — green (OK) with red patch (deviation)."""
    w, h = IMG_SIZE
    cx, cy = defect["cx"], defect["cy"]
    rx, ry = defect["rx"], defect["ry"]

    # Create RGBA image
    arr = np.zeros((h, w, 4), dtype=np.uint8)

    # Light green tint everywhere (part matches golden reference)
    arr[:, :, 1] = 40   # green channel
    arr[:, :, 3] = 25   # very low alpha (subtle green wash)

    # Red/magenta patch at defect location (deviation from golden)
    Y, X = np.ogrid[:h, :w]
    dist = ((X - cx) / (rx * 1.2)) ** 2 + ((Y - cy) / (ry * 1.2)) ** 2
    deviation_mask = dist < 1.0

    # Red deviation area
    arr[deviation_mask, 0] = 220  # red
    arr[deviation_mask, 1] = 40   # less green
    arr[deviation_mask, 2] = 80   # slight magenta
    # Alpha proportional to deviation strength
    deviation_strength = np.clip(1.0 - dist, 0, 1)
    arr[:, :, 3] = np.where(deviation_mask, (deviation_strength * 140).astype(np.uint8)[:, :], arr[:, :, 3])

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
