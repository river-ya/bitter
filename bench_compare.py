import time
import cv2
import numpy as np
import base64
import os
import io
import app

# Generate a synthetic face-like image and adjust JPEG quality to ~1MB
def generate_face_image(target_bytes=1_000_000):
    # start with 1024x1024 canvas
    size = 1024
    while True:
        img = np.full((size, size, 3), 255, dtype=np.uint8)
        # draw eyes
        cv2.circle(img, (int(size*0.35), int(size*0.4)), int(size*0.05), (0,0,0), -1)
        cv2.circle(img, (int(size*0.65), int(size*0.4)), int(size*0.05), (0,0,0), -1)
        # nose
        pts = np.array([[int(size*0.5), int(size*0.45)], [int(size*0.47), int(size*0.55)], [int(size*0.53), int(size*0.55)]])
        cv2.drawContours(img, [pts], 0, (20,20,20), -1)
        # mouth
        cv2.ellipse(img, (int(size*0.5), int(size*0.65)), (int(size*0.15), int(size*0.08)), 0, 0, 180, (0,0,0), -1)

        # try encode to jpeg with quality 90
        for q in [95,90,85,80,75,70]:
            ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), q])
            b = buf.tobytes()
            if len(b) >= target_bytes * 0.9 and len(b) <= target_bytes * 1.2:
                return img, b
        # if too small, increase resolution
        size = int(size * 1.2)
        if size > 3000:
            # give up and return current
            ok, buf = cv2.imencode('.jpg', img, [int(cv2.IMWRITE_JPEG_QUALITY), 90])
            return img, buf.tobytes()

# Create synthetic 68-point landmarks roughly positioned on the synthetic face
def generate_landmarks(size):
    w = h = size
    pts = np.zeros((68,2), dtype=np.int32)
    # left eye 36-41
    ex = int(w*0.35)
    ey = int(h*0.4)
    for i in range(36,42):
        pts[i] = [ex + (i-36)*2, ey + ((i%2)*2 - 1)]
    # right eye 42-47
    ex = int(w*0.65)
    for i in range(42,48):
        pts[i] = [ex + (i-42)*2, ey + ((i%2)*2 - 1)]
    # nose 27-35
    nx = int(w*0.5)
    ny = int(h*0.5)
    for i in range(27,36):
        pts[i] = [nx + (i-31), ny + (i-31)//2]
    # mouth 48-59
    mx = int(w*0.5)
    my = int(h*0.65)
    for i in range(48,60):
        pts[i] = [mx + (i-54)*3, my + ((i%2)*2 - 1)]
    # approximate other points to box around face
    left = int(w*0.25); right = int(w*0.75); top = int(h*0.2); bottom = int(h*0.8)
    for i in range(0,17):
        t = i/16
        pts[i] = [int(left + (right-left)*t), top]
    for i in range(17,27):
        pts[i] = [left, top + (i-17)*5]
    return pts

# Helper copied from app.py to compute bounding box
def get_boundary(points):
    x = points[:, 0]
    y = points[:, 1]
    left = np.min(x)
    right = np.max(x)
    top = np.min(y)
    bottom = np.max(y)
    return left - 1, right + 1, top - 1, bottom + 1

# Full-image heavy style1 (simulate original full-image remap cost)
def full_apply_style1(img, points, intensity=1.0):
    # 原始完整实现：对整张图建立网格并基于面部关键点进行多处变形
    left_eye = points[36:42]
    right_eye = points[42:48]
    nose = points[27:36]
    mouth = points[48:60]

    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left) / 2)

    h, w = img.shape[:2]
    grid_y, grid_x = np.mgrid[0:h, 0:w]

    # 左眼下垂
    x, y = left_eye[3]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_eyel = (dist < max_dist) & (grid_x < x)
    grid_y[mask_eyel] = grid_y[mask_eyel] - np.abs(
        intensity * (grid_x[mask_eyel] - x) * (max_dist - dist[mask_eyel]) / max_dist
    )

    # 右眼下垂
    x, y = right_eye[0]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_eyer = (dist < max_dist) & (grid_x > x)
    grid_y[mask_eyer] = grid_y[mask_eyer] - np.abs(
        intensity * (grid_x[mask_eyer] - x) * (max_dist - dist[mask_eyer]) / max_dist
    )

    # 鼻子区域拉伸
    x, y, w_box, h_box = cv2.boundingRect(nose.astype(np.int32))
    c_x, c_y = x + w_box // 2, y + h_box // 2
    dist = np.sqrt((grid_x - c_x) ** 2 + (grid_y - c_y) ** 2)
    mask = (dist < max_dist) & (grid_y > c_y) & (grid_x > left) & (grid_x < right)
    grid_y[mask] = grid_y[mask] - np.abs(
        intensity * (grid_y[mask] - c_y) * (max_dist - dist[mask]) / max_dist
    )
    mask_nose_l = mask & (grid_x < c_x)
    grid_x[mask_nose_l] = grid_x[mask_nose_l] + np.abs(
        intensity
        * (1 + (max_dist - dist[mask_nose_l]) / max_dist)
        * (grid_x[mask_nose_l] - left)
        / (c_x - left)
    )
    mask_nose_r = mask & (grid_x > c_x)
    grid_x[mask_nose_r] = grid_x[mask_nose_r] - np.abs(
        intensity
        * (1 + (max_dist - dist[mask_nose_r]) / max_dist)
        * (right - grid_x[mask_nose_r])
        / (right - c_x)
    )

    remapped = cv2.remap(
        img, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )
    return remapped

# Use app.apply_style1 (modified ROI) as roi version

if __name__ == '__main__':
    print('Generating test image (~1MB) ...')
    img, jpg_bytes = generate_face_image()
    size_bytes = len(jpg_bytes)
    print('Generated JPEG size (bytes):', size_bytes)

    # save for inspection
    with open('test_images/benchmark_face.jpg', 'wb') as f:
        f.write(jpg_bytes)

    landmarks = generate_landmarks(img.shape[0])

    # warmup
    print('Warming up...')
    _ = app.apply_style1(img.copy(), landmarks.copy(), 1.0)
    _ = full_apply_style1(img.copy(), landmarks.copy(), 1.0)

    runs = 5
    t_roi = []
    t_full = []
    for i in range(runs):
        t0 = time.perf_counter()
        _ = app.apply_style1(img.copy(), landmarks.copy(), 1.0)
        t1 = time.perf_counter()
        t_roi.append(t1-t0)

        t0 = time.perf_counter()
        _ = full_apply_style1(img.copy(), landmarks.copy(), 1.0)
        t1 = time.perf_counter()
        t_full.append(t1-t0)

    print('\nResults over {} runs:'.format(runs))
    print('ROI remap times (s):', ['{:.3f}'.format(x) for x in t_roi])
    print('Full-image remap times (s):', ['{:.3f}'.format(x) for x in t_full])
    print('ROI avg: {:.3f}s'.format(np.mean(t_roi)))
    print('Full avg: {:.3f}s'.format(np.mean(t_full)))
    print('Speedup (full/roi): {:.2f}x'.format(np.mean(t_full)/max(np.mean(t_roi), 1e-9)))
