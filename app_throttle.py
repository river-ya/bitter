from flask import Flask, abort, request, jsonify
from flask_cors import CORS
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
import numpy as np
import cv2
import base64
import dlib
from PIL import Image, ImageDraw, ImageFont
import io
import time
from gevent import monkey
from gevent.pywsgi import WSGIServer

# 异步补丁（必须放在最前面）
monkey.patch_all()

# 创建 Flask 应用实例并启用 CORS，允许所有来源访问所有路由
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# ========== 1. 节流配置 ==========
# 限制单IP每秒最多1次请求（可根据服务器性能调整）
limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["1 per second"],  # 核心节流规则
    storage_uri="memory://"  # 内存存储（轻量场景）
)

# ========== 2. 预加载资源（复用+延迟初始化） ==========
# 懒加载人脸检测器（首次请求时加载，避免启动耗时）
_detector = None
_predictor = None
FONT_PATH = "font_family/方正喵呜体.ttf"
FONT_BYTES = None
OVERLAY_IMG = None

def init_resources():
    """延迟初始化资源，避免启动阻塞"""
    global _detector, _predictor, FONT_BYTES, OVERLAY_IMG
    if _detector is None:
        _detector = dlib.get_frontal_face_detector()
    if _predictor is None:
        _predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")
    if FONT_BYTES is None:
        try:
            with open(FONT_PATH, "rb") as f:
                FONT_BYTES = f.read()
        except Exception:
            FONT_BYTES = None
    if OVERLAY_IMG is None:
        try:
            OVERLAY_IMG = Image.open("images/sweat.png").convert("RGBA")
        except Exception:
            OVERLAY_IMG = None

# ========== 3. 工具函数（优化计算） ==========
def base64_to_image(base64_str):
    try:
        # 优化：跳过base64前缀（如果有）
        if "," in base64_str:
            base64_str = base64_str.split(",")[1]
        img_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print("Error converting base64 to image:", str(e))
        return None

def image_to_base64(image):
    try:
        # 优化：降低JPEG质量（平衡速度和画质）
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 80])
        base64_str = base64.b64encode(buffer).decode("utf-8")
        return base64_str
    except Exception as e:
        print("Error converting image to base64:", str(e))
        return None

def apply_basic_filter_op(image, filter_name, value):
    """优化：提前返回（value=0时直接返回原图）"""
    try:
        v = max(0.0, min(float(value), 100.0))
        if v <= 0:  # 无效果时直接返回，避免计算
            return image

        if filter_name == "grayscale":
            alpha = v / 100.0
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            return cv2.addWeighted(image, 1 - alpha, gray, alpha, 0)

        if filter_name == "sepia":
            sepia_kernel = np.array(
                [
                    [0.272, 0.534, 0.131],
                    [0.349, 0.686, 0.168],
                    [0.393, 0.769, 0.189],
                ]
            )
            sepia = cv2.transform(image, sepia_kernel)
            sepia = np.clip(sepia, 0, 255).astype(np.uint8)
            alpha = v / 100.0
            return cv2.addWeighted(image, 1 - alpha, sepia, alpha, 0)

        if filter_name == "brightness":
            alpha = 1.0 + (v / 100.0)
            return cv2.convertScaleAbs(image, alpha=alpha, beta=0)

        if filter_name == "contrast":
            alpha = 1.0 + (v / 100.0)
            return cv2.convertScaleAbs(image, alpha=alpha, beta=0)

        return image
    except Exception as e:
        print("Error in apply_basic_filter_op:", str(e))
        return None

def get_boundary(points):
    x = points[:, 0]
    y = points[:, 1]
    left = np.min(x)
    right = np.max(x)
    top = np.min(y)
    bottom = np.max(y)
    return left - 1, right + 1, top - 1, bottom + 1

# ========== 4. 苦瓜脸特效（优化计算逻辑） ==========
def apply_bitter_face(img, style, intensity=1.0):
    if not style or str(style).strip() == "":
        return img
    
    # 优化1：图像下采样（降低计算量，不影响视觉效果）
    h, w = img.shape[:2]
    scale = 0.8  # 缩放到80%尺寸处理
    if h > 1080 or w > 1080:  # 仅对大图下采样
        scale = 0.6
    small_h, small_w = int(h * scale), int(w * scale)
    small_img = cv2.resize(img, (small_w, small_h), interpolation=cv2.INTER_AREA)
    
    gray = cv2.cvtColor(small_img, cv2.COLOR_BGR2GRAY)
    denoise = cv2.GaussianBlur(gray, (5, 5), 0)
    
    # 优化2：复用预加载的检测器
    faces = _detector(denoise)
    if len(faces) == 0:
        print("No face detected!")
        return img  # 不抛异常，直接返回原图
    
    # 应用特效到所有人脸
    for face in faces:
        landmarks = _predictor(gray, face)
        points = np.array([[p.x, p.y] for p in landmarks.parts()]) / scale  # 还原坐标
        
        if style == "style1":
            img = apply_style1(img, points, intensity)
        elif style == "style2":
            img = apply_style2(img, points, intensity)
        elif style == "style3":
            img = apply_style3(img, points, intensity)
    
    return img

