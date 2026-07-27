"""
vision.py - Xử lý ảnh game
Hỗ trợ: OCR (Tesseract), template matching (OpenCV), color detection
"""

import cv2
import numpy as np
from PIL import Image
import json
import os


class GameVision:
    """Nhận diện trạng thái game từ ảnh chụp"""

    def __init__(self, config: dict):
        """
        Args:
            config: dict từ config.json của game
        """
        self.config = config
        self.vision_type = config.get("vision", {}).get("type", "ocr")

    def analyze(self, game_image: Image.Image) -> str:
        """
        Phân tích ảnh game, trả về board state dạng text

        Args:
            game_image: PIL.Image của vùng game

        Returns:
            String biểu diễn board state (ví dụ: "0 2 4 8\n2 4 8 16\n...")
        """
        if self.vision_type == "ocr":
            return self._ocr_analysis(game_image)
        elif self.vision_type == "template":
            return self._template_analysis(game_image)
        elif self.vision_type == "color":
            return self._color_analysis(game_image)
        else:
            raise ValueError(f"Unknown vision type: {self.vision_type}")

    def _ocr_analysis(self, game_image: Image.Image) -> str:
        """Nhận diện board game bằng OCR"""
        try:
            import pytesseract
        except ImportError:
            raise ImportError(
                "pytesseract not installed. Run: pip install pytesseract\n"
                "Also install Tesseract from: https://github.com/UB-Mannheim/tesseract/wiki"
            )

        vision_cfg = self.config.get("vision", {})
        board_size = vision_cfg.get("board_size", [4, 4])
        ocr_config = vision_cfg.get("ocr_config", "--psm 7")

        rows, cols = board_size
        cell_w = game_image.width // cols
        cell_h = game_image.height // rows

        board = []
        for r in range(rows):
            row = []
            for c in range(cols):
                # Crop từng ô
                left = c * cell_w
                top = r * cell_h
                right = left + cell_w
                bottom = top + cell_h
                cell_img = game_image.crop((left, top, right, bottom))

                # OCR từng ô
                text = pytesseract.image_to_string(cell_img, config=ocr_config).strip()
                if text == "" or not text.isdigit():
                    text = "0"
                row.append(text)
            board.append(row)

        # Chuyển thành text board
        lines = []
        for row in board:
            lines.append(" ".join(row))
        return "\n".join(lines)

    def _template_analysis(self, game_image: Image.Image) -> str:
        """Nhận diện board game bằng template matching"""
        vision_cfg = self.config.get("vision", {})
        board_size = vision_cfg.get("board_size", [4, 4])
        templates_dir = vision_cfg.get("templates_dir", "templates")

        # Load templates từ thư mục game
        game_dir = self.config.get("_game_dir", "")
        templates_path = os.path.join(game_dir, templates_dir)

        if not os.path.exists(templates_path):
            raise FileNotFoundError(f"Templates directory not found: {templates_path}")

        # Load tất cả template ảnh
        templates = {}
        for f in os.listdir(templates_path):
            if f.endswith((".png", ".jpg", ".jpeg")):
                name = os.path.splitext(f)[0]
                tmpl = cv2.imread(os.path.join(templates_path, f), cv2.IMREAD_GRAYSCALE)
                if tmpl is not None:
                    templates[name] = tmpl

        # Chuyển game_image sang OpenCV format
        img_cv = cv2.cvtColor(np.array(game_image), cv2.COLOR_RGB2GRAY)

        rows, cols = board_size
        cell_w = game_image.width // cols
        cell_h = game_image.height // rows

        board = []
        for r in range(rows):
            row = []
            for c in range(cols):
                left = c * cell_w
                top = r * cell_h
                cell_img = img_cv[top:top + cell_h, left:left + cell_w]

                # Match với từng template
                best_match = "0"
                best_val = 0
                for name, tmpl in templates.items():
                    if tmpl.shape[0] > cell_h or tmpl.shape[1] > cell_w:
                        continue
                    result = cv2.matchTemplate(cell_img, tmpl, cv2.TM_CCOEFF_NORMED)
                    _, max_val, _, _ = cv2.minMaxLoc(result)
                    if max_val > best_val:
                        best_val = max_val
                        best_match = name

                row.append(best_match)
            board.append(row)

        lines = []
        for row in board:
            lines.append(" ".join(row))
        return "\n".join(lines)

    def _color_analysis(self, game_image: Image.Image) -> str:
        """Nhận diện board game bằng màu sắc"""
        vision_cfg = self.config.get("vision", {})
        board_size = vision_cfg.get("board_size", [4, 4])
        color_map = vision_cfg.get("color_map", {})

        img_array = np.array(game_image)
        rows, cols = board_size
        cell_w = game_image.width // cols
        cell_h = game_image.height // rows

        board = []
        for r in range(rows):
            row = []
            for c in range(cols):
                left = c * cell_w
                top = r * cell_h
                cell = img_array[top:top + cell_h, left:left + cell_w]
                avg_color = cell.mean(axis=(0, 1))  # RGB trung bình

                # Tìm màu gần nhất trong color_map
                best_match = "0"
                best_dist = float("inf")
                for name, rgb in color_map.items():
                    dist = np.linalg.norm(avg_color - np.array(rgb))
                    if dist < best_dist:
                        best_dist = dist
                        best_match = name

                row.append(best_match)
            board.append(row)

        lines = []
        for row in board:
            lines.append(" ".join(row))
        return "\n".join(lines)