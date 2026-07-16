"""
Generate realistic-looking industrial inspection demo images.
Each scenario gets a UNIQUE base appearance + specific defect.
Uses proper lighting simulation, noise, and texture.
"""
import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageEnhance
from pathlib import Path
import random

DEMO_DIR = Path("demo_data/images")
ANGLES = ["top", "north", "south", "east", "west"]
IMG_SIZE = (640, 480)
THUMB_SIZE = (160, 120)

random.seed(42)
np.random.seed(42)


def make_brushed_metal(w: int, h: int, base_gray: int = 170, blue_tint: int = 3, 
                       grain_dir: str = "horizontal") -> np.ndarray:
    """Create realistic brushed metal texture."""
    img = np.zeros((h, w, 3), dtype=np.float32)
    
    # Base color with slight gradient (simulates curved surface lighting)
    for y in range(h):
        for x in range(w):
            # Gentle radial gradient from center
            dx = (x - w / 2) / (w / 2)
            dy = (y - h / 2) / (h / 2)
            dist = np.sqrt(dx * dx * 0.3 + dy * dy * 0.5)
            light = 1.0 - dist * 0.15
            gray = base_gray * light
            img[y, x] = [gray - blue_tint, gray, gray + blue_tint]
    
    # Add machining/brush marks
    if grain_dir == "horizontal":
        for y in range(h):
            line_val = random.gauss(0, 3)
            img[y, :, :] += line_val
    else:
        for x in range(w):
            line_val = random.gauss(0, 3)
            img[:, x, :] += line_val
    
    # Fine noise
    noise = np.random.normal(0, 2, (h, w, 3))
    img += noise
    
    return np.clip(img, 0, 255).astype(np.uint8)


