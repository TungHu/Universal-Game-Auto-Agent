
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
        # image_dir co the la 1 duong dan hoac danh sach thu muc (thu tu uu tien)
        image_dirs = self.config.get("image_dir", "input_picture")
        if isinstance(image_dirs, str):
            image_dirs = [image_dirs]
        base = self.config.get("_base_dir", os.path.dirname(os.path.abspath(__file__)))

        for image_dir in image_dirs:
            if os.path.isabs(image_dir):
                path = os.path.join(image_dir, image_name)
            else:
                path = os.path.join(base, image_dir, image_name)
            # Ten khong co extension (vi du "1", "1x") -> tu tim file hinh
            if not os.path.splitext(path)[1]:
                for ext in (".png", ".jpg", ".jpeg", ".webp"):
                    if os.path.exists(path + ext):
                        return path + ext
            elif os.path.exists(path):
                return path
        return os.path.join(base, image_dirs[0], image_name)

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
            # Bug B: xoa cache frame truoc moi chu ky, neu khong chu ky 2+
            # cung man hinh se bi bo qua goi AI -> timeout
            if hasattr(self.vision, "reset_frame_cache"):
                self.vision.reset_frame_cache()
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
                # Bo delay khi buoc truoc da phat hien + click xong (co template)
                # va buoc sau cung co template -> buoc sau se tu poll den khi thay
                wait = step.get("wait_after", 0)
                # Buoc co force_wait=true -> van giu delay du buoc sau co template
                if wait and step.get("template") and not step.get("force_wait"):
                    nxt = self.steps[idx] if idx < total else None
                    if nxt and nxt.get("template"):
                        wait = 0
                if wait:
                    print(f"      Cho {wait:g} giay truoc buoc tiep theo...")
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
        description = step.get("description", "")
        template_name = step.get("template")
        image_name = step.get("image")
        if not template_name and not image_name:
            return {"ok": False, "message": "Missing image/template in step"}
        fallback_click = step.get("fallback_click")
        if template_name:
            # Template matching cuc bo - KHONG goi API
            timeout = step.get("timeout", 25.0)
            retry_interval = step.get("retry_interval", 1.0)
            threshold = step.get("threshold", 0.75)
            reference = self._load_reference(template_name)
            result = self.vision.locate_template(
                reference,
                description=description,
                step_index=step_index,
                timeout=timeout,
                retry_interval=retry_interval,
                threshold=threshold,
                fallback_click=fallback_click,
            )
        else:
            ai_cfg = self.vision._get_ai_config()
            timeout = step.get("timeout", ai_cfg.get("find_timeout", 25.0))
            retry_interval = step.get("retry_interval", ai_cfg.get("find_retry", 2.0))
            min_interval = ai_cfg.get("min_interval", 1.0)
            reference = self._load_reference(image_name)
            result = self.vision.locate(
                reference_image=reference,
                description=description,
                step_index=step_index,
                timeout=timeout,
                retry_interval=retry_interval,
                fallback_click=fallback_click,
                min_interval=min_interval,
            )
        # Fallback tra found=False nhung van co toa do -> PHAI click, khong thi
        # fallback_click trong steps.json tro thanh vo nghia
        if result.get("found") or result.get("action") == "fallback_click":
            if not result.get("found"):
                print(f"      [FALLBACK] {result.get('message', 'dung fallback_click')}")
            elif result.get("score") is not None:
                print(f"      match score: {result.get('score')}")
            try:
                if not self.dry_run:
                    self.controller.click_at(result["x"], result["y"])
                else:
                    print(f"      [DRY-RUN] CLICK ({result['x']}, {result['y']})")
            except Exception as e:
                return {"ok": False, "message": f"Loi click: {e}",
                        "optional": step.get("optional", False)}
            return {"ok": True, "result": result}
        return {"ok": False, "message": result.get("message", "not found"),
                "optional": step.get("optional", False)}

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
        skip_used_count = 0

        while len(picks) < count and attempts < max_attempts:
            attempts += 1
            free_cells = [(c, r) for c in range(cols) for r in range(rows)
                          if (c, r) not in picked_cells]
            if not free_cells:
                if avoid_repeat and self._all_used(skip_used_count, cols, rows):
                    # Tat ca o deu da dung -> dung lai anh cu ngay, khong cuon nua
                    print("      Tat ca o da dung o lan truoc -> cho phep dung lai anh cu")
                    avoid_repeat = False
                    skip_used_count = 0
                    picked_cells.clear()
                    continue
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
                skip_used_count += 1
                print(f"      Bo qua o ({col},{row}) - da dung o lan truoc")
                if skip_used_count >= cols * rows:
                    # Vuot qua toan bo luoi ma van khong chon duoc -> dung lai anh cu ngay
                    print("      Tat ca o da dung o lan truoc -> cho phep dung lai anh cu")
                    avoid_repeat = False
                    skip_used_count = 0
                    picked_cells.clear()
                continue

            if self.dry_run:
                print(f"      [DRY-RUN] CLICK o ({col},{row}) -> ({cx}, {cy})")
            else:
                try:
                    self.controller.click_at(cx, cy)
                except Exception as e:
                    return {"ok": False, "message": f"Loi click o ({col},{row}): {e}"}
            picks.append({"col": col, "row": row, "x": cx, "y": cy, "fingerprint": fp})
            if fp:
                used.add(fp)
            time.sleep(0.5)

        if len(picks) < count:
            return {"ok": False, "message": f"Chi chon duoc {len(picks)}/{count} anh"}

        if verify_count:
            count_tmpl_name = action_cfg.get("count_template")
            if count_tmpl_name:
                try:
                    tmpl = self._load_reference(count_tmpl_name)
                    check = self.vision.count_template(
                        tmpl, threshold=action_cfg.get("count_threshold", 0.75))
                    print(f"      Template dem: {check.get('count')} (mong doi {count}) - {check.get('message', '')}")
                    if check.get("found") and check.get("count") != count:
                        print(f"      [WARN] Dem lech: {check.get('count')} != {count}")
                except Exception as e:
                    print(f"      [WARN] Khong dem duoc: {e}")
            else:
                print("      [SKIP] verify_count: khong cung cap count_template (khong dung API)")

        self.used_photos["fingerprints"] = sorted(used)
        self._save_used_photos()
        print(f"      Da chon {len(picks)} anh (tong fingerprint da luu: {len(used)})")
        return {"ok": True, "picks": picks}

    @staticmethod
    def _all_used(skip_used_count, cols, rows):
        """True khi da bo qua toan bo vi vi tri cu da duoc dung."""
        return skip_used_count >= cols * rows

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
        max_presses = int(action_cfg.get("max_presses", 8))
        wait_each = float(action_cfg.get("wait_after_each", 1.5))
        back_cfg = action_cfg.get("back", {})

        # Che do cu: click mot template cho toi khi KHONG con thay no.
        template_name = step.get("template")
        if template_name and action_cfg.get("mode") == "click_until_gone":
            return self._run_click_until_gone(
                step, step_index, template_name, max_presses, wait_each)

        # Dieu kien dung ro rang: template can xuat hien, vi du 1x.
        target_template = step.get("until_template")
        image_name = step.get("image")
        reference_name = target_template or image_name
        if not reference_name:
            return {"ok": False, "back_presses": 0,
                    "message": "Thieu 'until_template' hoac 'image' cho dieu kien dung"}
        try:
            reference = self._load_reference(reference_name)
        except Exception as e:
            return {"ok": False, "back_presses": 0,
                    "message": f"Loi doc mau '{reference_name}': {e}"}

        threshold = float(step.get(
            "until_threshold", step.get("threshold", 0.8)))
        check_timeout = float(step.get("check_timeout", 0.5))
        retry_interval = float(step.get("retry_interval", 0.1))
        scales = step.get("until_scales", step.get("scales"))

        def find_target():
            if target_template:
                return self.vision.locate_template(
                    reference,
                    description=step.get("description", ""),
                    step_index=step_index,
                    timeout=check_timeout,
                    retry_interval=retry_interval,
                    threshold=threshold,
                    scales=scales,
                )
            return self.vision.verify_same(reference, step_index=step_index)

        def found(result):
            return bool(result.get("found") if target_template
                        else result.get("same"))

        def score(result):
            return result.get("score", result.get("confidence", 0))

        # Kiem tra mot lan dau va mot lan sau click cuoi cung.
        for clicks in range(max_presses + 1):
            try:
                result = find_target()
            except Exception as e:
                return {"ok": False, "back_presses": clicks,
                        "message": f"Loi kiem tra '{reference_name}': {e}"}

            if found(result):
                print(f"      Tim thay '{reference_name}' (score {score(result)}) "
                      f"-> da ve man hinh chinh sau {clicks} lan click Back")
                return {"ok": True, "back_presses": clicks,
                        "message": "Da tim thay man hinh dich"}

            if clicks == max_presses:
                print(f"      [FAIL] Khong thay '{reference_name}' sau "
                      f"{max_presses} lan click Back")
                return {"ok": False, "back_presses": max_presses,
                        "message": f"Khong thay '{reference_name}' sau {max_presses} lan click Back"}

            if not self.dry_run:
                if back_cfg.get("type") == "click_pct":
                    point = back_cfg.get("point")
                    if not isinstance(point, (list, tuple)) or len(point) != 2:
                        return {"ok": False, "back_presses": clicks,
                                "message": "Thieu hoac sai 'back.point'"}
                    px, py = point
                    region = getattr(self.vision, "region", None) or {
                        "left": 0, "top": 0, "width": 1368, "height": 912
                    }
                    bx = region["left"] + int(px * region["width"])
                    by = region["top"] + int(py * region["height"])
                    self.controller.click_at(bx, by)
                else:
                    self.controller.press_key("back")
            else:
                print(f"      [DRY-RUN] BACK {clicks + 1}/{max_presses}")

            print(f"      Click Back {clicks + 1}/{max_presses}; "
                  f"cho {wait_each:g} giay roi kiem tra lai...")
            time.sleep(wait_each)

        return {"ok": False, "back_presses": max_presses,
                "message": "Khong tim thay dieu kien dung"}

    def _run_click_until_gone(self, step, step_index, template_name,
                              max_presses, wait_each):
        """Click dau X (template) cho toi khi tim thay `until_template` tren man hinh.

        Mac dinh: bam 8x (dau X) cho den khi thay 1x (tile Engine Speed Lyrics)
        => man hinh da tro ve man hinh chinh AI Creation.
        """
        threshold = step.get("threshold", 0.8)
        check_timeout = step.get("check_timeout", 2.0)
        retry_interval = step.get("retry_interval", 0.5)
        scales = step.get("scales")
        until_name = step.get("until_template", "1x")
        until_threshold = step.get("until_threshold", 0.75)
        until_scales = step.get("until_scales")
        try:
            reference = self._load_reference(template_name)
            until_reference = self._load_reference(until_name)
        except Exception as e:
            return {"ok": False, "message": f"Loi doc template: {e}"}

        def find(ref, name, th, sc):
            return self.vision.locate_template(
                ref,
                description=step.get("description", ""),
                step_index=step_index,
                timeout=check_timeout,
                retry_interval=retry_interval,
                threshold=th,
                scales=sc,
            )

        clicks = 0
        for i in range(max_presses):
            # 1. Da ve man hinh chinh chua? (thay 1x)
            goal = find(until_reference, until_name, until_threshold, until_scales)
            if goal.get("found"):
                print(f"      Tim thay '{until_name}' (score {goal.get('score')}) "
                      f"-> da ve man hinh chinh sau {clicks} lan click X")
                return {"ok": True, "clicks": clicks}
            # 2. Chua ve -> tim dau X de bam
            x_res = find(reference, template_name, threshold, scales)
            if not x_res.get("found"):
                print(f"      Khong thay '{template_name}' va cung khong thay "
                      f"'{until_name}' -> dung o lan {i+1}")
                return {"ok": False, "clicks": clicks,
                        "message": f"Khong thay X hay {until_name} sau {clicks} lan click"}
            clicks += 1
            print(f"      Click X lan {i+1}/{max_presses} tai "
                  f"({x_res['x']}, {x_res['y']}) score {x_res.get('score')}")
            try:
                if not self.dry_run:
                    self.controller.click_at(x_res["x"], x_res["y"])
                else:
                    print(f"      [DRY-RUN] CLICK ({x_res['x']}, {x_res['y']})")
            except Exception as e:
                return {"ok": False, "message": f"Loi click: {e}"}
            time.sleep(wait_each)
        # Het luot: kiem tra lai lan cuoi
        goal = find(until_reference, until_name, until_threshold, until_scales)
        if goal.get("found"):
            print(f"      Tim thay '{until_name}' sau {clicks} lan click X")
            return {"ok": True, "clicks": clicks}
        print(f"      [WARN] Click {clicks} lan van khong thay '{until_name}'")
        return {"ok": False, "clicks": clicks,
                "message": f"Click {clicks} lan van khong thay '{until_name}'"}

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