def apply_style1(img, points, intensity):
    left, right, top, bottom = get_boundary(points)
    h_img, w_img = img.shape[:2]
    face_w = right - left
    pad = max(10, int(0.12 * face_w))
    left = max(0, int(left - pad))
    right = min(w_img, int(right + pad))
    top = max(0, int(top - pad))
    bottom = min(h_img, int(bottom + pad))
    if right - left <= 1 or bottom - top <= 1:
        return img

    roi = img[top:bottom, left:right].copy()
    points_local = points - np.array([left, top])

    left_eye = points_local[36:42]
    right_eye = points_local[42:48]
    nose = points_local[27:36]

    max_dist = int((right - left) / 2)
    rh, rw = roi.shape[:2]
    grid_y, grid_x = np.mgrid[0:rh, 0:rw]

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
    x0, y0, bw, bh = cv2.boundingRect(nose.astype(np.int32))
    c_x, c_y = x0 + bw // 2, y0 + bh // 2
    dist = np.sqrt((grid_x - c_x) ** 2 + (grid_y - c_y) ** 2)
    mask = (dist < max_dist) & (grid_y > c_y) & (grid_x > 0) & (grid_x < rw)
    grid_y[mask] = grid_y[mask] - np.abs(
        intensity * (grid_y[mask] - c_y) * (max_dist - dist[mask]) / max_dist
    )
    mask_nose_l = mask & (grid_x < c_x)
    grid_x[mask_nose_l] = grid_x[mask_nose_l] + np.abs(
        intensity
        * (1 + (max_dist - dist[mask_nose_l]) / max_dist)
        * (grid_x[mask_nose_l] - 0)
        / max(1, (c_x - 0))
    )
    mask_nose_r = mask & (grid_x > c_x)
    grid_x[mask_nose_r] = grid_x[mask_nose_r] - np.abs(
        intensity
        * (1 + (max_dist - dist[mask_nose_r]) / max_dist)
        * (rw - grid_x[mask_nose_r])
        / max(1, (rw - c_x))
    )

    grid_x = np.clip(grid_x, 0, rw - 1)
    grid_y = np.clip(grid_y, 0, rh - 1)
    remapped = cv2.remap(
        roi, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
    )
    img[top:bottom, left:right] = remapped
    return img

