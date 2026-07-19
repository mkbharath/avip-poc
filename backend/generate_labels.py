"""Generate label images for new PCB parts."""
from PIL import Image, ImageDraw
from pathlib import Path

out = Path("demo_data/labels")
parts = [
    ("444-027654-003", "RF Driver Board"),
    ("444-027654-004", "Power Distribution Board"),
]

for part_num, name in parts:
    img = Image.new("RGB", (240, 120), (250, 250, 252))
    draw = ImageDraw.Draw(img)
    draw.rectangle([(4, 4), (235, 115)], outline=(180, 182, 186), width=1)
    draw.text((12, 12), "LAM RESEARCH", fill=(27, 42, 74))
    draw.text((12, 30), f"P/N: {part_num}", fill=(15, 20, 30))
    draw.text((12, 50), f"DESC: {name}", fill=(80, 85, 95))
    draw.text((12, 70), "REV: A  SUPPLIER: CircuitPro", fill=(100, 105, 115))
    draw.text((12, 90), "MAT: FR-4 / Mixed", fill=(120, 125, 135))
    img.save(out / f"label_{part_num}.jpg", quality=90)
    print(f"  label_{part_num}.jpg")

print("Done!")
