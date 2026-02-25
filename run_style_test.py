import cv2
import numpy as np
import app
from bench_compare import generate_face_image, generate_landmarks

img, _ = generate_face_image()
landmarks = generate_landmarks(img.shape[0])

res1 = app.apply_style1(img.copy(), landmarks.copy(), 1.0)
res2 = app.apply_style2(img.copy(), landmarks.copy(), 1.0)
res3 = app.apply_style3(img.copy(), landmarks.copy(), 1.0)

cv2.imwrite('test_images/out_style1.jpg', res1)
cv2.imwrite('test_images/out_style2.jpg', res2)
cv2.imwrite('test_images/out_style3.jpg', res3)
print('Saved outputs to test_images/')
