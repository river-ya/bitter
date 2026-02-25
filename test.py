import cv2
import numpy as np
import app


img = cv2.imread('test_images/7.png')

res = app.apply_bitter_face(img, "style1", intensity=1.0)

cv2.imwrite('test_images/test.jpg', res)