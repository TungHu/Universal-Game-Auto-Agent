"""Test offline: match tung template tren chinh anh nguon cua no."""
import cv2
import numpy as np
from PIL import Image
from core.ai_vision import AIVision

CASES = [
    ("1x", "1.jpg"),
    ("2x", "2.jpg"),
    ("3x", "3.jpg"),
    ("4x", "4.jpg"),
    ("5x", "5.jpg"),
    ("6x", "6.jpg"),
    ("7x", "7.jpg"),
]

ok = 0
for name, img_file in CASES:
    img = cv2.cvtColor(np.array(Image.open(f"input_picture/{img_file}").convert("RGB")),
                       cv2.COLOR_RGB2GRAY)
    tmpl = cv2.cvtColor(np.array(Image.open(f"input_picture/{name}.png").convert("RGB")),
                        cv2.COLOR_RGB2GRAY)
    score, x, y, w, h = AIVision._match_template_best(img, tmpl)
    cx, cy = x + w // 2, y + h // 2
    status = "OK" if score >= 0.9 else "WEAK"
    if score >= 0.9:
        ok += 1
    print(f"{status:5} {name:20} score={score:.3f} center=({cx},{cy})")

print(f"\n{ok}/{len(CASES)} template match >= 0.9 tren anh nguon")
