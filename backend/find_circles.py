"""Find all red circle locations in the color variation image (p5 img2)."""
import cv2, numpy as np

# Load original with red circles
orig = cv2.imread('/tmp/p5_img2.png')
orig_h, orig_w = orig.shape[:2]
print(f'Original: {orig_w}x{orig_h}')

# Detect red
hsv = cv2.cvtColor(orig, cv2.COLOR_BGR2HSV)
rgb = cv2.cvtColor(orig, cv2.COLOR_BGR2RGB)
r,g,b = rgb[:,:,0].astype(int), rgb[:,:,1].astype(int), rgb[:,:,2].astype(int)
m1 = cv2.inRange(hsv, np.array([0,80,80]), np.array([10,255,255]))
m2 = cv2.inRange(hsv, np.array([160,80,80]), np.array([180,255,255]))
m3 = ((r>130)&(r>g+50)&(r>b+50)).astype(np.uint8)*255
mask = m1|m2|m3

# Use connected components to find each red circle separately
kernel = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,(5,5))
closed = cv2.morphologyEx(mask, cv2.MORPH_CLOSE, kernel)
n, labels, stats, centroids = cv2.connectedComponentsWithStats(closed)

print(f'Red components: {n-1}')

# Filter by area - circles should be > 500 pixels
circles = []
for i in range(1, n):
    area = stats[i, cv2.CC_STAT_AREA]
    cx, cy = int(centroids[i][0]), int(centroids[i][1])
    if area > 500:
        circles.append((area, cx, cy))
        print(f'  Circle: center=({cx},{cy}) area={area}')

circles.sort(key=lambda x: x[0], reverse=True)

# Crop transform: 1113x919 -> 4:3
# 1113/919 = 1.21 < 1.33 -> crop height
orig_w, orig_h = 1113, 919
new_h = int(orig_w / (640/480))  # 834
top_crop = (orig_h - new_h) // 2  # 42
sx = 640 / orig_w  # 0.575
sy = 480 / new_h   # 0.575

print(f'\nCrop: top_crop={top_crop}, scale={sx:.3f}')

# Map each circle to 640x480
print('\nMapped bboxes:')
bboxes = []
for area, cx, cy in circles:
    mx = int(cx * sx)
    my = int((cy - top_crop) * sy)
    mx = max(60, min(mx, 580))
    my = max(50, min(my, 430))
    bx = max(0, mx-80)
    by = max(0, my-60)
    bw, bh = 160, 120
    bx = min(bx, 640-bw)
    by = min(by, 480-bh)
    bboxes.append({"x": bx, "y": by, "width": bw, "height": bh})
    print(f'  orig=({cx},{cy}) -> mapped=({mx},{my}) -> bbox=({bx},{by},{bw}x{bh})')

# Draw on clean image
clean = cv2.imread('demo_data/images/scenarios/scenario-30/top.jpg')
colors = [(0,255,0),(0,200,255),(255,100,0),(200,0,255)]
for i, b in enumerate(bboxes):
    c = colors[i % len(colors)]
    cv2.rectangle(clean, (b['x'],b['y']), (b['x']+b['width'],b['y']+b['height']), c, 3)
    cv2.putText(clean, f'C{i+1}', (b['x'],b['y']-5), cv2.FONT_HERSHEY_SIMPLEX, 0.5, c, 2)
cv2.imwrite('/tmp/color_var_verify.jpg', clean)
print('Saved /tmp/color_var_verify.jpg')
