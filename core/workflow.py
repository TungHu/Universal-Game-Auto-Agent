"""workflow.py - Workflow runner for automated tasks"""

import os, json, time, hashlib, random
from PIL import Image


class WorkflowRunner:
    def __init__(self, config, vision, controller, debug=False, dry_run=False, repeat=0):
        self.config = config
        self.vision = vision
        self.controller = controller
        self.debug = debug
        self.dry_run = dry_run
        self.repeat = repeat
        self.steps = config.get("steps", [])
        self.used_photos_file = os.path.join(config.get("_game_dir", "."), "used_photos.json")
        self.used_photos = self._load_used_photos()
        self.cycle_count = 0
        self._capture = None

    def _load_used_photos(self):
        if os.path.exists(self.used_photos_file):
            try:
                with open(self.used_photos_file, "r", encoding="utf-8-sig") as f:
                    return json.load(f)
            except Exception:
                return {}
        return {}

    def _save_used_photos(self):
        with open(self.used_photos_file, "w", encoding="utf-8") as f:
            json.dump(self.used_photos, f, indent=2, ensure_ascii=False)

    def _get_image_path(self, image_name):
        image_dir = self.config.get("image_dir", "input_picture")
        if os.path.isabs(image_dir):
            return os.path.join(image_dir, image_name)
        base = self.config.get("_base_dir", os.path.dirname(os.path.abspath(__file__)))
        return os.path.join(base, image_dir, image_name)

    def _load_reference(self, image_name):
        path = self._get_image_path(image_name)
        if not os.path.exists(path):
            raise FileNotFoundError(f"Reference image not found: {path}")
        return Image.open(path)

    def _image_fingerprint(self, img):
        small = img.resize((32, 32), Image.LANCZOS).convert("L")
        import hashlib, numpy as np
        arr = np.array(small)
        return hashlib.md5(arr.tobytes()).hexdigest()

    def run(self):
        if not self.steps:
            print("  [WARN] Khong co buoc nao trong workflow")
            return
        total = len(self.steps)
        repeat_mode = self.repeat == 0
        cycle = 0
        while repeat_mode or cycle < self.repeat:
            cycle += 1
            self.cycle_count = cycle
            print(f"\n--- Chu ky {cycle} ---")
            ok = 0
            fail = 0
            for idx, step in enumerate(self.steps, 1):
                desc = step.get("description", step.get("image", "unknown"))
                print(f"  [{idx}/{total}] {desc}")
                result = self._run_step(step, idx)
                if result.get("ok"):
                    ok += 1
                    print(f"      OK")
                else:
                    fail += 1
                    msg = result.get("message", "")
                    if result.get("optional"):
                        print(f"      SKIP (optional): {msg}")
                    else:
                        print(f"      FAIL: {msg}")
                wait = step.get("wait_after", 0)
                if wait:
                    time.sleep(wait)
            print(f"--- Chu ky {cycle} xong: OK {ok}/{total}, FAIL {fail}/{total} ---")
            if not repeat_mode and cycle >= self.repeat:
                break

    def _run_step(self, step, step_index):
        action_type = step.get("action", {}).get("type", "ai")
        if action_type == "ai":
            return self._run_ai_step(step, step_index)
        elif action_type == "random_pick":
            return self._run_random_pick(step, step_index)
        elif action_type == "back_until":
            return self._run_back_until(step, step_index)
        elif action_type in ("key", "hotkey", "type", "scroll", "wait", "check"):
            return self._run_basic_action(step, step_index)
        else:
            return {"ok": False, "message": f"Unknown action type: {action_type}"}

    def _run_ai_step(self, step, step_index):
        image_name = step.get("image")
        description = step.get("description", "")
        if not image_name:
            return {"ok": False, "message": "Missing image in step"}
        timeout = step.get("timeout", self.vision._get_ai_config().get("find_timeout", 25.0))
        retry_interval = step.get("retry_interval", self.vision._get_ai_config().get("find_retry", 2.0))
        fallback_click = step.get("fallback_click")
        reference = self._load_reference(image_name)
        result = self.vision.locate(
            reference_image=reference,
            description=description,
            step_index=step_index,
            timeout=timeout,
            retry_interval=retry_interval,
            fallback_click=fallback_click,
        )
        if result["found"]:
            if not self.dry_run:
                self.controller.click_at(result["x"], result["y"])
            else:
                rx = result["x"]
                ry = result["y"]
                print(f"      [DRY-RUN] CLICK ({rx}, {ry})")
            return {"ok": True, "result": result}
        else:
            return {"ok": False, "message": result.get("message", "not found"), "optional": step.get("optional", False)}

    def _run_random_pick(self, step, step_index):
        action_cfg = step.get("action", {})
        count = action_cfg.get("count", 1)
        grid = action_cfg.get("grid", [0.01, 0.20, 0.99, 0.68])
        cols = action_cfg.get("cols", 3)
        rows = action_cfg.get("rows", 3)
        scroll_cfg = action_cfg.get("scroll", {}) or {}
        scroll_enabled = scroll_cfg.get("enabled", False)
        scroll_times = scroll_cfg.get("times", [1, 3])
        scroll_amount = scroll_cfg.get("amount", [300, 800])
        avoid_repeat = action_cfg.get("avoid_repeat", True)
        verify_count = action_cfg.get("verify_count", False)
        region = self.vision.region or {"left": 0, "top": 0, "width": 1368, "height": 912}
        rw = region["width"]
        rh = region["height"]
        left = int(grid[0] * rw) + region["left"]
        top = int(grid[1] * rh) + region["top"]
        right = int(grid[2] * rw) + region["left"]
        bottom = int(grid[3] * rh) + region["top"]
        cell_w = (right - left) / cols
        cell_h = (bottom - top) / rows

        used = set(self.used_photos.get("fingerprints", []))
        picks = []
        picked_cells = set()
        scroll_rounds = 0
        max_scroll_rounds = 3
        attempts = 0
        max_attempts = max(count * 10, 20)

        while len(picks) < count and attempts < max_attempts:
            attempts += 1
            free_cells = [(c, r) for c in range(cols) for r in range(rows)
                          if (c, r) not in picked_cells]
            if not free_cells:
                if scroll_enabled and scroll_rounds < max_scroll_rounds:
                    scroll_rounds += 1
                    print(f"      Het o trong -> cuon lan {scroll_rounds}")
                    self._random_scroll(scroll_amount, scroll_times)
                    picked_cells.clear()
                    continue
                print("      Het anh moi -> cho phep dung lai anh cu")
                free_cells = [(c, r) for c in range(cols) for r in range(rows)]
                avoid_repeat = False

            col, row = random.choice(free_cells)
            picked_cells.add((col, row))
            cx = left + int(col * cell_w + cell_w / 2)
            cy = top + int(row * cell_h + cell_h / 2)

            fp = self._cell_fingerprint(cx, cy, cell_w, cell_h)
            if avoid_repeat and fp and fp in used:
                print(f"      Bo qua o ({col},{row}) - da dung o lan truoc")
                continue

            if self.dry_run:
                print(f"      [DRY-RUN] CLICK o ({col},{row}) -> ({cx}, {cy})")
            else:
                self.controller.click_at(cx, cy)
            picks.append({"col": col, "row": row, "x": cx, "y": cy, "fingerprint": fp})
            if fp:
                used.add(fp)
            time.sleep(0.5)

        if len(picks) < count:
            return {"ok": False, "message": f"Chi chon duoc {len(picks)}/{count} anh"}

        if verify_count:
            check = self.vision.count_selected_items(
                step.get("description", "anh da chon"), count, step_index
            )
            print(f"      AI dem: {check.get('count')} (mong doi {count})")
            if check.get("found") and check.get("count") != count:
                print(f"      [WARN] AI dem lech: {check.get('count')} != {count}")

        self.used_photos["fingerprints"] = sorted(used)
        self._save_used_photos()
        print(f"      Da chon {len(picks)} anh (tong fingerprint da luu: {len(used)})")
        return {"ok": True, "picks": picks}

    def _screen_capture(self):
        if getattr(self, "_capture", None) is None:
            from core.capture import ScreenCapture
            self._capture = ScreenCapture()
        return self._capture

    def _cell_fingerprint(self, cx, cy, cell_w, cell_h):
        try:
            half_w = max(int(cell_w / 2) - 4, 1)
            half_h = max(int(cell_h / 2) - 4, 1)
            region = {
                "left": cx - half_w,
                "top": cy - half_h,
                "width": half_w * 2,
                "height": half_h * 2,
            }
            img = self._screen_capture().capture_region(region)
            return self._image_fingerprint(img)
        except Exception:
            return None

    def _random_scroll(self, amount_range, times_range):
        times = random.randint(int(times_range[0]), int(times_range[1]))
        amount = random.randint(int(amount_range[0]), int(amount_range[1]))
        for _ in range(times):
            if self.dry_run:
                print(f"      [DRY-RUN] SCROLL {amount}")
            else:
                self.controller.scroll(amount)
            time.sleep(0.4)
        return times, amount

    def _run_back_until(self, step, step_index):
        action_cfg = step.get("action", {})
        max_presses = action_cfg.get("max_presses", 8)
        wait_each = action_cfg.get("wait_after_each", 1.5)
        back_cfg = action_cfg.get("back", {})
        image_name = step.get("image")
        reference = self._load_reference(image_name) if image_name else None
        for i in range(max_presses):
            if reference:
                result = self.vision.verify_same(reference, step_index=step_index)
                if result.get("same"):
                    print(f"      Thay anh mau -> dung back")
                    return {"ok": True, "back_presses": i}
            if not self.dry_run:
                if back_cfg.get("type") == "click_pct":
                    px, py = back_cfg["point"]
                    region = self.vision.region or {"left": 0, "top": 0, "width": 1368, "height": 912}
                    bx = region["left"] + int(px * region["width"])
                    by = region["top"] + int(py * region["height"])
                    self.controller.click_at(bx, by)
                else:
                    self.controller.press_key("back")
            else:
                print(f"      [DRY-RUN] BACK #{i+1}")
            time.sleep(wait_each)
        return {"ok": True, "back_presses": max_presses}

    def _run_basic_action(self, step, step_index):
        action_cfg = step.get("action", {})
        atype = action_cfg.get("type")
        if atype == "key":
            key = action_cfg.get("key")
            if not self.dry_run:
                self.controller.press_key(key)
            else:
                print(f"      [DRY-RUN] KEY {key}")
            return {"ok": True}
        elif atype == "hotkey":
            keys = action_cfg.get("keys", [])
            if not self.dry_run:
                self.controller.hotkey(*keys)
            else:
                print(f"      [DRY-RUN] HOTKEY {'+'.join(keys)}")
            return {"ok": True}
        elif atype == "type":
            text = action_cfg.get("text", "")
            if not self.dry_run:
                self.controller.type_text(text)
            else:
                print(f"      [DRY-RUN] TYPE '{text}'")
            return {"ok": True}
        elif atype == "scroll":
            amount = action_cfg.get("amount", -300)
            if not self.dry_run:
                self.controller.scroll(amount)
            else:
                print(f"      [DRY-RUN] SCROLL {amount}")
            return {"ok": True}
        elif atype == "wait":
            duration = action_cfg.get("duration", 1.0)
            time.sleep(duration)
            return {"ok": True}
        elif atype == "check":
            return {"ok": True}
        return {"ok": False, "message": f"Unknown basic action: {atype}"}