def apply_style2(img, points, intensity):
    left_eye = points[36:42]
    right_eye = points[42:48]
    nose = points[27:36]
    mouth = points[48:60]
    l_x , l_y = left_eye[0]
    r_x , r_y = right_eye[3]
    k = (r_y - l_y) / (r_x - l_x + 1e-6)
    angle = -np.degrees(np.arctan(k))

    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left)/2)
    h_img, w_img = img.shape[:2]
    face_w = right - left
    pad = max(10, int(0.12 * face_w))
    left = max(0, int(left - pad))
    right = min(w_img, int(right + pad))
    top = max(0, int(top - pad))
    bottom = min(h_img, int(bottom + pad))
    if right - left <= 1 or bottom - top <= 1:
        return img

    roi = img[top:bottom, left:right].copy()
    points_local = points - np.array([left, top])
    rh, rw = roi.shape[:2]
    grid_y, grid_x = np.mgrid[0:rh, 0:rw]

    # 鼻子横向拉伸
    nose_local = points_local[27:36]
    nose_center_x_local = np.mean(nose_local[:, 0])
    nose_center_y_local = np.mean(nose_local[:, 1])
    nose_radius = int(max_dist * 0.4)
    dist_nose = np.sqrt((grid_x - nose_center_x_local) ** 2 + (grid_y - nose_center_y_local) ** 2)
    mask_nose = dist_nose < nose_radius

    left_mask = mask_nose & (grid_x < nose_center_x_local)
    right_mask = mask_nose & (grid_x >= nose_center_x_local)
    stretch_factor = (nose_radius - dist_nose) / max(1, nose_radius)

    grid_x[left_mask] = grid_x[left_mask] + intensity * (nose_center_x_local - grid_x[left_mask]) * stretch_factor[left_mask]
    grid_x[right_mask] = grid_x[right_mask] - intensity * (grid_x[right_mask] - nose_center_x_local) * stretch_factor[right_mask]

    # 嘴巴拉伸
    mouth_local = points_local[48:60]
    mouth_center_x_local = np.mean(mouth_local[:, 0])
    mouth_center_y_local = np.mean(mouth_local[:, 1])
    mouth_radius = int(max_dist * 0.8)
    dist_mouth = np.sqrt((grid_x - mouth_center_x_local) ** 2 + (grid_y - mouth_center_y_local) ** 2)
    mask_mouth = dist_mouth < mouth_radius

    mouth_left = mask_mouth & (grid_x < mouth_center_x_local)
    mouth_right = mask_mouth & (grid_x >= mouth_center_x_local)
    mouth_stretch = (mouth_radius - dist_mouth) / max(1, mouth_radius)

    grid_x[mouth_left] = grid_x[mouth_left] + intensity * 1.0 * (mouth_center_x_local - grid_x[mouth_left]) * mouth_stretch[mouth_left]
    grid_x[mouth_right] = grid_x[mouth_right] - intensity * 1.0 * (grid_x[mouth_right] - mouth_center_x_local) * mouth_stretch[mouth_right]

    mouth_top = mask_mouth & (grid_y < mouth_center_y_local)
    mouth_bottom = mask_mouth & (grid_y >= mouth_center_y_local)
    vertical_intensity = intensity * 0.7
    grid_y[mouth_top] = grid_y[mouth_top] + vertical_intensity * (mouth_center_y_local - grid_y[mouth_top]) * mouth_stretch[mouth_top]
    grid_y[mouth_bottom] = grid_y[mouth_bottom] - vertical_intensity * (grid_y[mouth_bottom] - mouth_center_y_local) * mouth_stretch[mouth_bottom]

    remapped = cv2.remap(
        roi, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )
    img[top:bottom, left:right] = remapped

    # 文字和叠加层（优化：跳过无资源时的计算）
    if FONT_BYTES is None or OVERLAY_IMG is None:
        return img
    
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw_full = ImageDraw.Draw(pil_img)
    text = "真的会谢!!"
    face_width = right - left
    font_size = max(10, int(face_width * 0.2))
    
    try:
        font = ImageFont.truetype(io.BytesIO(FONT_BYTES), font_size)
    except Exception:
        font = ImageFont.load_default()

    bbox = draw_full.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    face_center_x = (left + right) / 2
    y = max(0, int(top - text_height - 0.37 * (bottom - top)))
    x = int(face_center_x - text_width / 2)

    text_image = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
    draw_text = ImageDraw.Draw(text_image)
    draw_text.text((0,0), text, fill=(124, 141, 89), font=font, align='center', stroke_width=3, stroke_fill='black')
    rotated_text_image = text_image.rotate(angle, expand=True)
    pil_img.paste(rotated_text_image,(int(x), int(y)), rotated_text_image)

    overlay_img = OVERLAY_IMG.copy()
    overlay_img = overlay_img.resize((int(face_width * 0.15), int((bottom - top) * 0.15))).rotate(angle, expand=True)
    width = overlay_img.size[0]
    ox = int(x + text_width - width)
    oy = int(y + text_height * 1.4)
    pil_img.paste(overlay_img, (ox, oy), overlay_img)

    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)
    return img

def d(x, y, k, b):
    dist = np.abs(k * x - y + b)
    while max(dist) > 3:
        dist /= 2
    return dist

