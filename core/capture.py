"""
capture.py - Chụp màn hình game
Sử dụng mss để chụp nhanh, hỗ trợ đa màn hình
"""

import mss
import numpy as np
from PIL import Image


class ScreenCapture:
    """Chụp màn hình với mss"""

    def __init__(self):
        self.sct = mss.mss()

    def capture_region(self, region: dict) -> Image.Image:
        """
        Chụp một vùng màn hình

        Args:
            region: dict với keys {'left', 'top', 'width', 'height'}

        Returns:
            PIL.Image của vùng đã chụp
        """
        screenshot = self.sct.grab(region)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def capture_fullscreen(self) -> Image.Image:
        """Chụp toàn màn hình"""
        monitor = self.sct.monitors[1]  # Monitor chính
        screenshot = self.sct.grab(monitor)
        return Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

    def get_all_monitors(self):
        """Lấy danh sách tất cả màn hình"""
        return self.sct.monitors