from flask import Flask, abort, request, jsonify
from flask_cors import CORS
import numpy as np
import cv2
import base64
import dlib
from PIL import Image, ImageDraw, ImageFont
import io

# 创建 Flask 应用实例并启用 CORS，允许所有来源访问所有路由
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 加载人脸检测器和关键点预测器
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")

# Preload font bytes and overlay image to avoid per-request disk I/O
FONT_PATH = "font_family/方正喵呜体.ttf"
FONT_BYTES = None
OVERLAY_IMG = None
try:
    with open(FONT_PATH, "rb") as f:
        FONT_BYTES = f.read()
except Exception:
    FONT_BYTES = None

try:
    OVERLAY_IMG = Image.open("images/sweat.png").convert("RGBA")
except Exception:
    OVERLAY_IMG = None


def base64_to_image(base64_str):
    try:
        img_data = base64.b64decode(base64_str)
        nparr = np.frombuffer(img_data, np.uint8)
        img = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
        return img
    except Exception as e:
        print("Error converting base64 to image:", str(e))
        return None


def image_to_base64(image):
    try:
        _, buffer = cv2.imencode(".jpg", image, [cv2.IMWRITE_JPEG_QUALITY, 90])
        base64_str = base64.b64encode(buffer).decode("utf-8")
        return base64_str
    except Exception as e:
        print("Error converting image to base64:", str(e))
        return None


def apply_basic_filter_op(image, filter_name, value):
    """
    应用简单的基础滤镜效果：
    - grayscale: 灰度
    - sepia: 复古
    - brightness: 亮度
    - contrast: 对比度
    value 范围建议为 0-100, 对应不同强度
    """
    try:
        v = max(0.0, min(float(value), 100.0))

        if filter_name == "grayscale":
            # CSS: grayscale(0-100%) → OpenCV: 0-1 混合
            alpha = v / 100.0
            gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
            gray = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
            return cv2.addWeighted(image, 1 - alpha, gray, alpha, 0)

        if filter_name == "sepia":
            # 先生成 sepia 效果，再根据强度与原图进行混合
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
            # CSS: brightness(100-200%) → OpenCV: 1.0-2.0 alpha
            alpha = 1.0 + (v / 100.0)
            return cv2.convertScaleAbs(image, alpha=alpha, beta=0)

        if filter_name == "contrast":
            # CSS: contrast(100-200%) → OpenCV: 1.0-2.0 alpha
            alpha = 1.0 + (v / 100.0)
            return cv2.convertScaleAbs(image, alpha=alpha, beta=0)

        # 未知滤镜，直接返回原图
        return image
    except Exception as e:
        print("Error in apply_basic_filter_op:", str(e))
        return None

def apply_bitter_face(img, style, intensity=1.0):
    if not style or str(style).strip() == "":
        return img
    # 保存原图像大小
    h, w = img.shape[:2]
    oh, ow = h, w
    # 不再对小图进行无限放大（放大会显著增加计算量）
    # 若图像过大，可在此处选择下采样，但为保持简单性，保留原始分辨率以避免复杂的坐标映射。
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 降噪
    denoise = cv2.GaussianBlur(gray, (5, 5), 0)
    # 检测人脸
    faces = detector(denoise)
    if len(faces) == 0:
        print("No face detected!")
        abort(500, description="No face detected!")
        return None

    # 应用特效到所有人脸
    for face in faces:
        landmarks = predictor(gray, face)
        points = np.array([[p.x, p.y] for p in landmarks.parts()])

        # 根据不同style应用不同的变形
        if style == "style1":
            # 苦瓜脸样式1：向内挤压脸颊
            img = apply_style1(img, points, intensity)
        elif style == "style2":
            # 苦瓜脸样式2：拉长下巴
            img = apply_style2(img, points, intensity)
        elif style == "style3":
            # 苦瓜脸样式3：扁平化
            img = apply_style3(img, points, intensity)
    # 恢复原图像大小
    img = cv2.resize(img, (ow, oh), interpolation=cv2.INTER_LINEAR)
    return img