def apply_style3(img, points, intensity):
    left_brow = points[17:22]
    right_brow = points[22:27]
    mouth = points[48:60]

    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left) / 7 * 2)
    h_img, w_img = img.shape[:2]
    face_w = right - left
    pad = max(10, int(0.12 * face_w))
    left = max(0, int(left - pad))
    right = min(w_img, int(right + pad))
    top = max(0, int(top - pad))
    bottom = min(h_img, int(bottom + pad))
    if right - left <= 1 or bottom - top <= 1:
        return img

    roi = img[top:bottom, left:right].copy()
    points_local = points - np.array([left, top])
    mouth_local = points_local[48:60]
    left_brow_local = points_local[17:22]
    right_brow_local = points_local[22:27]

    max_dist = int((right - left) / 7 * 2)
    rh, rw = roi.shape[:2]
    grid_y, grid_x = np.mgrid[0:rh, 0:rw]

    # 左眼上挑
    x, y = left_brow_local[3]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_browl = (dist < max_dist) & (grid_x > x)
    grid_y[mask_browl] = grid_y[mask_browl] + np.abs(
        intensity * (grid_x[mask_browl] - x) * (max_dist - dist[mask_browl]) / max_dist
    )

    # 右眼上挑
    x, y = right_brow_local[1]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_browr = (dist < max_dist) & (grid_x < x)
    grid_y[mask_browr] = grid_y[mask_browr] + np.abs(
        intensity * (grid_x[mask_browr] - x) * (max_dist - dist[mask_browr]) / max_dist
    )

    # 嘴部两端纵向拉伸
    xl, yl = mouth_local[0]
    xr, yr = mouth_local[6]
    max_dist_m = int(np.sqrt((yr - yl) ** 2 + (xr - xl) ** 2) // 3)
    delta = max_dist_m / 2 if max_dist_m > 0 else 0

    k = (yr - yl) / (xr - xl + 1e-6)
    b = yl - k * xl

    xl += delta
    yl += delta * k
    dist = np.sqrt((grid_x - xl) ** 2 + (grid_y - yl) ** 2)
    mask_mouthl = dist < max_dist_m
    grid_y[mask_mouthl] = grid_y[mask_mouthl] - (
        intensity
        * (max_dist_m - dist[mask_mouthl])
        / max(1, max_dist_m)
        * (grid_y[mask_mouthl] - yl)
        * d(grid_x[mask_mouthl], grid_y[mask_mouthl], k, b)
    )

    xr -= delta
    yr -= delta * k
    dist = np.sqrt((grid_x - xr) ** 2 + (grid_y - yr) ** 2)
    mask_mouthr = dist < max_dist_m
    grid_y[mask_mouthr] = grid_y[mask_mouthr] - (
        intensity
        * (max_dist_m - dist[mask_mouthr])
        / max(1, max_dist_m)
        * (grid_y[mask_mouthr] - yr)
        * d(grid_x[mask_mouthr], grid_y[mask_mouthr], k, b)
    )

    remapped = cv2.remap(
        roi, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )
    img[top:bottom, left:right] = remapped
    return img

def apply_filter_combo_op(image, bitter_style, filter_values, intensity=1.0):
    if image is None:
        return None
    # 优化：提前初始化资源
    init_resources()
    if bitter_style and str(bitter_style).strip():
        image = apply_bitter_face(image, bitter_style, intensity)
        if image is None:
            return None
    # 优化：过滤无效果的滤镜
    order = ["grayscale", "sepia", "brightness", "contrast"]
    for name in order:
        value = filter_values.get(name, 0) or 0
        if float(value) > 0:
            image = apply_basic_filter_op(image, name, value)
            if image is None:
                return None
    return image

# ========== 5. 路由（增加节流装饰器） ==========
@app.route("/", methods=["GET"])
def home():
    return "Server is running (optimized with throttling)"

@app.route("/test", methods=["GET"])
def test():
    return "Test OK (throttling enabled)"

@app.route("/apply_filter", methods=["POST"])
@limiter.limit("1 per second")  # 单独节流规则（覆盖全局）
def apply_filter():
    try:
        data = request.json
        if not data or "image" not in data or "style" not in data:
            return jsonify({"error": "Missing required parameters"}), 400

        image_b64 = data["image"]
        bitter_style = data["style"]
        intensity = float(data.get("intensity", 1.0))

        image = base64_to_image(image_b64)
        if image is None:
            return jsonify({"error": "Invalid image data"}), 400

        result = apply_filter_combo_op(image, bitter_style, {}, intensity)
        if result is None:
            return jsonify({"error": "Failed to process image"}), 500

        result_b64 = image_to_base64(result)
        if result_b64 is None:
            return jsonify({"error": "Failed to process image"}), 500
        return jsonify({"image": result_b64})

    except Exception as e:
        print("错误:", str(e))
        return jsonify({"error": str(e)}), 500

@app.route("/apply_filter_combo", methods=["POST"])
@limiter.limit("1 per second")  # 核心接口节流
def apply_filter_combo_route():
    try:
        data = request.json or {}
        image_b64 = data.get("image")
        bitter_style = data.get("bitter_style") or ""
        filter_values = data.get("filter_values") or {}
        intensity = float(data.get("intensity", 1.0))

        if not image_b64:
            return jsonify({"error": "Missing image"}), 400

        image = base64_to_image(image_b64)
        if image is None:
            return jsonify({"error": "Invalid image data"}), 400

        result = apply_filter_combo_op(image, bitter_style, filter_values, intensity)
        if result is None:
            return jsonify({"error": "Failed to process image"}), 500

        result_b64 = image_to_base64(result)
        if result_b64 is None:
            return jsonify({"error": "Failed to encode image"}), 500

        return jsonify({"image": result_b64})
    except Exception as e:
        print("错误:", str(e))
        return jsonify({"error": str(e)}), 500

# ========== 6. 启动异步服务器（替代默认同步服务器） ==========
if __name__ == "__main__":
    # 替换默认Flask服务器为gevent异步服务器
    http_server = WSGIServer(("0.0.0.0", 5000), app)
    print("Server running with throttling (gevent) on http://0.0.0.0:5000")
    try:
        http_server.serve_forever()
    except KeyboardInterrupt:
        http_server.stop()