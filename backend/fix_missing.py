import urllib.request
from PIL import Image
from io import BytesIO
from pathlib import Path

fixes = {
    "demo_data/images/metal_plate/clean/north.jpg": "https://images.unsplash.com/photo-1567789884554-0b844b597180?w=640&h=480&fit=crop&crop=top",
    "demo_data/images/weldment/clean/east.jpg": "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?w=640&h=480&fit=crop&crop=top",
    "demo_data/images/screw/clean/south.jpg": "https://images.unsplash.com/photo-1572981779307-38b8cabb2407?w=640&h=480&fit=crop&crop=bottom",
}

for path, url in fixes.items():
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=15).read()
        img = Image.open(BytesIO(data)).convert("RGB").resize((640, 480), Image.LANCZOS)
        img.save(path, quality=90)
        thumb = img.copy()
        thumb.thumbnail((160, 120))
        p = Path(path)
        thumb.save(str(p.parent / f"{p.stem}_thumb{p.suffix}"), quality=85)
        print(f"OK: {path}")
    except Exception as e:
        print(f"FAIL: {path} - {e}")