def apply_filter_combo_op(image, bitter_style, filter_values, intensity=1.0):
    """
    按顺序应用：先苦瓜脸（若有），再依次应用 grayscale / sepia / brightness / contrast（value>0 时）。
    filter_values: dict, 键为 grayscale, sepia, brightness, contrast，值为 0-100。
    intensity: 苦瓜脸变形强度，默认为 1.0。
    """
    if image is None:
        return None
    if bitter_style and str(bitter_style).strip():
        image = apply_bitter_face(image, bitter_style, intensity)
        if image is None:
            return None
    order = ["grayscale", "sepia", "brightness", "contrast"]
    for name in order:
        value = filter_values.get(name, 0) or 0
        if float(value) > 0:
            image = apply_basic_filter_op(image, name, value)
            if image is None:
                return None
    return image

def get_boundary(points):
    x = points[:, 0]
    y = points[:, 1]
    left = np.min(x)
    right = np.max(x)
    top = np.min(y)
    bottom = np.max(y)
    return left - 1, right + 1, top - 1, bottom + 1


def apply_style1(img, points, intensity):
    # 局部 ROI remap：仅在脸部 bounding box 内建立网格并重映射，避免对整图操作
    left, right, top, bottom = get_boundary(points)
    h_img, w_img = img.shape[:2]
    # add small padding to ROI to avoid border artifacts
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

    # 保证映射坐标在 roi 范围内，避免 remap 取样到边界外导致黑色伪影
    grid_x = np.clip(grid_x, 0, rw - 1)
    grid_y = np.clip(grid_y, 0, rh - 1)
    remapped = cv2.remap(
        roi, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR, borderMode=cv2.BORDER_REFLECT
    )
    img[top:bottom, left:right] = remapped
    return img


