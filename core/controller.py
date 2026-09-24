"""controller.py - Dieu khien chuot va ban phim"""

import time
from pynput.keyboard import Key, Controller as KeyController
from pynput.mouse import Controller as MouseController


class GameController:
    KEY_MAP = {
        "up": Key.up, "down": Key.down, "left": Key.left, "right": Key.right,
        "enter": Key.enter, "space": Key.space, "esc": Key.esc, "tab": Key.tab,
        "shift": Key.shift, "ctrl": Key.ctrl, "alt": Key.alt,
        "backspace": Key.backspace, "delete": Key.delete, "back": Key.backspace,
    }

    def __init__(self, config):
        self.config = config
        self.control_type = config.get("control", {}).get("type", "keyboard")
        self.keyboard = KeyController()
        self.mouse = MouseController()
        self.region = config.get("_region", {})

    def act(self, action):
        action = action.strip().lower()
        try:
            if self.control_type == "keyboard":
                self._keyboard_action(action)
            elif self.control_type == "mouse":
                self._mouse_action(action)
            elif self.control_type == "mouse_grid":
                self._mouse_grid_action(action)
            else:
                self._generic_action(action)
        except Exception as e:
            print(f"  {action.upper()} ({self.control_type}) - LOI: {e}")
            return
        print(f"  {action.upper()} ({self.control_type})")

    def _keyboard_action(self, action):
        if action in self.KEY_MAP:
            key = self.KEY_MAP[action]
        else:
            key = action
        self.keyboard.press(key)
        time.sleep(0.05)
        self.keyboard.release(key)

    def _mouse_action(self, action):
        parts = action.strip().split(",")
        if len(parts) == 2:
            x, y = int(parts[0].strip()), int(parts[1].strip())
        elif self.region:
            x = self.region["left"] + self.region["width"] // 2
            y = self.region["top"] + self.region["height"] // 2
        else:
            return
        self.mouse.position = (x, y)
        time.sleep(0.05)
        self.mouse.click()

    def _mouse_grid_action(self, action):
        parts = action.strip().split(",")
        if len(parts) != 2:
            return
        row, col = int(parts[0].strip()), int(parts[1].strip())
        control_cfg = self.config.get("control", {})
        grid_size = control_cfg.get("grid_size", [4, 4])
        if not self.region:
            return
        cell_w = self.region["width"] // grid_size[1]
        cell_h = self.region["height"] // grid_size[0]
        x = self.region["left"] + col * cell_w + cell_w // 2
        y = self.region["top"] + row * cell_h + cell_h // 2
        self.mouse.position = (x, y)
        time.sleep(0.05)
        self.mouse.click()

    def _generic_action(self, action):
        parts = action.strip().split(",")
        if len(parts) == 2:
            try:
                x, y = int(parts[0].strip()), int(parts[1].strip())
                self.click_at(x, y)
                return
            except (ValueError, IndexError):
                pass
        if action in self.KEY_MAP:
            self.press_key(action)

    def click_at(self, x, y, region=None):
        if region:
            x = region.get("left", 0) + x
            y = region.get("top", 0) + y
        self.mouse.position = (x, y)
        time.sleep(0.05)
        self.mouse.click()

    def move_to(self, x, y, region=None):
        if region:
            x = region.get("left", 0) + x
            y = region.get("top", 0) + y
        self.mouse.position = (x, y)
        time.sleep(0.02)

    def press_key(self, key_name):
        key_name = key_name.strip().lower()
        if key_name in self.KEY_MAP:
            key = self.KEY_MAP[key_name]
        else:
            key = key_name
        self.keyboard.press(key)
        time.sleep(0.05)
        self.keyboard.release(key)

    def hotkey(self, *keys):
        pressed = []
        for k in keys:
            k = k.strip().lower()
            if k in self.KEY_MAP:
                key = self.KEY_MAP[k]
            else:
                key = k
            self.keyboard.press(key)
            pressed.append(key)
            time.sleep(0.03)
        for key in reversed(pressed):
            self.keyboard.release(key)
            time.sleep(0.03)

    def type_text(self, text, interval=0.03):
        for ch in text:
            self.keyboard.press(ch)
            time.sleep(interval)
            self.keyboard.release(ch)

    def scroll(self, amount):
        self.mouse.scroll(0, int(amount / 100))
