"""Download realistic semiconductor part images from free sources."""
import urllib.request
import os
from PIL import Image
from io import BytesIO
from pathlib import Path

OUT_BASE = Path("demo_data/images")

# Unsplash free images (resized to 640x480 via URL params)
# These are public domain / free-to-use images
METAL_PLATE_URLS = {
    "top": "https://images.unsplash.com/photo-1635070041078-e363dbe005cb?w=640&h=480&fit=crop&crop=center",
    "north": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=640&h=480&fit=crop&crop=center",
    "south": "https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=640&h=480&fit=crop&crop=center",
    "east": "https://images.unsplash.com/photo-1567789884554-0b844b597180?w=640&h=480&fit=crop&crop=center",
    "west": "https://images.unsplash.com/photo-1503602642458-232111445657?w=640&h=480&fit=crop&crop=center",
}

PCB_URLS = {
    "top": "https://images.unsplash.com/photo-1518770660439-4636190af475?w=640&h=480&fit=crop&crop=center",
    "north": "https://images.unsplash.com/photo-1555617766-c94804975da3?w=640&h=480&fit=crop&crop=center",
    "south": "https://images.unsplash.com/photo-1601132359864-c974e79890ac?w=640&h=480&fit=crop&crop=center",
    "east": "https://images.unsplash.com/photo-1562408590-e32931084e23?w=640&h=480&fit=crop&crop=center",
    "west": "https://images.unsplash.com/photo-1580584126903-c17d41830450?w=640&h=480&fit=crop&crop=center",
}

WELDMENT_URLS = {
    "top": "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?w=640&h=480&fit=crop&crop=center",
    "north": "https://images.unsplash.com/photo-1565193566173-7a0ee3dbe261?w=640&h=480&fit=crop&crop=center",
    "south": "https://images.unsplash.com/photo-1590959651373-a3db0f38a961?w=640&h=480&fit=crop&crop=center",
    "east": "https://images.unsplash.com/photo-1581093458791-9d42e3c7e117?w=640&h=480&fit=crop&crop=center",
    "west": "https://images.unsplash.com/photo-1504917595217-d4dc5ebe6122?w=640&h=480&fit=crop&crop=bottom",
}

SCREW_URLS = {
    "top": "https://images.unsplash.com/photo-1572981779307-38b8cabb2407?w=640&h=480&fit=crop&crop=center",
    "north": "https://images.unsplash.com/photo-1567789884554-0b844b597180?w=640&h=480&fit=crop&crop=top",
    "south": "https://images.unsplash.com/photo-1558618666-fcd25c85f82e?w=640&h=480&fit=crop&crop=bottom",
    "east": "https://images.unsplash.com/photo-1504328345606-18bbc8c9d7d1?w=640&h=480&fit=crop&crop=left",
    "west": "https://images.unsplash.com/photo-1503602642458-232111445657?w=640&h=480&fit=crop&crop=right",
}


def download_image(url: str, out_path: Path) -> bool:
    """Download an image, resize to 640x480, and save."""
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        data = urllib.request.urlopen(req, timeout=15).read()
        img = Image.open(BytesIO(data))
        img = img.convert("RGB")
        img = img.resize((640, 480), Image.LANCZOS)
        img.save(str(out_path), quality=90)
        # Also save thumbnail
        thumb = img.copy()
        thumb.thumbnail((160, 120))
        thumb_path = out_path.parent / f"{out_path.stem}_thumb{out_path.suffix}"
        thumb.save(str(thumb_path), quality=85)
        print(f"  OK: {out_path.name} ({os.path.getsize(out_path)} bytes)")
        return True
    except Exception as e:
        print(f"  FAIL: {out_path.name} - {e}")
        return False


def download_set(urls: dict, folder: str):
    """Download a set of images for a family/variant."""
    out_dir = OUT_BASE / folder
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"\n{folder}:")
    for angle, url in urls.items():
        download_image(url, out_dir / f"{angle}.jpg")


def main():
    print("Downloading realistic images from Unsplash (free license)...")
    download_set(METAL_PLATE_URLS, "metal_plate/clean")
    download_set(PCB_URLS, "pcb/clean")
    download_set(WELDMENT_URLS, "weldment/clean")
    download_set(SCREW_URLS, "screw/clean")
    print("\nDone! Images downloaded.")
    print("NOTE: Run generate_realistic_images.py after this to create scenario variants.")


if __name__ == "__main__":
    main()
