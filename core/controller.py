"""
controller.py - Dieu khien chuot va ban phim
Dung pynput (low-level input) de gui phim/click - hoat dong voi moi game
"""

import time
from pynput.keyboard import Key, Controller as KeyController
from pynput.mouse import Controller as MouseController


class GameController:
    """Dieu khien game bang chuot/phim dung pynput (low-level)"""

    # Map ten phim tu AI sang pynput Key
    KEY_MAP = {
        "up": Key.up,
        "down": Key.down,
        "left": Key.left,
        "right": Key.right,
        "enter": Key.enter,
        "space": Key.space,
        "esc": Key.esc,
        "tab": Key.tab,
        "shift": Key.shift,
        "ctrl": Key.ctrl,
        "alt": Key.alt,
        "backspace": Key.backspace,
        "delete": Key.delete,
    }

    def __init__(self, config: dict):
        """
        Args:
            config: dict tu config.json cua game
        """
        self.config = config
        self.control_type = config.get("control", {}).get("type", "keyboard")
        self.keyboard = KeyController()
        self.mouse = MouseController()
        self.region = config.get("_region", {})
        print(f"  [CONTROLLER] Khoi tao: type={self.control_type} (pynput)")

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
        """Nhan phim bang pynput (low-level, hoat dong voi game)"""
        keys = self.config.get("control", {}).get("keys", [])
        print(f"  [CONTROLLER] Nhan phim: '{action}' (cho phep: {keys})")

        # Map action -> pynput Key
        if action in self.KEY_MAP:
            key = self.KEY_MAP[action]
        else:
            # Neu la phim thuong (a, b, c, w, ...), gui truc tiep
            key = action

        # Press & release bang pynput
        self.keyboard.press(key)
        time.sleep(0.05)
        self.keyboard.release(key)
        print(f"  [CONTROLLER] Da nhan phim '{action}'")

    def _mouse_action(self, action: str):
        """Click chuot tai toa do bang pynput"""
        try:
            parts = action.strip().split(",")
            x, y = int(parts[0].strip()), int(parts[1].strip())
            print(f"  [CONTROLLER] Click chuot tai ({x}, {y})")
            self.mouse.position = (x, y)
            time.sleep(0.05)
            self.mouse.click()
        except (ValueError, IndexError):
            # Fallback: click vao vung game
            if self.region:
                cx = self.region["left"] + self.region["width"] // 2
                cy = self.region["top"] + self.region["height"] // 2
                print(f"  [CONTROLLER] Click vao tam vung game ({cx}, {cy})")
                self.mouse.position = (cx, cy)
                time.sleep(0.05)
                self.mouse.click()

    def _mouse_grid_action(self, action: str):
        """Click vao o tren grid bang pynput (vi du: "2,3" = hang 2, cot 3)"""
        try:
            parts = action.strip().split(",")
            row, col = int(parts[0].strip()), int(parts[1].strip())
        except (ValueError, IndexError):
            print(f"  [CONTROLLER] Loi parse grid action: '{action}'")
            return

        control_cfg = self.config.get("control", {})
        grid_size = control_cfg.get("grid_size", [4, 4])

        if not self.region:
            print("  [CONTROLLER] Loi: khong co region")
            return

        cell_w = self.region["width"] // grid_size[1]
        cell_h = self.region["height"] // grid_size[0]

        x = self.region["left"] + col * cell_w + cell_w // 2
        y = self.region["top"] + row * cell_h + cell_h // 2

        print(f"  [CONTROLLER] Click grid ({row},{col}) -> man hinh ({x}, {y})")
        self.mouse.position = (x, y)
        time.sleep(0.05)
        self.mouse.click()