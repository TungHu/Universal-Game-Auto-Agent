"""
region_selector.py - Chon vung game
GUI tkinter: keo chuot chon vung, R dung lai vung cu, Enter xac nhan
"""

import os, json, tkinter as tk
from PIL import Image, ImageTk
import mss


class RegionSelector:
    def __init__(self, save_path=None):
        self.region = None
        self.start_x = None
        self.start_y = None
        self.rect_id = None
        self.saved_region = None
        self.save_path = save_path
        self.root = None
        self.canvas = None
        self.coord_label = None
        if save_path and os.path.exists(save_path):
            try:
                with open(save_path, "r", encoding="utf-8-sig") as f:
                    self.saved_region = json.load(f)
            except Exception:
                self.saved_region = None

    def select_region(self):
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            screenshot = sct.grab(monitor)
            img = Image.frombytes("RGB", screenshot.size, screenshot.bgra, "raw", "BGRX")
        self.root = tk.Tk()
        self.root.title("Chon vung game - Keo chuot, R=vung cu, Enter=xac nhan, Esc=huy")
        self.root.attributes("-fullscreen", True)
        self.root.attributes("-topmost", True)
        screen_w = self.root.winfo_screenwidth()
        screen_h = self.root.winfo_screenheight()
        self.canvas = tk.Canvas(self.root, cursor="cross", bg="black", highlightthickness=0)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        self.canvas_img = ImageTk.PhotoImage(img)
        self.canvas.create_image(0, 0, anchor=tk.NW, image=self.canvas_img)
        if self.saved_region:
            r = self.saved_region
            self.canvas.create_rectangle(
                r["left"], r["top"], r["left"] + r["width"], r["top"] + r["height"],
                outline="#00FF00", width=3, dash=(8, 4), tags="saved"
            )
            self.canvas.create_text(
                r["left"] + 5, r["top"] - 15,
                text=f"VUNG DA LUU: {r['width']}x{r['height']} tai ({r['left']}, {r['top']})",
                anchor=tk.W, fill="#00FF00", font=("Arial", 12, "bold"), tags="saved"
            )
        self.canvas.create_text(
            10, screen_h - 40,
            text="Keo chuot de chon vung | R = dung lai vung cu | Enter = xac nhan | Esc = huy",
            anchor=tk.W, fill="white", font=("Arial", 11)
        )
        self.coord_label = self.canvas.create_text(
            screen_w - 150, screen_h - 40, text="",
            anchor=tk.E, fill="yellow", font=("Arial", 10)
        )
        self.canvas.bind("<ButtonPress-1>", self._on_mouse_down)
        self.canvas.bind("<B1-Motion>", self._on_mouse_drag)
        self.canvas.bind("<ButtonRelease-1>", self._on_mouse_up)
        self.canvas.bind("<Motion>", self._on_mouse_move)
        self.root.bind("<Return>", self._on_confirm)
        self.root.bind("<Escape>", self._on_cancel)
        self.root.bind("<Key-r>", self._on_reuse_saved)
        self.root.bind("<Key-R>", self._on_reuse_saved)
        self.canvas.image = self.canvas_img
        self.root.mainloop()
        return self.region

    def _on_mouse_down(self, event):
        self.start_x, self.start_y = event.x, event.y
        if self.rect_id:
            self.canvas.delete(self.rect_id)
        self.rect_id = self.canvas.create_rectangle(
            self.start_x, self.start_y, event.x, event.y,
            outline="red", width=3, dash=(10, 5)
        )

    def _on_mouse_drag(self, event):
        if self.rect_id:
            self.canvas.coords(self.rect_id, self.start_x, self.start_y, event.x, event.y)
        self._update_coord_label(event.x, event.y)

    def _on_mouse_up(self, event):
        if self.start_x is None:
            return
        x1 = min(self.start_x, event.x)
        y1 = min(self.start_y, event.y)
        x2 = max(self.start_x, event.x)
        y2 = max(self.start_y, event.y)
        self.region = {"left": x1, "top": y1, "width": x2 - x1, "height": y2 - y1}

    def _on_mouse_move(self, event):
        self._update_coord_label(event.x, event.y)

    def _update_coord_label(self, x, y):
        if self.coord_label:
            self.canvas.itemconfig(self.coord_label, text=f"Toa do: ({x}, {y})")

    def _on_confirm(self, event):
        if self.region is None:
            if self.saved_region:
                self.region = self.saved_region.copy()
            else:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    self.region = {"left": monitor["left"], "top": monitor["top"], "width": monitor["width"], "height": monitor["height"]}
        if self.save_path and self.region:
            os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
            with open(self.save_path, "w") as f:
                json.dump(self.region, f, indent=2)
        self.root.quit()
        self.root.destroy()

    def _on_cancel(self, event):
        self.region = None
        self.root.quit()
        self.root.destroy()

    def _on_reuse_saved(self, event):
        if self.saved_region:
            self.region = self.saved_region.copy()
            if self.save_path:
                os.makedirs(os.path.dirname(self.save_path), exist_ok=True)
                with open(self.save_path, "w") as f:
                    json.dump(self.region, f, indent=2)
            self.root.quit()
            self.root.destroy()

    @staticmethod
    def save_region(game_dir, region):
        path = os.path.join(game_dir, "region.json")
        with open(path, "w", encoding="utf-8") as f:
            json.dump(region, f, indent=2)
        print(f"  Da luu vung game vao {path}")

    @staticmethod
    def load_region(game_dir):
        path = os.path.join(game_dir, "region.json")
        if os.path.exists(path):
            with open(path, "r", encoding="utf-8-sig") as f:
                return json.load(f)
        return None
