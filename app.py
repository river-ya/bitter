from flask import Flask, request, jsonify
from flask_cors import CORS
import numpy as np
import cv2
import base64
import dlib
from PIL import Image, ImageDraw, ImageFont

# 创建 Flask 应用实例并启用 CORS，允许所有来源访问所有路由
app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# 加载人脸检测器和关键点预测器
detector = dlib.get_frontal_face_detector()
predictor = dlib.shape_predictor("shape_predictor_68_face_landmarks.dat")


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


def apply_bitter_face(img, style, intensity=1.0):
    # 保存原图像大小
    h, w = img.shape[:2]
    oh, ow = h, w
    # 缩放图像
    while w < 300 and w != 0:
        w *= 2
        h *= 2
    img = cv2.resize(img, (w, h), interpolation=cv2.INTER_LINEAR)
    # 转换为灰度图
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # 降噪
    denoise = cv2.GaussianBlur(gray, (5, 5), 0)
    # 检测人脸
    faces = detector(denoise)
    if len(faces) == 0:
        print("No face detected!")
        return img

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


def get_boundary(points):
    x = points[:, 0]
    y = points[:, 1]
    left = np.min(x)
    right = np.max(x)
    top = np.min(y)
    bottom = np.max(y)
    return left - 1, right + 1, top - 1, bottom + 1