def apply_style2(img, points, intensity):
    # 获取脸部轮廓点
    left_eye = points[36:42]
    right_eye = points[42:48]
    nose = points[27:36]
    mouth = points[48:60]
    l_x , l_y = left_eye[0]
    r_x , r_y = right_eye[3]
    k = (r_y - l_y) / (r_x - l_x)
    angle = -np.degrees(np.arctan(k))

    # 框整个人脸所在区域
    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left)/2)

    # 计算脸部中心
    face_center_x = (left + right) / 2
    # 局部 ROI remap（仅对脸部区域做 remap）
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
    rh, rw = roi.shape[:2]
    grid_y, grid_x = np.mgrid[0:rh, 0:rw]

    # 扩大嘴巴和鼻子（横向拉伸1.5倍）
    # 鼻子横向拉伸（使用局部坐标）
    nose_local = points_local[27:36]
    nose_center_x_local = np.mean(nose_local[:, 0])
    nose_center_y_local = np.mean(nose_local[:, 1])
    nose_radius = int(max_dist * 0.4)  # 影响半径
    dist_nose = np.sqrt((grid_x - nose_center_x_local) ** 2 + (grid_y - nose_center_y_local) ** 2)
    mask_nose = dist_nose < nose_radius

    # 左右侧分别处理（局部）
    left_mask = mask_nose & (grid_x < nose_center_x_local)
    right_mask = mask_nose & (grid_x >= nose_center_x_local)
    stretch_factor = (nose_radius - dist_nose) / max(1, nose_radius)  # 衰减系数

    grid_x[left_mask] = grid_x[left_mask] + intensity * (nose_center_x_local - grid_x[left_mask]) * stretch_factor[left_mask]
    grid_x[right_mask] = grid_x[right_mask] - intensity * (grid_x[right_mask] - nose_center_x_local) * stretch_factor[right_mask]

    # 嘴巴横向拉伸
    mouth_local = points_local[48:60]
    mouth_center_x_local = np.mean(mouth_local[:, 0])
    mouth_center_y_local = np.mean(mouth_local[:, 1])
    mouth_radius = int(max_dist * 0.8)  # 更大影响范围
    dist_mouth = np.sqrt((grid_x - mouth_center_x_local) ** 2 + (grid_y - mouth_center_y_local) ** 2)
    mask_mouth = dist_mouth < mouth_radius

    # 分离左右处理区域
    mouth_left = mask_mouth & (grid_x < mouth_center_x_local)
    mouth_right = mask_mouth & (grid_x >= mouth_center_x_local)
    mouth_stretch = (mouth_radius - dist_mouth) / max(1, mouth_radius)

    grid_x[mouth_left] = grid_x[mouth_left] + intensity * 1.0 * (mouth_center_x_local - grid_x[mouth_left]) * mouth_stretch[mouth_left]
    grid_x[mouth_right] = grid_x[mouth_right] - intensity * 1.0 * (grid_x[mouth_right] - mouth_center_x_local) * mouth_stretch[mouth_right]

    # 添加纵向拉伸
    # 分离上下处理区域
    mouth_top = mask_mouth & (grid_y < mouth_center_y_local)
    mouth_bottom = mask_mouth & (grid_y >= mouth_center_y_local)

    # 纵向拉伸（上部分向上，下部分向下）
    vertical_intensity = intensity * 0.7  # 可以调整纵向拉伸的强度
    grid_y[mouth_top] = grid_y[mouth_top] + vertical_intensity * (mouth_center_y_local - grid_y[mouth_top]) * mouth_stretch[
        mouth_top]
    grid_y[mouth_bottom] = grid_y[mouth_bottom] - vertical_intensity * (grid_y[mouth_bottom] - mouth_center_y_local) * \
                           mouth_stretch[mouth_bottom]

    # remap ROI and paste back
    remapped = cv2.remap(
        roi, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )
    img[top:bottom, left:right] = remapped

    # 添加文字特效与叠加（在内存中操作，使用预加载资源以避免磁盘 I/O）
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw_full = ImageDraw.Draw(pil_img)
    text = "真的会谢!!"
    face_width = right - left
    face_height = bottom - top
    font_size = max(10, int(face_width * 0.2))
    try:
        if FONT_BYTES:
            font = ImageFont.truetype(io.BytesIO(FONT_BYTES), font_size)
        else:
            font = ImageFont.load_default()
    except Exception:
        font = ImageFont.load_default()

    bbox = draw_full.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    face_center_x = (left + right) / 2
    y = max(0, int(top - text_height - 0.37 * face_height))
    x = int(face_center_x - text_width / 2)

    text_image = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
    draw_text = ImageDraw.Draw(text_image)
    draw_text.text((0,0), text, fill=(124, 141, 89), font=font, align='center', stroke_width=3, stroke_fill='black')
    rotated_text_image = text_image.rotate(angle, expand=True)
    pil_img.paste(rotated_text_image,(int(x), int(y)), rotated_text_image)

    # 叠加部分图片（使用预加载 overlay）
    if OVERLAY_IMG is not None:
        overlay_img = OVERLAY_IMG.copy()
        overlay_img = overlay_img.resize((int(face_width * 0.15), int(face_height * 0.15))).rotate(angle, expand=True)
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
    # 获取脸部轮廓点
    left_brow = points[17:22]
    right_brow = points[22:27]
    mouth = points[48:60]

    # 框整个人脸所在区域
    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left) / 7 * 2)

    # 局部 ROI remap
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


# 两个简单的 GET 路由，便于检查服务是否启动成功。
# “当有人通过 HTTP GET 请求访问服务器的根路径 / 时，执行函数 home()。”

@app.route("/", methods=["GET"])
def home():
    return "Server is running"


@app.route("/test", methods=["GET"])
def test():
    return "Test OK"


@app.route("/apply_filter", methods=["POST"])
def apply_filter():
    """
    应用苦瓜脸特效。
    """
    try:
        print("收到请求...")
        data = request.json
        print("请求数据:", data)

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
def apply_filter_combo_route():
    """
    应用滤镜组合：苦瓜脸（可选）+ 多种普通滤镜。
    请求体：image (base64), bitter_style (''|'style1'|'style2'|'style3'),
           filter_values: { grayscale, sepia, brightness, contrast } 均为 0-100。
    """
    try:
        data = request.json or {}
        image_b64 = data.get("image")
        bitter_style = data.get("bitter_style") or ""
        filter_values = data.get("filter_values") or {}
        intensity = float(data.get("intensity", 1.0))

        if not data:
            return jsonify({"error": "Missing required parameters"}), 400

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


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

