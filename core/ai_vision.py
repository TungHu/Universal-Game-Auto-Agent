"""ai_vision.py - AI Vision module"""

import os, json, time, hashlib, re, base64
import numpy as np
from PIL import Image, ImageDraw, ImageFont
from io import BytesIO


class AIConnectionError(Exception):
    pass


class AIVision:
    VISION_PROVIDERS = {"gemini", "openai", "claude", "ollama"}
    # Model mac dinh cho tung provider vision
    VISION_DEFAULT_MODEL = {
        "gemini": "gemini-2.0-flash",
        "openai": "gpt-4o-mini",
        "claude": "claude-3-haiku-20240307",
        "ollama": "llama3.2-vision",
    }
    # Canh lon nhat cua anh gui cho AI (px). Anh se bi resize ve kich thuoc nay.
    DEFAULT_MAX_SIZE = 720
    # So lan thu lai khi goi API loi (mang chop, rate limit...)
    DEFAULT_RETRY_ON_ERROR = 1

    def __init__(self, brain, config, region=None, debug=False, mock=False):
        self.brain = brain
        self.config = config
        self.region = region or {}
        self.debug = debug
        self.mock = mock
        self.debug_dir = os.path.join(config.get("_game_dir", "."), "debug")
        self.frame_hashes = {}
        self.last_reply = {}
        self.mock_counter = 0

    def _get_ai_config(self):
        ai_cfg = self.config.get("ai", {})
        provider = ai_cfg.get("provider", "gemini")
        default_model = self.VISION_DEFAULT_MODEL.get(provider, "gemini-2.0-flash")
        return {
            "provider": provider,
            "model": ai_cfg.get("model") or default_model,
            "min_interval": ai_cfg.get("min_interval", 1.0),
            "find_timeout": ai_cfg.get("find_timeout", 25.0),
            "find_retry": ai_cfg.get("find_retry_interval", 2.0),
            "max_size": ai_cfg.get("max_size", self.DEFAULT_MAX_SIZE),
            "retry_on_error": ai_cfg.get("retry_on_error", self.DEFAULT_RETRY_ON_ERROR),
        }

    def _check_vision_support(self, provider):
        if provider not in self.VISION_PROVIDERS:
            raise ValueError(f"Provider '{provider}' khong ho tro AI Vision. Chi ho tro: gemini, openai, claude, ollama")

    def _prepare_image(self, img, max_size=None):
        """
        Resize anh truoc khi gui cho AI.

        Returns:
            (anh_da_resize, ti_le) voi ti_le = kich_thuoc_sau / kich_thuoc_truoc

        LUU Y: toa do AI tra ve tinh theo ANH DA RESIZE nay, nen phai chia
        cho ti_le de quy doi ve pixel that cua vung man hinh.
        """
        if max_size is None:
            max_size = self._get_ai_config()["max_size"]
        w, h = img.size
        if max_size and max(w, h) > max_size:
            scale = max_size / max(w, h)
            new_size = (max(1, int(round(w * scale))), max(1, int(round(h * scale))))
            return img.resize(new_size, Image.LANCZOS), scale
        return img, 1.0

    def _pil_to_base64(self, img):
        """Encode PIL.Image -> base64 JPEG. Khong resize (da lam o _prepare_image)."""
        buffered = BytesIO()
        img.save(buffered, format="JPEG", quality=80)
        return base64.b64encode(buffered.getvalue()).decode("utf-8")

    def _add_grid_overlay(self, img, step_index=0):
        w, h = img.size
        draw = ImageDraw.Draw(img)
        grid_w, grid_h = 144, 256
        line_color = (0, 255, 0, 120)
        text_color = (0, 255, 0)
        bg_color = (0, 0, 0, 100)
        try:
            font = ImageFont.truetype("arial.ttf", 14)
            font_small = ImageFont.truetype("arial.ttf", 10)
        except (OSError, IOError):
            try:
                font = ImageFont.truetype("C:\Windows\Fonts\arial.ttf", 14)
                font_small = ImageFont.truetype("C:\Windows\Fonts\arial.ttf", 10)
            except (OSError, IOError):
                font = ImageFont.load_default()
                font_small = font
        for x in range(0, w, grid_w):
            draw.line([(x, 0), (x, h)], fill=line_color, width=1)
            bbox = draw.textbbox((x + 2, 2), str(x), font=font_small)
            draw.rectangle([(bbox[0]-1, bbox[1]-1), (bbox[2]+1, bbox[3]+1)], fill=bg_color)
            draw.text((x + 2, 2), str(x), fill=text_color, font=font_small)
        for y in range(0, h, grid_h):
            draw.line([(0, y), (w, y)], fill=line_color, width=1)
            bbox = draw.textbbox((2, y + 2), str(y), font=font_small)
            draw.rectangle([(bbox[0]-1, bbox[1]-1), (bbox[2]+1, bbox[3]+1)], fill=bg_color)
            draw.text((2, y + 2), str(y), fill=text_color, font=font_small)
        bbox = draw.textbbox((w - 80, h - 20), f"{w}x{h}", font=font_small)
        draw.rectangle([(bbox[0]-2, bbox[1]-2), (bbox[2]+2, bbox[3]+2)], fill=(0,0,0,180))
        draw.text((w - 78, h - 18), f"{w}x{h}", fill=(255,255,0), font=font_small)
        if self.debug:
            debug_path = os.path.join(self.debug_dir, f"step_{step_index:02d}_grid.jpg")
            os.makedirs(self.debug_dir, exist_ok=True)
            img.save(debug_path, "JPEG")
        return img

    def _compute_frame_hash(self, img):
        small = img.resize((64, 64), Image.LANCZOS).convert("L")
        arr = np.array(small)
        return hashlib.md5(arr.tobytes()).hexdigest()

    def _frame_changed(self, step_index, img):
        current_hash = self._compute_frame_hash(img)
        last_hash = self.frame_hashes.get(step_index)
        if last_hash == current_hash:
            return False
        self.frame_hashes[step_index] = current_hash
        return True

    def reset_frame_cache(self):
        """Xoa cache frame. Phai goi o dau moi chu ky, neu khong chu ky sau se
        tuong man hinh khong doi va bo qua luon buoc goi AI."""
        self.frame_hashes.clear()

    def locate(self, reference_image, description, step_index=0, timeout=25.0, retry_interval=2.0, fallback_click=None, min_interval=1.0):
        ai_cfg = self._get_ai_config()
        provider = ai_cfg["provider"]
        self._check_vision_support(provider)
        region = self.region if self.region else {"left": 0, "top": 0, "width": 1368, "height": 912}
        region_left = region.get("left", 0)
        region_top = region.get("top", 0)
        start_time = time.time()
        last_api_call = 0
        error_count = 0
        attempt = 0
        prompt = self._build_locate_prompt(description)
        while time.time() - start_time < timeout:
            attempt += 1
            try:
                from core.capture import ScreenCapture
                capture = ScreenCapture()
                screenshot = capture.capture_region(region)
            except Exception as e:
                return {"found": False, "x": 0, "y": 0, "score": 0.0, "action": "none", "message": f"Loi chup man hinh: {e}"}
            if not self._frame_changed(step_index, screenshot):
                remaining = timeout - (time.time() - start_time)
                if remaining > 0:
                    time.sleep(min(retry_interval, remaining))
                continue
            now = time.time()
            if now - last_api_call < min_interval:
                time.sleep(min_interval - (now - last_api_call))
            # QUAN TRONG: ve luoi len CHINH anh da resize (anh ma AI nhin thay),
            # roi chia toa do AI tra ve cho scale de ra pixel that cua vung.
            grid_img, scale = self._prepare_image(screenshot.copy())
            grid_img = self._add_grid_overlay(grid_img, step_index)
            ref_img, _ = self._prepare_image(reference_image.copy())
            try:
                if self.debug:
                    os.makedirs(self.debug_dir, exist_ok=True)
                    debug_ref = os.path.join(self.debug_dir, f"step_{step_index:02d}_reference.jpg")
                    ref_img.save(debug_ref, "JPEG")
                reply = self._call_ai_vision(prompt, ref_img, grid_img, provider=provider)
                last_api_call = time.time()
                error_count = 0
                if self.debug:
                    self.last_reply[step_index] = reply
                    debug_reply = os.path.join(self.debug_dir, f"step_{step_index:02d}_reply.txt")
                    with open(debug_reply, "w", encoding="utf-8") as f:
                        f.write(reply)
            except Exception as e:
                error_count += 1
                if error_count > ai_cfg["retry_on_error"]:
                    return {"found": False, "x": 0, "y": 0, "score": 0.0, "action": "none",
                            "message": f"Loi goi AI (thu {error_count} lan): {e}"}
                print(f"      [WARN] Loi goi AI (thu {error_count}) -> thu lai: {e}")
                remaining = timeout - (time.time() - start_time)
                if remaining > 0:
                    time.sleep(min(retry_interval, remaining))
                continue
            result = self._parse_locate_response(reply, description)
            if result["found"]:
                rx = int(round(result["x"] / scale))
                ry = int(round(result["y"] / scale))
                result["relative_x"] = rx
                result["relative_y"] = ry
                result["x"] = region_left + rx
                result["y"] = region_top + ry
                result["scale"] = round(scale, 4)
                if self.debug:
                    debug_marked = os.path.join(self.debug_dir, f"step_{step_index:02d}_found.jpg")
                    marked = screenshot.copy()
                    draw = ImageDraw.Draw(marked)
                    draw.ellipse([rx - 8, ry - 8, rx + 8, ry + 8], outline="red", width=3)
                    draw.ellipse([rx - 4, ry - 4, rx + 4, ry + 4], outline="yellow", width=2)
                    marked.save(debug_marked, "JPEG")
                return result
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                time.sleep(min(retry_interval, remaining))
        if fallback_click and "point" in fallback_click:
            px, py = fallback_click["point"]
            rw = region.get("width", 1368)
            rh = region.get("height", 912)
            return {
                "found": False,
                "x": region_left + int(px * rw),
                "y": region_top + int(py * rh),
                "relative_x": int(px * rw),
                "relative_y": int(py * rh),
                "score": 0.0,
                "action": "fallback_click",
                "message": f"TIMEOUT {timeout}s -> fallback {px*100:.0f}%, {py*100:.0f}%"
            }
        return {"found": False, "x": 0, "y": 0, "score": 0.0, "action": "none", "message": f"TIMEOUT {timeout}s - khong thay '{description}'"}

    @staticmethod
    def _match_template_best(img_gray, tmpl_gray, scales=None):
        """Tim vi tri match tot nhat giua template va anh (multi-scale).

        Returns:
            (score, x, y, w, h) - toa do goc tren TRAI cua vung match tren anh.
        """
        import cv2
        if scales is None:
            # Template co the thay doi ca vi tri va kich thuoc khi vung chup
            # doi do phan giai/DPI. Vi du 1x can scale ~1.7 tren anh 720x1600.
            scales = [round(x, 3) for x in np.arange(0.4, 2.51, 0.05)]
        ih, iw = img_gray.shape[:2]
        best = (0.0, 0, 0, 0, 0)
        for s in scales:
            tw, th = int(tmpl_gray.shape[1] * s), int(tmpl_gray.shape[0] * s)
            if tw < 8 or th < 8 or tw > iw or th > ih:
                continue
            interp = cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR
            resized = cv2.resize(tmpl_gray, (tw, th), interpolation=interp)
            res = cv2.matchTemplate(img_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, mx, _, loc = cv2.minMaxLoc(res)
            if mx > best[0]:
                best = (float(mx), loc[0], loc[1], tw, th)
        return best

    def locate_template(self, template_image, description="", step_index=0,
                        timeout=25.0, retry_interval=1.0, threshold=0.75,
                        fallback_click=None, scales=None):
        """Tim nut/doi tuong bang template matching (OpenCV) - KHONG goi API.

        Multi-scale (0.4 - 1.6) de khong phu thuoc do phan giai region.
        Tra ve toa do pixel TUYET DOI (da cong region left/top).
        """
        import cv2
        region = self.region if self.region else {"left": 0, "top": 0, "width": 1368, "height": 912}
        region_left = region.get("left", 0)
        region_top = region.get("top", 0)
        if self.mock:
            rw, rh = region.get("width", 1368), region.get("height", 912)
            return {"found": True, "x": region_left + rw // 2, "y": region_top + rh // 2,
                    "relative_x": rw // 2, "relative_y": rh // 2, "score": 0.9,
                    "action": "click", "message": "mock template"}
        tmpl_gray = cv2.cvtColor(np.array(template_image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        start_time = time.time()
        last_best = 0.0
        while time.time() - start_time < timeout:
            try:
                from core.capture import ScreenCapture
                screenshot = ScreenCapture().capture_region(region)
            except Exception as e:
                return {"found": False, "x": 0, "y": 0, "score": 0.0, "action": "none",
                        "message": f"Loi chup man hinh: {e}"}
            img_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
            score, mx, my, mw, mh = self._match_template_best(img_gray, tmpl_gray, scales=scales)
            last_best = max(last_best, score)
            if score >= threshold:
                rx = mx + mw // 2
                ry = my + mh // 2
                if self.debug:
                    os.makedirs(self.debug_dir, exist_ok=True)
                    marked = screenshot.copy()
                    draw = ImageDraw.Draw(marked)
                    draw.ellipse([rx - 8, ry - 8, rx + 8, ry + 8], outline="red", width=3)
                    draw.ellipse([rx - 4, ry - 4, rx + 4, ry + 4], outline="yellow", width=2)
                    marked.save(os.path.join(self.debug_dir, f"step_{step_index:02d}_found.jpg"), "JPEG")
                return {"found": True, "x": region_left + rx, "y": region_top + ry,
                        "relative_x": rx, "relative_y": ry, "score": round(score, 3),
                        "action": "click",
                        "message": f"template match {score:.2f} >= {threshold}"}
            remaining = timeout - (time.time() - start_time)
            if remaining > 0:
                time.sleep(min(retry_interval, remaining))
        if fallback_click and "point" in fallback_click:
            px, py = fallback_click["point"]
            rw = region.get("width", 1368)
            rh = region.get("height", 912)
            return {"found": False, "x": region_left + int(px * rw),
                    "y": region_top + int(py * rh),
                    "relative_x": int(px * rw), "relative_y": int(py * rh),
                    "score": round(last_best, 3), "action": "fallback_click",
                    "message": f"TIMEOUT {timeout}s (best {last_best:.2f}) -> fallback {px*100:.0f}%, {py*100:.0f}%"}
        return {"found": False, "x": 0, "y": 0, "score": round(last_best, 3),
                "action": "none",
                "message": f"TIMEOUT {timeout}s - khong thay template (best {last_best:.2f} < {threshold})"}

    def count_template(self, template_image, threshold=0.75):
        """Dem so vi tri xuat hien template tren man hinh - KHONG goi API."""
        import cv2
        if self.mock:
            return {"count": 2, "found": True, "message": "mock"}
        try:
            from core.capture import ScreenCapture
            region = self.region if self.region else {"left": 0, "top": 0, "width": 1368, "height": 912}
            screenshot = ScreenCapture().capture_region(region)
        except Exception as e:
            return {"count": 0, "found": False, "message": f"Loi chup: {e}"}
        img_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        tmpl_gray = cv2.cvtColor(np.array(template_image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        ih, iw = img_gray.shape[:2]
        best_res, best_s, best_score = None, 1.0, 0.0
        for s in [round(x, 3) for x in np.arange(0.4, 1.61, 0.04)]:
            tw, th = int(tmpl_gray.shape[1] * s), int(tmpl_gray.shape[0] * s)
            if tw < 8 or th < 8 or tw > iw or th > ih:
                continue
            resized = cv2.resize(tmpl_gray, (tw, th),
                                 interpolation=cv2.INTER_AREA if s < 1 else cv2.INTER_LINEAR)
            res = cv2.matchTemplate(img_gray, resized, cv2.TM_CCOEFF_NORMED)
            _, mx, _, _ = cv2.minMaxLoc(res)
            if mx > best_score:
                best_score, best_res, best_s = mx, res, s
        if best_res is None:
            return {"count": 0, "found": False, "message": "template qua lon"}
        binary = (best_res >= threshold).astype(np.uint8)
        n, _ = cv2.connectedComponents(binary)
        count = int(max(n - 1, 0))
        return {"count": count, "found": True,
                "message": f"dem {count} (score {best_score:.2f}, scale {best_s})"}

    def verify_same(self, reference_image, step_index=0):
        """So sanh man hinh hien tai voi anh mau bang template matching cuc bo.
        KHONG goi API. Lay cac strip ngang cua anh mau, match multi-scale,
        lay diem cao nhat - khong phu thuoc status bar/thanh dieu huong."""
        import cv2
        if self.mock:
            return {"same": True, "confidence": 0.99, "message": "mock"}
        try:
            from core.capture import ScreenCapture
            region = self.region if self.region else {"left": 0, "top": 0, "width": 1368, "height": 912}
            screenshot = ScreenCapture().capture_region(region)
        except Exception as e:
            return {"same": False, "confidence": 0.0, "message": f"Loi chup man hinh: {e}"}
        img_gray = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2GRAY)
        ref_gray = cv2.cvtColor(np.array(reference_image.convert("RGB")), cv2.COLOR_RGB2GRAY)
        h, w = ref_gray.shape[:2]
        best = 0.0
        for top_frac in (0.15, 0.30, 0.45, 0.60):
            strip = ref_gray[int(h * top_frac):int(h * (top_frac + 0.25)), :]
            score, _, _, _, _ = self._match_template_best(img_gray, strip)
            best = max(best, score)
        same = best >= 0.75
        return {"same": same, "confidence": round(best, 3),
                "message": f"strip-match {best:.2f} -> {'giong' if same else 'khac'}"}

    def _build_locate_prompt(self, description):
        return (
            "Ban la AI tim vi tri can click tren man hinh.\n\n"
            "**Anh mau** (ben trai): Mau tuyen chon, can tim tren man hinh thuc te.\n"
            "**Man hinh thuc te** (ben phai): Screenshot hien tai, da ve LUOI TOA DO mau xanh.\n\n"
            "**LUOI TOA DO:**\n"
            "- Cac so ben TRAI (truc Y): toa do Y cua diem do (pixel)\n"
            "- Cac so ben TREN (truc X): toa do X cua diem do (pixel)\n"
            "- Mo khoang luoi: 144px theo x, 256px theo y\n\n"
            f"**Yeu cau:**\nTim diem toa do (x, y) can click de thuc hien:\n\"{description}\"\n\n"
            "**Quy tac:**\n"
            "1. CHI CLICK VAO NUT/ICON/TEXT, KHONG CLICK VUNG VIDEO PREVIEW\n"
            "2. Tim vung MAU SAC GIONG ANH MAU nhat\n"
            "3. Tra ve toa do TAM cua nut/doi tuong can click\n"
            "4. Tra ve CHINH XAC theo luoi toa do\n\n"
            "**Dinh dang (CHI TRA JSON, KHONG MARKDOWN):**\n"
            '{ "found": true, "x": 526, "y": 845, "action": "click", "confidence": 0.95 }\n\n'
            "Neu khong tim thay:\n"
            '{ "found": false, "action": "wait", "message": "Chua thay nut" }'
        )

    def _build_verify_prompt(self):
        return (
            "Ban la AI so sanh 2 anh man hinh game.\n\n"
            "**Anh mau** (ben trai): Man hinh mong muon.\n"
            "**Man hinh thuc te** (ben phai): Screenshot hien tai.\n\n"
            "Xem 2 anh co giong nhau khong (cung noi dung, cung trang thai).\n\n"
            "**Dinh dang (CHI TRA JSON):**\n"
            '{ "same": true, "confidence": 0.95 }\n\n'
            "Hoac:\n"
            '{ "same": false, "confidence": 0.1 }'
        )

    def _call_ai_vision(self, prompt, *images, provider=None):
        if self.mock:
            return self._mock_ai_vision(prompt)
        if provider is None:
            provider = self._get_ai_config()["provider"]
        if provider == "gemini":
            return self._call_gemini_vision(prompt, *images)
        elif provider in ("openai", "claude"):
            return self._call_openai_vision(prompt, *images)
        elif provider == "ollama":
            return self._call_ollama_vision(prompt, *images)
        else:
            raise ValueError(f"Provider '{provider}' khong ho tro vision")

    def _mock_ai_vision(self, prompt):
        """Tra ve ket qua gia de test workflow khong can API key"""
        self.mock_counter += 1
        low = prompt.lower()
        if '"same"' in low or "so sanh 2 anh" in low:
            return '{"same": true, "confidence": 0.9}'
        if '"count"' in low or "dem so item" in low:
            return '{"count": 2, "found": true, "message": "mock: 2 item"}'
        if '"found"' in low:
            region = self.region or {"left": 0, "top": 0, "width": 1368, "height": 912}
            rw = region.get("width", 1368)
            rh = region.get("height", 912)
            # Toa do phai tinh theo ANH DA RESIZE vi locate() se chia cho scale
            max_size = self._get_ai_config()["max_size"]
            scale = min(1.0, max_size / max(rw, rh)) if max_size else 1.0
            x = int(rw * scale * 0.5)
            y = int(rh * scale * 0.5)
            return ('{"found": true, "x": %d, "y": %d, "action": "click", '
                    '"confidence": 0.9, "message": "mock"}' % (x, y))
        return '{"found": false, "action": "wait", "message": "mock unknown prompt"}'

    def _get_api_key(self, provider):
        """Lay API key cho DUNG provider vision (khong phu thuoc brain).
        Uu tien: config['ai']['api_key'] (CLI --api-key) -> providers[provider].api_key
        -> bien moi truong -> brain."""
        ai_key = (self.config.get("ai") or {}).get("api_key", "")
        if ai_key:
            return ai_key
        prov_cfg = (self.config.get("providers") or {}).get(provider) or {}
        api_key = prov_cfg.get("api_key", "") or prov_cfg.get("apiKey", "")
        if api_key:
            return api_key
        env_map = {
            "gemini": "GEMINI_API_KEY",
            "openai": "OPENAI_API_KEY",
            "claude": "ANTHROPIC_API_KEY",
        }
        env_var = env_map.get(provider, "")
        if env_var:
            api_key = os.environ.get(env_var, "")
        if api_key:
            return api_key
        if self.brain is not None:
            try:
                return self.brain._get_provider_config().get("api_key", "") or ""
            except Exception:
                return ""
        return ""

    def _call_gemini_vision(self, prompt, *images):
        from google import genai
        ai_cfg = self._get_ai_config()
        api_key = self._get_api_key("gemini")
        model = ai_cfg["model"] or self.VISION_DEFAULT_MODEL["gemini"]
        if not api_key:
            raise AIConnectionError(
                "Gemini API key not found. Dat providers.gemini.api_key trong config.json "
                "hoac bien moi truong GEMINI_API_KEY"
            )
        client = genai.Client(api_key=api_key)
        contents = [prompt]
        for img in images:
            contents.append(img)
        response = client.models.generate_content(model=model, contents=contents)
        return response.text.strip()

    def _call_openai_vision(self, prompt, *images):
        from openai import OpenAI
        import httpx
        ai_cfg = self._get_ai_config()
        provider = ai_cfg["provider"]
        api_key = self._get_api_key(provider)
        if not api_key:
            raise AIConnectionError(
                f"{provider.title()} API key not found. Dat providers.{provider}.api_key "
                f"trong config.json hoac bien moi truong tuong ung"
            )
        if provider == "openai":
            base_url = self.config.get("openai_url", "https://api.openai.com/v1")
        elif provider == "claude":
            base_url = self.config.get("claude_url", "https://api.anthropic.com/v1")
        else:
            base_url = self.config.get("api_url", "https://api.openai.com/v1")
        model = ai_cfg["model"] or self.VISION_DEFAULT_MODEL.get(provider, "gpt-4o-mini")
        client = OpenAI(base_url=base_url, api_key=api_key, http_client=httpx.Client(timeout=httpx.Timeout(30.0, connect=10.0)))
        content = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = self._pil_to_base64(img)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}], max_tokens=200)
        return response.choices[0].message.content.strip()

    def _call_ollama_vision(self, prompt, *images):
        from openai import OpenAI
        import httpx
        ai_cfg = self._get_ai_config()
        base_url = self.config.get("ollama_url", "http://localhost:11434/v1")
        model = ai_cfg["model"] or self.VISION_DEFAULT_MODEL["ollama"]
        client = OpenAI(base_url=base_url, api_key="ollama", http_client=httpx.Client(timeout=httpx.Timeout(60.0, connect=5.0)))
        content = [{"type": "text", "text": prompt}]
        for img in images:
            b64 = self._pil_to_base64(img)
            content.append({"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{b64}"}})
        response = client.chat.completions.create(model=model, messages=[{"role": "user", "content": content}], max_tokens=200)
        return response.choices[0].message.content.strip()

    def _parse_locate_response(self, reply, description):
        reply = reply.strip()
        if reply.startswith("```"):
            lines = reply.split("\n")
            reply = "\n".join(lines[1:])
            if reply.endswith("```"):
                reply = reply[:-3]
            reply = reply.strip()
            if reply.lower().startswith("json"):
                reply = reply[4:].strip()
        try:
            data = json.loads(reply)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*\}', reply, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    data = {"found": False, "action": "wait", "message": f"Parse error"}
            else:
                data = {"found": False, "action": "wait", "message": f"No JSON"}
        if "found" not in data:
            data["found"] = False
        if data.get("found"):
            data.setdefault("x", 0)
            data.setdefault("y", 0)
            data.setdefault("action", "click")
            data.setdefault("confidence", 0.5)
        else:
            data.setdefault("action", "wait")
            data.setdefault("message", description)
        return data

    def _parse_verify_response(self, reply):
        reply = reply.strip()
        if reply.startswith("```"):
            lines = reply.split("\n")
            reply = "\n".join(lines[1:])
            if reply.endswith("```"):
                reply = reply[:-3]
            reply = reply.strip()
            if reply.lower().startswith("json"):
                reply = reply[4:].strip()
        try:
            data = json.loads(reply)
        except json.JSONDecodeError:
            json_match = re.search(r'\{[^{}]*\}', reply, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    data = {"same": False, "confidence": 0.0}
            else:
                data = {"same": False, "confidence": 0.0}
        data.setdefault("same", False)
        data.setdefault("confidence", 0.0)
        data.setdefault("message", "")
        return data

    def count_selected_items(self, description, expected_count, step_index=0):
        prompt = (
            f"Ban la AI dem so item duoc chon tren man hinh.\n\n"
            f"**Man hinh thuc te** (ben phai): Screenshot, da ve LUOI TOA DO mau xanh.\n\n"
            f"**LUOI TOA DO:**\n"
            f"- Cac so ben TRAI (truc Y): toa do Y\n"
            f"- Cac so ben TREN (truc X): toa do X\n"
            f"- Mo khoang luoi: 144px theo x, 256px theo y\n\n"
            f"**Yeu cau:**\n"
            f"1. Dem so item ({description}) dang duoc CHON\n"
            f"2. Tra ve SO LUONG chinh xac\n\n"
            '{ "count": 2, "found": true, "message": "Thay 2" }\n\n'
            'Hoac:\n'
            '{ "count": 0, "found": false, "message": "Chua co" }'
        )
        try:
            from core.capture import ScreenCapture
            capture = ScreenCapture()
            region = self.region if self.region else {"left": 0, "top": 0, "width": 1368, "height": 912}
            screenshot = capture.capture_region(region)
        except Exception as e:
            return {"count": 0, "found": False, "message": f"Loi chup: {e}"}
        grid_img = self._add_grid_overlay(self._prepare_image(screenshot.copy())[0], step_index)
        try:
            reply = self._call_ai_vision(prompt, grid_img)
        except Exception as e:
            return {"count": 0, "found": False, "message": f"Loi AI: {e}"}
        try:
            reply = reply.strip()
            if reply.startswith("```"):
                lines = reply.split("\n")
                reply = "\n".join(lines[1:])
                if reply.endswith("```"):
                    reply = reply[:-3]
                reply = reply.strip()
                if reply.lower().startswith("json"):
                    reply = reply[4:].strip()
            data = json.loads(reply)
        except (json.JSONDecodeError, ValueError):
            json_match = re.search(r'\{[^{}]*\}', reply, re.DOTALL)
            if json_match:
                try:
                    data = json.loads(json_match.group())
                except json.JSONDecodeError:
                    data = {"count": 0, "found": False}
            else:
                data = {"count": 0, "found": False}
        data.setdefault("count", 0)
        data.setdefault("found", False)
        data.setdefault("message", "")
        return data