def apply_style1(img, points, intensity):
    # 获取脸部轮廓点
    left_eye = points[36:42]
    right_eye = points[42:48]
    nose = points[27:36]
    mouth = points[48:60]

    # 框整个人脸所在区域
    left, right, top, bottom = get_boundary(points)
    max_dist = int((right - left) / 2)

    # 创建变形网格
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
    x, y, w, h = cv2.boundingRect(nose)
    c_x, c_y = x + w // 2, y + h // 2
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

    return cv2.remap(
        img, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )


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
    # 创建变形网格
    h, w = img.shape[:2]    #获取图像的高度 h 和宽度 w ，使用 np.mgrid 创建一个二维网格，用于后续的图像变形操作。
    grid_y, grid_x = np.mgrid[0:h, 0:w]

    # 扩大嘴巴和鼻子（横向拉伸1.5倍）
    # 鼻子横向拉伸
    nose_center_x = np.mean(nose[:, 0])
    nose_center_y = np.mean(nose[:, 1])
    nose_radius = int(max_dist * 0.4)  # 影响半径
    dist_nose = np.sqrt((grid_x - nose_center_x) ** 2 + (grid_y - nose_center_y) ** 2)
    mask_nose = dist_nose < nose_radius

    # 左右侧分别处理
    left_mask = mask_nose & (grid_x < nose_center_x)
    right_mask = mask_nose & (grid_x >= nose_center_x)
    stretch_factor = (nose_radius - dist_nose) / nose_radius  # 衰减系数

    grid_x[left_mask] = grid_x[left_mask] + intensity * (nose_center_x - grid_x[left_mask]) * stretch_factor[left_mask]
    grid_x[right_mask] = grid_x[right_mask] - intensity * (grid_x[right_mask] - nose_center_x) * stretch_factor[right_mask]

    # 嘴巴横向拉伸
    mouth_center_x = np.mean(mouth[:, 0])
    mouth_center_y = np.mean(mouth[:, 1])
    mouth_radius = int(max_dist * 0.8)  # 更大影响范围
    dist_mouth = np.sqrt((grid_x - mouth_center_x) ** 2 + (grid_y - mouth_center_y) ** 2)
    mask_mouth = dist_mouth < mouth_radius

    # 分离左右处理区域
    mouth_left = mask_mouth & (grid_x < mouth_center_x)
    mouth_right = mask_mouth & (grid_x >= mouth_center_x)
    mouth_stretch = (mouth_radius - dist_mouth) / mouth_radius

    grid_x[mouth_left] = grid_x[mouth_left] + intensity * 1.0 * (mouth_center_x - grid_x[mouth_left]) * mouth_stretch[mouth_left]
    grid_x[mouth_right] = grid_x[mouth_right] - intensity * 1.0 * (grid_x[mouth_right] - mouth_center_x) * mouth_stretch[mouth_right]

    # 添加纵向拉伸
    # 分离上下处理区域
    mouth_top = mask_mouth & (grid_y < mouth_center_y)
    mouth_bottom = mask_mouth & (grid_y >= mouth_center_y)

    # 纵向拉伸（上部分向上，下部分向下）
    vertical_intensity = intensity * 0.7  # 可以调整纵向拉伸的强度
    grid_y[mouth_top] = grid_y[mouth_top] + vertical_intensity * (mouth_center_y - grid_y[mouth_top]) * mouth_stretch[
        mouth_top]
    grid_y[mouth_bottom] = grid_y[mouth_bottom] - vertical_intensity * (grid_y[mouth_bottom] - mouth_center_y) * \
                           mouth_stretch[mouth_bottom]

    # 添加文字特效
    pil_img = Image.fromarray(cv2.cvtColor(img, cv2.COLOR_BGR2RGB))
    draw = ImageDraw.Draw(pil_img)

    # 根据人脸宽度动态调整字体大小
    font_path = "font_family/方正喵呜体.ttf"
    face_width = right - left
    font_size = int(face_width * 0.2)  # 这里的 0.2 是一个比例系数，可以根据实际情况调整
    font = ImageFont.truetype(font_path, font_size)

    text = "真的会谢!!"
    bbox = draw.textbbox((0, 0), text, font=font)
    text_width = bbox[2] - bbox[0]
    text_height = bbox[3] - bbox[1]
    face_center_x = (left + right) / 2
    face_center_y = (top + bottom) / 2
    face_width = right - left
    face_height = bottom - top
    y = top - text_height - 0.37 * face_height
    x = face_center_x - text_width / 2 + k * (face_center_y - y)
    
    text_image = Image.new('RGBA', (text_width, text_height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(text_image)
    draw.text((0,0), text, fill=(124, 141, 89), font=font, align='center', stroke_width=3, stroke_fill='black')
    rotated_text_image = text_image.rotate(angle, expand=True)
    pil_img.paste(rotated_text_image,(int(x), int(y)), rotated_text_image)

    # 叠加部分图片
    overlay_img = Image.open("images/sweat.png").convert("RGBA")
    overlay_img = overlay_img.resize((int(face_width * 0.15), int(face_height * 0.15))).rotate(angle,expand=True)
    width = overlay_img.size[0]
    x = x + text_width - width
    y = y + text_height * 1.4
    pil_img.paste(overlay_img, (int(x), int(y)), overlay_img)

    img = cv2.cvtColor(np.array(pil_img), cv2.COLOR_RGB2BGR)

    return cv2.remap(
        img, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )


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

    # 创建变形网格
    h, w = img.shape[:2]
    grid_y, grid_x = np.mgrid[0:h, 0:w]

    # 左眼上挑
    x, y = left_brow[3]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_browl = (dist < max_dist) & (grid_x > x)
    grid_y[mask_browl] = grid_y[mask_browl] + np.abs(
        intensity * (grid_x[mask_browl] - x) * (max_dist - dist[mask_browl]) / max_dist
    )

    # 右眼上挑
    x, y = right_brow[1]
    dist = np.sqrt((grid_x - x) ** 2 + (grid_y - y) ** 2)
    mask_browr = (dist < max_dist) & (grid_x < x)
    grid_y[mask_browr] = grid_y[mask_browr] + np.abs(
        intensity * (grid_x[mask_browr] - x) * (max_dist - dist[mask_browr]) / max_dist
    )

    # 嘴部两端纵向拉伸
    xl, yl = mouth[0]
    xr, yr = mouth[6]
    max_dist = np.sqrt((yr - yl) ** 2 + (xr - xl) ** 2) // 3
    delta = max_dist / 2

    k = (yr - yl) / (xr - xl)
    b = yl - k * xl

    xl += delta
    yl += delta * k
    dist = np.sqrt((grid_x - xl) ** 2 + (grid_y - yl) ** 2)
    mask_mouthl = dist < max_dist
    grid_y[mask_mouthl] = grid_y[mask_mouthl] - (
        intensity
        * (max_dist - dist[mask_mouthl])
        / max_dist
        * (grid_y[mask_mouthl] - yl)
        * d(grid_x[mask_mouthl], grid_y[mask_mouthl], k, b)
    )

    xr -= delta
    yr -= delta * k
    dist = np.sqrt((grid_x - xr) ** 2 + (grid_y - yr) ** 2)
    mask_mouthr = dist < max_dist
    grid_y[mask_mouthr] = grid_y[mask_mouthr] - (
        intensity
        * (max_dist - dist[mask_mouthr])
        / max_dist
        * (grid_y[mask_mouthr] - yr)
        * d(grid_x[mask_mouthr], grid_y[mask_mouthr], k, b)
    )

    return cv2.remap(
        img, grid_x.astype(np.float32), grid_y.astype(np.float32), cv2.INTER_LINEAR
    )


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
    try:
        print("收到请求...")  # 添加日志
        data = request.json
        print("请求数据:", data)  # 添加日志

        if not data or "image" not in data or "style" not in data:
            return jsonify({"error": "Missing required parameters"}), 400

        image_b64 = data["image"]
        style = data["style"]
        intensity = float(data.get("intensity", 1.0))

        # 转换base64图片为OpenCV格式
        image = base64_to_image(image_b64)
        if image is None:
            return jsonify({"error": "Invalid image data"}), 400

        # 应用苦瓜脸特效
        result = apply_bitter_face(image, style, intensity)

        # 转换回base64
        result_b64 = image_to_base64(result)
        if result_b64 is None:
            return jsonify({"error": "Failed to process image"}), 500

        return jsonify({"image": result_b64})

    except Exception as e:
        print("错误:", str(e))  # 添加日志
        return jsonify({"error": str(e)}), 500


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)

