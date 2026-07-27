"""
region_selector.py - Chọn vùng game thủ công
Hiển thị ảnh toàn màn hình, người dùng click-kéo chọn vùng game
"""

import tkinter as tk
from PIL import Image, ImageTk
import mss
import os
import json


class RegionSelector:
    """GUI cho phép người dùng chọn vùng game trên màn hình"""

    def __init__(self):
        self.region = None
        self.start_x = None
        self.start_y = None
        self.rect = None
        self.root = None
        self.canvas = None

    def select_region(self) -> dict:
        """
        Mở cửa sổ fullscreen, người dùng click-kéo chọn vùng

        Returns:
            dict: {'left', 'top', 'width', 'height'}
        """
        # Chụp toàn màn hình
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")

        # Tạo cửa sổ tkinter
        self.root = tk.Tk()
        self.root.title("Chọn vùng game - Click kéo để chọn, nhấn Enter để xác nhận")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)

        # Convert ảnh sang PhotoImage
        img_tk = ImageTk.PhotoImage(img)

        # Canvas để hiển thị ảnh và vẽ hình chữ nhật
        self.canvas = tk.Canvas(self.root, width=img.width, height=img.height)
        self.canvas.pack()
        self.canvas.create_image(0, 0, anchor=tk.NW, image=img_tk)

        # Bind sự kiện chuột
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.root.bind("<Return>", self._on_confirm)
        self.root.bind("<Escape>", self._on_cancel)

        # Giữ reference để ảnh không bị garbage collect
        self.canvas.image = img_tk

        # Chờ người dùng chọn
        self.root.mainloop()

        return self.region

    def _on_mouse_down(self, event):
        """Bắt đầu kéo chọn"""
        self.start_x = event.x
        self.start_y = event.y
        if self.rect:
            self.canvas.delete(self.rect)
        self.rect = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="red", width=3, dash=(10, 5)
        )

    def _on_mouse_drag(self, event):
        """Kéo để mở rộng vùng chọn"""
        if self.rect:
            self.canvas.coords(self.rect, self.start_x, self.start_y, event.x, event.y)

    def _on_mouse_up(self, event):
        """Kết thúc kéo chọn"""
        if self.start_x is None or self.start_y is None:
            return

        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)

        self.region = {
            "left": x1,
            "top": y1,
            "width": x2 - x1,
            "height": y2 - y1
        }

    def _on_confirm(self, event):
        """Xác nhận vùng chọn và đóng"""
        if self.region is None:
            # Nếu chưa chọn, dùng toàn màn hình
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                self.region = {
                    "left": monitor["left"],
                    "top": monitor["top"],
                    "width": monitor["width"],
                    "height": monitor["height"]
                }
        self.root.quit()
        self.root.destroy()

    def _on_cancel(self, event):
        """Hủy và thoát"""
        self.region = None
        self.root.quit()
        self.root.destroy()

    @staticmethod
    def save_region(game_dir: str, region: dict):
        """Lưu region vào file region.json"""
        path = os.path.join(game_dir, "region.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(region, f, indent=2)
        print(f"  ✅ Đã lưu vùng game vào {path}")

    @staticmethod
    def load_region(game_dir: str) -> dict:
        """Đọc region từ file region.json"""
        path = os.path.join(game_dir, "region.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8") as f:
                return json.load(f)
        return None