"""
controller.py - Dieu khien chuot va ban phim
Dung pyautogui de mo phong thao tac nguoi dung
"""

import pyautogui
import time
import sys


class GameController:
    """Dieu khien game bang chuot/phim"""

    def __init__(self, config: dict):
        """
        Args:
            config: dict tu config.json cua game
        """
        self.config = config
        self.control_type = config.get("control", {}).get("type", "keyboard")
        pyautogui.PAUSE = 0.05  # Delay giua cac thao tac
        print(f"  [CONTROLLER] Khoi tao: type={self.control_type}")

    def act(self, action: str):
        """
        Thuc thi mot hanh dong trong game

        Args:
            action: Ten hanh dong (up/down/left/right, hoac toa do click)
        """
        action = action.strip().lower()
        print(f"  [CONTROLLER] Thuc thi: '{action}' (type={self.control_type})")

        try:
            if self.control_type == "keyboard":
                self._keyboard_action(action)
            elif self.control_type == "mouse":
                self._mouse_action(action)
            elif self.control_type == "mouse_grid":
                self._mouse_grid_action(action)
            else:
                raise ValueError(f"Unknown control type: {self.control_type}")
            print(f"  [CONTROLLER] OK")
        except Exception as e:
            print(f"  [CONTROLLER] LOI: {e}")

    def _keyboard_action(self, action: str):
        """Nhan phim theo huong dan AI"""
        keys = self.config.get("control", {}).get("keys", [])
        print(f"  [CONTROLLER] Nhan phim: '{action}' (cho phep: {keys})")

        try:
            pyautogui.press(action)
        except Exception as e:
            print(f"  [CONTROLLER] Loi nhan phim: {e}")
            raise

    def _mouse_action(self, action: str):
        """Click chuot tai toa do"""
        try:
            parts = action.strip().split(",")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            print(f"  [CONTROLLER] Click chuot tai ({x}, {y})")
            pyautogui.click(x, y)
        except (ValueError, IndexError):
            # Fallback: click vao vung game
            region = self.config.get("_region", {})
            if region:
                cx = region["left"] + region["width"] // 2
                cy = region["top"] + region["height"] // 2
                print(f"  [CONTROLLER] Click vao tam vung game ({cx}, {cy})")
                pyautogui.click(cx, cy)

    def _mouse_grid_action(self, action: str):
        """Click vao o tren grid (vi du: "2,3" = hang 2, cot 3)"""
        try:
            parts = action.strip().split(",")
            row, col = int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            print(f"  [CONTROLLER] Loi parse grid action: '{action}'")
            return

        region = self.config.get("_region", {})
        control_cfg = self.config.get("control", {})
        grid_size = control_cfg.get("grid_size", [4, 4])

        if not region:
            print("  [CONTROLLER] Loi: khong co region")
            return

        cell_w = region["width"] // grid_size[1]
        cell_h = region["height"] // grid_size[0]

        x = region["left"] + col * cell_w + cell_w // 2
        y = region["top"] + row * cell_h + cell_h // 2

        print(f"  [CONTROLLER] Click grid ({row},{col}) -> man hinh ({x}, {y})")
        pyautogui.click(x, y)