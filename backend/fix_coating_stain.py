"""Find all red annotation positions in coating stain images."""
import cv2, numpy as np, fitz
from pathlib import Path
from PIL import Image, ImageEnhance, ImageDraw

doc = fitz.open('/Users/bharathm/LamResearch/Defect pic samples.pdf')

def find_red_clusters(img_bgr, min_area=300):
    hsv = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2HSV)
    rgb = cv2.cvtColor(img_bgr, cv2.COLOR_BGR2RGB)
    r,g,b = rgb[:,:,0].astype(int), rgb[:,:,1].astype(int), rgb[:,:,2].astype(int)
    m1 = cv2.inRange(hsv, np.array([0,80,80]), np.array([10,255,255]))
    m2 = cv2.inRange(hsv, np.array([160,80,80]), np.array([180,255,255]))
    m3 = ((r>130)&(r>g+50)&(r>b+50)).astype(np.uint8)*255
    mask = m1|m2|m3
    k = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(7,7))
    closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, k)
    n, labels, stats, centroids = cv2.connectedComponentsWithStats(closed)
    clusters = []
    for i in range(1, n):
        area = stats[i, cv2.CC_STAT_AREA]
        if area >= min_area:
            cx, cy = int(centroids[i][0]), int(centroids[i][1])
            clusters.append((area, cx, cy))
    clusters.sort(key=lambda x: x[0], reverse=True)
    return clusters

def crop_transform(orig_w, orig_h):
    tr = 640/480; cr = orig_w/orig_h
    if cr > tr:
        cw = int(orig_h*tr); lc = (orig_w-cw)//2; tc = 0; ch = orig_h
    else:
        ch = int(orig_w/tr); lc = 0; tc = (orig_h-ch)//2; cw = orig_w
    return lc, tc, 640/cw, 480/ch

def map_bbox(cx, cy, orig_w, orig_h, bw=140, bh=110):
    lc, tc, sx, sy = crop_transform(orig_w, orig_h)
    mx = max(70, min(int(cx*sx), 570)); my = max(55, min(int((cy-tc)*sy), 425))
    bx = max(0, min(mx-bw//2, 640-bw)); by = max(0, min(my-bh//2, 480-bh))
    return {"x": bx, "y": by, "width": bw, "height": bh}

# Scenarios with coating stain across multiple PDF images
COATING_STAIN_SOURCES = {
    # S27 = p4 img2 (700x1031) dark coated bowl - THIS is the one in the screenshot
    33: {"page": 3, "img_idx": 1},   # p4 img2
    # S15 = p4 img4 perforated plate
    15: {"page": 3, "img_idx": 3},   # p4 img4
}

SCENARIOS_DIR = Path('demo_data/images/scenarios')

for s, info in COATING_STAIN_SOURCES.items():
    page = doc[info['page']]
    imgs = page.get_images(full=True)
    xref = imgs[info['img_idx']][0]
    pix = fitz.Pixmap(doc, xref)
    if pix.n > 4: pix = fitz.Pixmap(fitz.csRGB, pix)
    pix.save(f'/tmp/stain_orig_{s}.png')
    orig = cv2.imread(f'/tmp/stain_orig_{s}.png')
    orig_h, orig_w = orig.shape[:2]
    
    clusters = find_red_clusters(orig)
    print(f'\nS{s} ({orig_w}x{orig_h}): {len(clusters)} red clusters')
    
    bboxes = []
    for area, cx, cy in clusters[:4]:  # max 4
        b = map_bbox(cx, cy, orig_w, orig_h)
        bboxes.append(b)
        print(f'  orig=({cx},{cy}) area={area} -> bbox {b}')
    
    # Draw verification
    clean = cv2.imread(str(SCENARIOS_DIR/f'scenario-{s:02d}'/'top.jpg'))
    if clean is not None:
        colors = [(0,255,0),(0,200,255),(255,100,0),(200,0,255)]
        for i, b in enumerate(bboxes):
            c = colors[i%len(colors)]
            cv2.rectangle(clean, (b['x'],b['y']), (b['x']+b['width'],b['y']+b['height']), c, 3)
        cv2.imwrite(f'/tmp/stain_verify_{s}.jpg', clean)

doc.close()