def make_clean_aluminum_top(seed: int = 0) -> Image.Image:
    """Top view - plan view showing the machined pocket, holes, and features from above."""
    np.random.seed(seed)
    w, h = IMG_SIZE
    arr = make_brushed_metal(w, h, base_gray=175, blue_tint=4)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Large machined pocket (rectangular depression)
    pocket = (100, 80, w-100, h-80)
    draw.rectangle(pocket, outline=(135, 137, 141), width=3)
    # Inner step
    draw.rectangle((115, 95, w-115, h-95), outline=(150, 152, 156), width=1)
    # Pocket floor (slightly different shade)
    for y in range(100, h-100):
        shade = 162 + random.randint(-2, 2)
        draw.line([(120, y), (w-120, y)], fill=(shade, shade, shade+2))
    
    # 6 mounting holes in a rectangular pattern
    holes = [(130, 110), (w//2, 110), (w-130, 110),
             (130, h-110), (w//2, h-110), (w-130, h-110)]
    for hx, hy in holes:
        draw.ellipse([(hx-12, hy-12), (hx+12, hy+12)], fill=(45, 47, 51), outline=(75, 77, 81), width=2)
        draw.ellipse([(hx-5, hy-5), (hx+5, hy+5)], fill=(30, 32, 36))
    
    # Center crosshair alignment mark
    cx, cy = w//2, h//2
    draw.line([(cx-25, cy), (cx+25, cy)], fill=(130, 132, 136), width=1)
    draw.line([(cx, cy-25), (cx, cy+25)], fill=(130, 132, 136), width=1)
    draw.ellipse([(cx-3, cy-3), (cx+3, cy+3)], outline=(130, 132, 136))
    
    # Engraved part number (bottom-right)
    draw.text((w-170, h-45), "839-041322", fill=(140, 142, 146))
    draw.text((w-170, h-30), "REV C  AL6061", fill=(148, 150, 154))
    
    return img


def make_north_view(seed: int = 0) -> Image.Image:
    """North view - front face showing the plate thickness and chamfered edges."""
    np.random.seed(seed + 200)
    w, h = IMG_SIZE
    # Darker background (looking at the part from the front)
    arr = np.full((h, w, 3), 85, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # The plate body (horizontal rectangle showing thickness)
    plate_top = h // 3
    plate_bot = 2 * h // 3
    plate_left = 80
    plate_right = w - 80
    
    # Main body
    draw.rectangle([(plate_left, plate_top), (plate_right, plate_bot)], fill=(172, 174, 178))
    
    # Top surface (slight gradient showing the flat face)
    for y in range(plate_top, plate_top + 15):
        shade = 185 - (y - plate_top)
        draw.line([(plate_left, y), (plate_right, y)], fill=(shade, shade, shade+2))
    
    # Bottom chamfer
    for i in range(8):
        shade = 155 + i * 2
        draw.line([(plate_left+i, plate_bot-i), (plate_right-i, plate_bot-i)], fill=(shade, shade, shade))
    
    # Machining marks (horizontal lines)
    for y in range(plate_top + 20, plate_bot - 10, 4):
        alpha = 165 + random.randint(-3, 3)
        draw.line([(plate_left+5, y), (plate_right-5, y)], fill=(alpha, alpha, alpha+1))
    
    # Pocket opening visible from this angle (dark slot)
    slot_l = w // 3
    slot_r = 2 * w // 3
    draw.rectangle([(slot_l, plate_top), (slot_r, plate_top + 12)], fill=(100, 102, 106))
    
    # Dimension annotation
    draw.line([(plate_left-20, plate_top), (plate_left-20, plate_bot)], fill=(80, 150, 220), width=1)
    draw.line([(plate_left-25, plate_top), (plate_left-15, plate_top)], fill=(80, 150, 220), width=1)
    draw.line([(plate_left-25, plate_bot), (plate_left-15, plate_bot)], fill=(80, 150, 220), width=1)
    draw.text((plate_left-55, h//2-5), "12.7", fill=(80, 150, 220))
    
    return img


def make_south_view(seed: int = 0) -> Image.Image:
    """South view - back face showing connector slots and mounting tabs."""
    np.random.seed(seed + 300)
    w, h = IMG_SIZE
    arr = np.full((h, w, 3), 90, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    plate_top = h // 3
    plate_bot = 2 * h // 3
    plate_left = 80
    plate_right = w - 80
    
    # Main body
    draw.rectangle([(plate_left, plate_top), (plate_right, plate_bot)], fill=(168, 170, 174))
    
    # Three keyway slots on bottom edge
    for sx in [w//4, w//2, 3*w//4]:
        draw.rectangle([(sx-20, plate_bot-25), (sx+20, plate_bot)], fill=(60, 62, 66))
        draw.rectangle([(sx-18, plate_bot-23), (sx+18, plate_bot-2)], fill=(70, 72, 76))
    
    # Mounting tab extending below
    tab_cx = w // 2
    draw.polygon([(tab_cx-30, plate_bot), (tab_cx+30, plate_bot), 
                  (tab_cx+25, plate_bot+35), (tab_cx-25, plate_bot+35)], 
                 fill=(165, 167, 171), outline=(130, 132, 136))
    draw.ellipse([(tab_cx-8, plate_bot+10), (tab_cx+8, plate_bot+26)], fill=(50, 52, 56))
    
    # Surface texture
    for y in range(plate_top + 5, plate_bot - 5, 5):
        alpha = 162 + random.randint(-3, 3)
        draw.line([(plate_left+3, y), (plate_right-3, y)], fill=(alpha, alpha, alpha))
    
    return img


def make_east_view(seed: int = 0) -> Image.Image:
    """East view - narrow right edge showing bolt pattern and thickness."""
    np.random.seed(seed + 400)
    w, h = IMG_SIZE
    arr = np.full((h, w, 3), 80, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Narrow plate edge (tall rectangle)
    edge_left = w // 3
    edge_right = 2 * w // 3
    edge_top = 50
    edge_bot = h - 50
    
    draw.rectangle([(edge_left, edge_top), (edge_right, edge_bot)], fill=(170, 172, 176))
    
    # Chamfer on edges
    for i in range(6):
        shade = 180 + i * 2
        draw.line([(edge_left+i, edge_top), (edge_left+i, edge_bot)], fill=(shade, shade, shade))
        draw.line([(edge_right-i, edge_top), (edge_right-i, edge_bot)], fill=(shade, shade, shade))
    
    # 4 bolt holes visible from this edge
    for by in [h//5, 2*h//5, 3*h//5, 4*h//5]:
        cx = w // 2
        draw.ellipse([(cx-9, by-9), (cx+9, by+9)], fill=(50, 52, 56), outline=(85, 87, 91), width=2)
        draw.ellipse([(cx-3, by-3), (cx+3, by+3)], fill=(35, 37, 41))
    
    # Vertical machining marks
    for x in range(edge_left + 8, edge_right - 8, 3):
        alpha = 163 + random.randint(-3, 3)
        draw.line([(x, edge_top+8), (x, edge_bot-8)], fill=(alpha, alpha, alpha))
    
    # Height dimension
    draw.line([(edge_right+25, edge_top), (edge_right+25, edge_bot)], fill=(80, 150, 220), width=1)
    draw.text((edge_right+30, h//2-5), "254mm", fill=(80, 150, 220))
    
    return img


def make_west_view(seed: int = 0) -> Image.Image:
    """West view - narrow left edge showing label/etching area and QC stamp."""
    np.random.seed(seed + 500)
    w, h = IMG_SIZE
    arr = np.full((h, w, 3), 82, dtype=np.uint8)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Narrow plate edge
    edge_left = w // 3
    edge_right = 2 * w // 3
    edge_top = 50
    edge_bot = h - 50
    
    draw.rectangle([(edge_left, edge_top), (edge_right, edge_bot)], fill=(172, 174, 178))
    
    # Engraved label area (recessed rectangle)
    label_top = h // 4
    label_bot = h // 4 + 80
    draw.rectangle([(edge_left+15, label_top), (edge_right-15, label_bot)], 
                   fill=(158, 160, 164), outline=(140, 142, 146))
    draw.text((edge_left+25, label_top+10), "P/N: 839-041322", fill=(120, 122, 126))
    draw.text((edge_left+25, label_top+28), "REV: C", fill=(120, 122, 126))
    draw.text((edge_left+25, label_top+46), "AL6061-T6", fill=(120, 122, 126))
    
    # QC inspection stamp (circular)
    qc_cy = 3 * h // 4
    qc_cx = w // 2
    draw.ellipse([(qc_cx-20, qc_cy-20), (qc_cx+20, qc_cy+20)], outline=(60, 160, 80), width=2)
    draw.text((qc_cx-8, qc_cy-7), "QC", fill=(60, 160, 80))
    draw.text((qc_cx-12, qc_cy+8), "PASS", fill=(60, 160, 80))
    
    # Vertical machining marks
    for x in range(edge_left + 5, edge_right - 5, 3):
        alpha = 165 + random.randint(-3, 3)
        draw.line([(x, edge_top+5), (x, edge_bot-5)], fill=(alpha, alpha, alpha))
    
    return img


def make_pcb_board() -> Image.Image:
    """Realistic PCB appearance."""
    w, h = IMG_SIZE
    # Green PCB base with slight texture
    arr = np.zeros((h, w, 3), dtype=np.uint8)
    for y in range(h):
        for x in range(w):
            noise = random.randint(-5, 5)
            arr[y, x] = [25 + noise, 80 + noise, 40 + noise]
    
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Copper traces (horizontal and vertical)
    for _ in range(25):
        y = random.randint(20, h-20)
        x1 = random.randint(0, w//2)
        x2 = x1 + random.randint(100, 300)
        draw.line([(x1, y), (x2, y)], fill=(180, 150, 60), width=2)
    for _ in range(20):
        x = random.randint(20, w-20)
        y1 = random.randint(0, h//2)
        y2 = y1 + random.randint(80, 250)
        draw.line([(x, y1), (x, y2)], fill=(180, 150, 60), width=2)
    
    # IC packages (black rectangles with pads)
    ics = [(150, 120, 60, 60), (350, 200, 50, 50), (480, 100, 40, 55), (200, 320, 70, 45)]
    for ix, iy, iw, ih in ics:
        draw.rectangle([(ix, iy), (ix+iw, iy+ih)], fill=(20, 20, 25), outline=(40, 40, 45))
        # Pin 1 dot
        draw.ellipse([(ix+3, iy+3), (ix+7, iy+7)], fill=(150, 150, 155))
        # Pads on sides
        for p in range(max(iw, ih) // 8):
            draw.rectangle([(ix-3, iy+4+p*8), (ix, iy+7+p*8)], fill=(190, 165, 70))
            draw.rectangle([(ix+iw, iy+4+p*8), (ix+iw+3, iy+7+p*8)], fill=(190, 165, 70))
    
    # SMD components (capacitors, resistors)
    for _ in range(30):
        cx = random.randint(50, w-50)
        cy = random.randint(50, h-50)
        cw, ch = random.choice([(8, 4), (6, 3), (10, 5)])
        color = random.choice([(40, 30, 20), (80, 60, 40), (100, 80, 60)])
        draw.rectangle([(cx, cy), (cx+cw, cy+ch)], fill=color)
        # Solder pads
        draw.rectangle([(cx-2, cy), (cx, cy+ch)], fill=(190, 165, 70))
        draw.rectangle([(cx+cw, cy), (cx+cw+2, cy+ch)], fill=(190, 165, 70))
    
    # Silk screen text
    draw.text((30, h-25), "PCB REV E  444-027654", fill=(200, 200, 200))
    
    return img


def make_screw_assembly(angle: str = "top") -> Image.Image:
    """Machined plate with 8 screw positions — all present."""
    w, h = IMG_SIZE
    arr = make_brushed_metal(w, h, base_gray=168, blue_tint=3)
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    if angle == "top":
        # Rectangular mounting plate with 8 screw holes in a pattern
        # Plate outline
        draw.rectangle([(60, 60), (w-60, h-60)], outline=(130, 132, 136), width=2)
        
        # 8 screw positions in 2 rows of 4
        screw_positions = [
            (150, 150), (270, 150), (390, 150), (510, 150),  # Top row
            (150, 330), (270, 330), (390, 330), (510, 330),  # Bottom row
        ]
        for sx, sy in screw_positions:
            # Screw head (installed)
            draw.ellipse([(sx-14, sy-14), (sx+14, sy+14)], fill=(120, 122, 126), outline=(95, 97, 101), width=2)
            # Phillips cross slot
            draw.line([(sx-7, sy), (sx+7, sy)], fill=(70, 72, 76), width=2)
            draw.line([(sx, sy-7), (sx, sy+7)], fill=(70, 72, 76), width=2)
            # Subtle highlight
            draw.arc([(sx-12, sy-12), (sx+12, sy+12)], start=200, end=320, fill=(155, 157, 161), width=1)
        
        # Center alignment feature
        draw.rectangle([(w//2-40, h//2-25), (w//2+40, h//2+25)], outline=(140, 142, 146), width=1)
        draw.text((w-140, h-40), "715-098456", fill=(130, 132, 136))
    else:
        # Side views — show plate edge with screw heads visible
        plate_top = h // 3
        plate_bot = 2 * h // 3
        draw.rectangle([(50, plate_top), (w-50, plate_bot)], fill=(165, 167, 171), outline=(130, 132, 136))
        # Screw heads visible from side (bumps on top surface)
        for sx in [150, 270, 390, 510]:
            draw.arc([(sx-10, plate_top-6), (sx+10, plate_top+6)], start=180, end=360, fill=(120, 122, 126), width=3)
    
    return img


def make_weldment() -> Image.Image:
    """Stainless steel weldment with weld bead."""
    w, h = IMG_SIZE
    arr = make_brushed_metal(w, h, base_gray=180, blue_tint=2, grain_dir="horizontal")
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Weld bead across middle
    weld_y = h // 2
    for x in range(60, w-60):
        wy = weld_y + int(3 * np.sin(x * 0.08))
        # Weld bead texture
        for dy in range(-5, 5):
            shade = 130 + abs(dy) * 8 + random.randint(-5, 5)
            draw.point((x, wy + dy), fill=(shade, shade, shade + 2))
    
    # Heat-affected zone (subtle coloring)
    for x in range(60, w-60):
        wy = weld_y + int(3 * np.sin(x * 0.08))
        for dy in range(6, 20):
            if random.random() > 0.4:
                r = 180 + random.randint(-10, 10)
                g = 160 + random.randint(-10, 10)
                b = 120 + random.randint(-10, 10)
                draw.point((x, wy + dy), fill=(r, g, b))
                draw.point((x, wy - dy), fill=(r, g, b))
    
    return img


# ============ DEFECT OVERLAYS (LARGE AND OBVIOUS) ============

def add_deep_scratches(img: Image.Image) -> Image.Image:
    """Add prominent scratches — bright white lines with dark edges."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # 3 prominent scratches at different angles
    scratches = [
        (50, h//3, w-80, h//3 - 15),       # Nearly horizontal
        (w//4, 50, 3*w//4, h//2 + 30),      # Diagonal
        (100, 2*h//3, w-150, 2*h//3 + 10),  # Lower horizontal
    ]
    for x1, y1, x2, y2 in scratches:
        # Dark shadow
        draw.line([(x1, y1+3), (x2, y2+3)], fill=(60, 62, 66), width=3)
        # Bright scratch (exposed metal)
        draw.line([(x1, y1), (x2, y2)], fill=(245, 247, 255), width=3)
        # Specular highlight
        draw.line([(x1+2, y1-1), (x2+2, y2-1)], fill=(255, 255, 255), width=1)
    
    return img


def add_large_dent(img: Image.Image) -> Image.Image:
    """Add a very prominent impact dent."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2, h // 2
    
    # Create dent by darkening a circular region
    arr = np.array(img)
    Y, X = np.ogrid[:h, :w]
    dist = np.sqrt((X - cx) ** 2 + (Y - cy) ** 2)
    
    # Darken inside the dent radius
    mask = dist < 60
    arr[mask] = (arr[mask] * 0.7).astype(np.uint8)
    
    # Very dark center
    center_mask = dist < 25
    arr[center_mask] = (arr[center_mask] * 0.5).astype(np.uint8)
    
    img = Image.fromarray(arr)
    draw = ImageDraw.Draw(img)
    
    # Bright rim (displaced metal catches light)
    draw.arc([(cx-60, cy-60), (cx+60, cy+60)], start=190, end=350, fill=(235, 237, 245), width=5)
    # Dark rim opposite side
    draw.arc([(cx-60, cy-60), (cx+60, cy+60)], start=10, end=170, fill=(90, 92, 96), width=4)
    # Radial cracks
    for angle in range(0, 360, 25):
        rad = np.radians(angle)
        x1 = cx + int(55 * np.cos(rad))
        y1 = cy + int(55 * np.sin(rad))
        x2 = cx + int(75 * np.cos(rad))
        y2 = cy + int(75 * np.sin(rad))
        draw.line([(x1, y1), (x2, y2)], fill=(100, 102, 106), width=1)
    
    return img


def add_missing_fastener(img: Image.Image) -> Image.Image:
    """Show a clearly empty mounting point — no annotations (overlay handles that)."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Position where fastener is missing (upper-left quadrant)
    cx, cy = w // 4, h // 4
    
    # Dark empty hole (clearly no fastener installed)
    draw.ellipse([(cx-22, cy-22), (cx+22, cy+22)], fill=(20, 22, 26), outline=(60, 62, 66), width=3)
    # Thread marks inside the empty hole
    for r in [7, 13, 19]:
        draw.arc([(cx-r, cy-r), (cx+r, cy+r)], start=0, end=360, fill=(40, 42, 46), width=1)
    # Depth shadow in center
    draw.ellipse([(cx-8, cy-8), (cx+8, cy+8)], fill=(10, 12, 16))
    
    # Show other fasteners are PRESENT (for clear contrast)
    other_holes = [(3*w//4, h//4), (w//4, 3*h//4), (3*w//4, 3*h//4), (w//2, h//4), (w//2, 3*h//4)]
    for ox, oy in other_holes:
        # Filled screw head (present)
        draw.ellipse([(ox-14, oy-14), (ox+14, oy+14)], fill=(110, 112, 116), outline=(90, 92, 96), width=2)
        # Phillips cross slot
        draw.line([(ox-6, oy), (ox+6, oy)], fill=(75, 77, 81), width=2)
        draw.line([(ox, oy-6), (ox, oy+6)], fill=(75, 77, 81), width=2)
    
    return img


def add_heavy_contamination(img: Image.Image) -> Image.Image:
    """Add a large, obvious contamination patch."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    cx, cy = w // 2 + 30, h // 2 - 20
    
    # Large dark irregular patch
    arr = np.array(img)
    for _ in range(5000):
        px = cx + int(random.gauss(0, 45))
        py = cy + int(random.gauss(0, 35))
        if 0 <= px < w and 0 <= py < h:
            darkness = random.randint(20, 60)
            arr[py, px] = [darkness, darkness - 5, darkness - 10]
    
    img = Image.fromarray(arr)
    # Blur slightly for realism
    img = img.filter(ImageFilter.GaussianBlur(radius=1))
    draw = ImageDraw.Draw(img)
    
    # Scattered particles around main patch
    for _ in range(50):
        px = cx + random.randint(-100, 100)
        py = cy + random.randint(-80, 80)
        size = random.randint(3, 8)
        draw.ellipse([(px, py), (px+size, py+size)], fill=(30 + random.randint(0, 30), 25, 20))
    
    # Stain boundary ring
    draw.ellipse([(cx-70, cy-55), (cx+70, cy+55)], outline=(50, 45, 40), width=2)
    
    return img


def add_visible_crack(img: Image.Image) -> Image.Image:
    """Add a prominent crack pattern."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Main crack - thick, dark, jagged
    x, y = w // 4, h // 2
    points = [(x, y)]
    for _ in range(30):
        x += random.randint(8, 16)
        y += random.randint(-8, 8)
        points.append((x, y))
    
    # Dark wide crack
    draw.line(points, fill=(20, 20, 25), width=5)
    # Inner line
    draw.line(points, fill=(10, 10, 15), width=2)
    # White stress highlight on one edge
    highlight = [(px, py - 4) for px, py in points]
    draw.line(highlight, fill=(230, 232, 240), width=2)
    
    # Branch 1
    mid = points[10]
    bx, by = mid
    branch = [(bx, by)]
    for _ in range(15):
        bx += random.randint(4, 12)
        by += random.randint(4, 10)
        branch.append((bx, by))
    draw.line(branch, fill=(25, 25, 30), width=3)
    
    # Branch 2
    mid2 = points[20]
    bx2, by2 = mid2
    branch2 = [(bx2, by2)]
    for _ in range(10):
        bx2 += random.randint(3, 9)
        by2 -= random.randint(3, 9)
        branch2.append((bx2, by2))
    draw.line(branch2, fill=(30, 30, 35), width=2)
    
    return img


def add_surface_discoloration(img: Image.Image) -> Image.Image:
    """Add subtle but visible surface anomaly — heat tint/discoloration."""
    arr = np.array(img).astype(np.float32)
    w, h = img.size
    cx, cy = w // 2, h // 2
    
    # Yellowish-brown tint in an oval region
    Y, X = np.ogrid[:h, :w]
    dist = ((X - cx) / 60.0) ** 2 + ((Y - cy) / 40.0) ** 2
    mask = dist < 1.0
    
    # Apply tint
    arr[mask, 0] = np.minimum(arr[mask, 0] * 1.15 + 15, 255)  # More red
    arr[mask, 1] = arr[mask, 1] * 0.92  # Less green
    arr[mask, 2] = arr[mask, 2] * 0.75  # Much less blue
    
    img = Image.fromarray(arr.astype(np.uint8))
    draw = ImageDraw.Draw(img)
    # Subtle boundary
    draw.ellipse([(cx-60, cy-40), (cx+60, cy+40)], outline=(170, 140, 90), width=1)
    
    return img


# ============ SCENARIO GENERATION ============

SCENARIOS = {
    "scenario-01": {"base": "clean_plate", "defect": None, "desc": "Clean pass"},
    "scenario-02": {"base": "clean_plate", "defect": "scratch", "desc": "Scratched plate"},
    "scenario-03": {"base": "clean_plate", "defect": "dent", "desc": "Dented plate"},
    "scenario-04": {"base": "clean_plate", "defect": "missing", "desc": "Missing fastener"},
    "scenario-05": {"base": "weldment", "defect": "contamination", "desc": "Contaminated weld"},
    "scenario-06": {"base": "clean_plate", "defect": "anomaly", "desc": "Unknown anomaly"},
    "scenario-07": {"base": "clean_plate_alt", "defect": "anomaly", "desc": "Subtle deviation"},
    "scenario-08": {"base": "pcb", "defect": "pcb_multi", "desc": "PCB multi-defect"},
    "scenario-09": {"base": "weldment", "defect": "anomaly", "desc": "Heat tint"},
    "scenario-10": {"base": "clean_plate_alt", "defect": "scratch", "desc": "False positive scratch"},
}

DEFECT_APPLIERS = {
    "scratch": add_deep_scratches,
    "dent": add_large_dent,
    "missing": add_missing_fastener,
    "contamination": add_heavy_contamination,
    "crack": add_visible_crack,
    "anomaly": add_surface_discoloration,
}


def get_base_image(base_type: str, angle: str) -> Image.Image:
    """Generate a base image for the given type and angle."""
    if base_type == "clean_plate":
        if angle == "top":
            return make_clean_aluminum_top(seed=1)
        elif angle == "north":
            return make_north_view(seed=2)
        elif angle == "south":
            return make_south_view(seed=3)
        elif angle == "east":
            return make_east_view(seed=4)
        else:
            return make_west_view(seed=5)
    elif base_type == "clean_plate_alt":
        if angle == "top":
            return make_clean_aluminum_top(seed=10)
        elif angle == "north":
            return make_north_view(seed=11)
        elif angle == "south":
            return make_south_view(seed=12)
        elif angle == "east":
            return make_east_view(seed=13)
        else:
            return make_west_view(seed=14)
    elif base_type == "pcb":
        return make_pcb_board()
    elif base_type == "weldment":
        return make_weldment()
    else:
        return make_clean_aluminum_top(seed=99)


def apply_pcb_multi_defect(img: Image.Image) -> Image.Image:
    """Apply multiple PCB-specific defects — large and clearly visible."""
    draw = ImageDraw.Draw(img)
    w, h = img.size
    
    # Missing component — LARGE empty area where component should be
    # Show an obviously empty footprint with exposed copper pads
    cx, cy = 370, 210
    # Component footprint outline (where component should sit)
    draw.rectangle([(cx-18, cy-10), (cx+18, cy+10)], fill=(30, 85, 45))  # bare board
    # Exposed copper pads (large, bright gold, clearly empty)
    draw.rectangle([(cx-18, cy-8), (cx-8, cy+8)], fill=(220, 190, 60), outline=(180, 150, 40), width=1)
    draw.rectangle([(cx+8, cy-8), (cx+18, cy+8)], fill=(220, 190, 60), outline=(180, 150, 40), width=1)
    # Solder paste visible on pads (lighter)
    draw.rectangle([(cx-16, cy-6), (cx-10, cy+6)], fill=(230, 210, 100))
    draw.rectangle([(cx+10, cy-6), (cx+16, cy+6)], fill=(230, 210, 100))
    
    # Solder crack — LARGE visible fracture across an IC package
    bx, by = 500, 127  # Center of the IC at (480, 100, 40, 55)
    # First make the IC body visible (redraw slightly lighter so crack contrasts)
    draw.rectangle([(478, 98), (522, 157)], fill=(35, 35, 40), outline=(55, 55, 60), width=1)
    # CRACK: bright/white fracture line across the IC body (highly visible on dark surface)
    crack_pts = [(478, by-8), (485, by-3), (493, by-10), (500, by-2),
                 (508, by-8), (515, by+2), (522, by-4)]
    # White crack line (thermal stress crack on dark IC)
    draw.line(crack_pts, fill=(220, 220, 225), width=3)
    draw.line(crack_pts, fill=(255, 255, 255), width=1)
    # Dark shadow below crack
    crack_shadow = [(px, py + 3) for px, py in crack_pts]
    draw.line(crack_shadow, fill=(15, 15, 18), width=2)
    
    # Flux contamination residue near connector (dark yellowish stain)
    for _ in range(50):
        px = 80 + random.randint(-40, 40)
        py = 350 + random.randint(-30, 30)
        size = random.randint(3, 9)
        draw.ellipse([(px, py), (px+size, py+size)], fill=(100, 80, 30))
    
    return img


def generate_scenario(scenario_id: str, config: dict):
    """Generate all angle images for one scenario."""
    out_dir = DEMO_DIR / "scenarios" / scenario_id
    out_dir.mkdir(parents=True, exist_ok=True)
    
    base_type = config["base"]
    defect_type = config["defect"]
    
    for angle in ANGLES:
        img = get_base_image(base_type, angle)
        
        # Apply defect only to TOP view (where the camera captures the main surface)
        if defect_type and angle == "top":
            if defect_type == "pcb_multi":
                img = apply_pcb_multi_defect(img)
            else:
                applier = DEFECT_APPLIERS.get(defect_type)
                if applier:
                    img = applier(img)
        
        img.save(out_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(out_dir / f"{angle}_thumb.jpg", quality=85)
    
    print(f"  ✓ {scenario_id}: {config['desc']}")


def main():
    # Also regenerate clean base images for kiosk capture flow
    print("Generating scenario images...")
    for scenario_id, config in SCENARIOS.items():
        generate_scenario(scenario_id, config)
    
    # Regenerate the clean family images used by kiosk flow
    print("\nRegenerating clean capture images...")
    clean_dir = DEMO_DIR / "metal_plate" / "clean"
    clean_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = get_base_image("clean_plate", angle)
        img.save(clean_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(clean_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ metal_plate/clean")
    
    # PCB clean
    pcb_dir = DEMO_DIR / "pcb" / "clean"
    pcb_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_board()
        img.save(pcb_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(pcb_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ pcb/clean")
    
    # Weldment clean
    weld_dir = DEMO_DIR / "weldment" / "clean"
    weld_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_weldment()
        img.save(weld_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(weld_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ weldment/clean")
    
    # Also regenerate screw assembly (shows fastener array)
    print("\nRegenerating screw assembly images...")
    screw_dir = DEMO_DIR / "screw" / "clean"
    screw_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_screw_assembly(angle)
        img.save(screw_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(screw_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ screw/clean")

    # Screw assembly defective (missing one screw) for kiosk flow
    print("\nGenerating kiosk-specific defective images...")
    screw_defect_dir = DEMO_DIR / "kiosk" / "715-098456-003"
    screw_defect_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_screw_assembly(angle)
        if angle == "top":
            # Remove one screw (position #3 = index 2, at (390, 150))
            draw = ImageDraw.Draw(img)
            # Cover the screw with empty hole
            sx, sy = 390, 150
            # Paint over the existing screw with base metal color
            draw.ellipse([(sx-16, sy-16), (sx+16, sy+16)], fill=(168, 170, 174))
            # Empty threaded hole (no screw)
            draw.ellipse([(sx-14, sy-14), (sx+14, sy+14)], fill=(50, 52, 56), outline=(80, 82, 86), width=2)
            # Thread marks
            for r in [5, 9, 13]:
                draw.arc([(sx-r, sy-r), (sx+r, sy+r)], start=0, end=360, fill=(40, 42, 46), width=1)
            draw.ellipse([(sx-4, sy-4), (sx+4, sy+4)], fill=(25, 27, 31))
        img.save(screw_defect_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(screw_defect_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ kiosk/715-098456-003 (missing screw)")
    
    # Gas distribution plate with scratch for kiosk
    scratch_dir = DEMO_DIR / "kiosk" / "839-041322-002"
    scratch_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = get_base_image("clean_plate", angle)
        if angle == "top":
            img = add_deep_scratches(img)
        img.save(scratch_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(scratch_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ kiosk/839-041322-002 (scratch)")

    # ESC Controller Board with defects for kiosk
    pcb_defect_dir = DEMO_DIR / "kiosk" / "444-027654-002"
    pcb_defect_dir.mkdir(parents=True, exist_ok=True)
    for angle in ANGLES:
        img = make_pcb_board()
        if angle == "top":
            img = apply_pcb_multi_defect(img)
        img.save(pcb_defect_dir / f"{angle}.jpg", quality=92)
        thumb = img.copy()
        thumb.thumbnail(THUMB_SIZE)
        thumb.save(pcb_defect_dir / f"{angle}_thumb.jpg", quality=85)
    print("  ✓ kiosk/444-027654-002 (PCB defects)")

    print("\nDone! All images regenerated.")


if __name__ == "__main__":
    main()
