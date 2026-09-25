"""crop.py - Cong cu crop anh template tu screenshot

Su dung: python tools/crop.py <duong_dan_anh>
Vi du:   python tools/crop.py input_picture/1.jpg

Thao tac: keo chuot de chon vung -> Enter = luu (hoi ten file) -> Esc = huy
Anh luu vao input_picture/templates/<ten>.png
"""

import os
import sys
import tkinter as tk
from tkinter import simpledialog
from PIL import Image, ImageTk


def main():
    if len(sys.argv) < 2:
        print("Su dung: python tools/crop.py <duong_dan_anh>")
        sys.exit(1)
    src = sys.argv[1]
    if not os.path.exists(src):
        print(f"Khong tim thay anh: {src}")
        sys.exit(1)

    base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    out_dir = os.path.join(base_dir, "input_picture")

    img = Image.open(src).convert("RGB")
    iw, ih = img.size

    root = tk.Tk()
    root.title(f"Crop template - {os.path.basename(src)} ({iw}x{ih})")

    # Scale anh vua man hinh neu qua lon
    sw = root.winfo_screenwidth() - 100
    sh = root.winfo_screenheight() - 150
    scale = min(1.0, sw / iw, sh / ih)
    disp_w, disp_h = int(iw * scale), int(ih * scale)
    disp_img = img.resize((disp_w, disp_h), Image.LANCZOS)

    canvas = tk.Canvas(root, width=disp_w, height=disp_h, cursor="cross")
    canvas.pack()
    canvas.create_image(0, 0, anchor=tk.NW, image=ImageTk.PhotoImage(disp_img))

    info = tk.Label(root, text="Keo chuot de chon vung | Enter = luu | Esc = huy")
    info.pack()

    state = {"x0": None, "y0": None, "rect": None, "img_tk": canvas.data_images[0] if hasattr(canvas, "data_images") else None}

    def on_down(e):
        state["x0"], state["y0"] = e.x, e.y
        if state["rect"]:
            canvas.delete(state["rect"])
        state["rect"] = canvas.create_rectangle(e.x, e.y, e.x, e.y, outline="red", width=2)

    def on_drag(e):
        if state["x0"] is not None:
            canvas.coords(state["rect"], state["x0"], state["y0"], e.x, e.y)

    def on_up(e):
        if state["x0"] is None:
            return
        x1, x2 = sorted((state["x0"], e.x))
        y1, y2 = sorted((state["y0"], e.y))
        # Ve khung chinh xac (toanh lech do scale)
        canvas.coords(state["rect"], x1, y1, x2, y2)

    def sel_real():
        if state["x0"] is None:
            return None
        coords = canvas.coords(state["rect"])
        x1, y1, x2, y2 = [int(round(c / scale)) for c in coords]
        x1, y1 = max(0, x1), max(0, y1)
        x2, y2 = min(iw, x2), min(ih, y2)
        if x2 - x1 < 5 or y2 - y1 < 5:
            return None
        return (x1, y1, x2, y2)

    def on_enter(e):
        box = sel_real()
        if not box:
            info.config(text="Vung qua nho - keo lai!", fg="red")
            return
        name = simpledialog.askstring("Luu template", "Ten file (khong can .png):",
                                      parent=root)
        if not name:
            return
        if not name.endswith(".png"):
            name += ".png"
        os.makedirs(out_dir, exist_ok=True)
        out_path = os.path.join(out_dir, name)
        img.crop(box).save(out_path)
        print(f"Da luu: {out_path}  (box={box})")
        print(f"Hint: dat ten theo quy uoc <so>x (vi du 8x) va goi trong steps.json bang ten do")
        root.destroy()

    def on_esc(e):
        root.destroy()

    canvas.bind("<ButtonPress-1>", on_down)
    canvas.bind("<B1-Motion>", on_drag)
    canvas.bind("<ButtonRelease-1>", on_up)
    root.bind("<Return>", on_enter)
    root.bind("<Escape>", on_esc)
    root.mainloop()


if __name__ == "__main__":
    main()
