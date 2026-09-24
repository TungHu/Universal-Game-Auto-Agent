# -*- coding: utf-8 -*-
"""
play.py - Launcher DUY NHAT cho Universal Game Auto Agent
Usage:
    python play.py <game_name> [options]

Options:
    --select-region    Select game region manually
    --provider         AI provider (gemini/openai/ollama)
    --interval         Loop interval in seconds
    --model            AI model (e.g. gemini-2.0-flash, gpt-4o-mini, llama3.2)
"""

import sys
import os
import json
import time
import argparse

# Them thu muc hien tai vao path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from core.capture import ScreenCapture
from core.vision import GameVision
from core.brain import BaseBrain, AIConnectionError
from core.controller import GameController
from core.region_selector import RegionSelector


def print_banner():
    """In banner khoi dong"""
    print("=" * 60)
    print("  [GAME] Universal Game Auto Agent")
    print("  AI auto play games")
    print("=" * 60)


def print_step(step: str, status: str = "..."):
    """In trang thai buoc"""
    icons = {"done": "[OK]", "fail": "[FAIL]", "...": "[..]"}
    icon = icons.get(status, "[..]")
    print(f"  {icon} {step}")


def main():
    parser = argparse.ArgumentParser(
        description="Universal Game Auto Agent"
    )
    parser.add_argument("game", nargs="?", help="Game name (e.g. 2048)")
    parser.add_argument("--select-region", action="store_true",
                        help="Select game region manually")
    parser.add_argument("--provider",
                        choices=["gemini", "openai", "claude", "groq", "deepseek", "openrouter", "ollama"],
                        help="AI provider")
    parser.add_argument("--interval", type=float,
                        help="Loop interval in seconds")
    parser.add_argument("--model",
                        help="AI model (e.g. gemini-2.0-flash, gpt-4o-mini, llama3.2)")    
    parser.add_argument("--workflow", help="Workflow name (e.g. capcut_auto)")
    parser.add_argument("--dry-run", action="store_true",
                        help="Dry run: khong click, chi in hanh dong")
    parser.add_argument("--repeat", type=int, default=0,
                        help="So lan lap workflow (0 = vo han)")
    parser.add_argument("--list", action="store_true",
                        help="Liet ke cac workflow")
    parser.add_argument("--debug-ai", action="store_true",
                        help="Luu debug images + AI replies")
    parser.add_argument("--no-region-prompt", action="store_true",
                        help="Khong hoi chon vung, dung region.json")
    parser.add_argument("--region", default=None,
                        help="Region preset: fullscreen hoac path to region.json")
    parser.add_argument("--mock-ai", action="store_true",
                        help="Mock AI: khong goi API, tra ve ket qua gia (de test)")
    parser.add_argument("--api-key", default=None,
                        help="API key ghi de cho provider hien tai (khong luu vao file)")

    args = parser.parse_args()

    print_banner()

    if args.list:
        list_workflows()
        sys.exit(0)

    if args.workflow:
        run_workflow(args)
        sys.exit(0)

    if not args.game:
        print("\n  [FAIL] Thieu ten game. Dung: python play.py <game> [options]")
        print("  Hoac: python play.py --list\n")
        sys.exit(1)

    print(f"\n  Game: {args.game}")
    print()

    # --- Buoc 1: Xac dinh duong dan game ---
    game_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "games", f"game_{args.game}")
    if not os.path.exists(game_dir):
        print_step(f"Khong tim thay game '{args.game}'", "fail")
        print(f"\n  Cac game hien co:")
        games_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "games")
        if os.path.exists(games_dir):
            for g in os.listdir(games_dir):
                if g.startswith("game_"):
                    print(f"    - {g.replace('game_', '')}")
        print()
        sys.exit(1)

    # --- Buoc 2: Doc config ---
    config_path = os.path.join(game_dir, "config.json")
    if not os.path.exists(config_path):
        print_step(f"Khong tim thay {config_path}", "fail")
        sys.exit(1)

    with open(config_path, "r", encoding="utf-8-sig") as f:
        config = json.load(f)

    print_step("Da doc config.json", "done")

    # --- Buoc 3: Chon vung game ---
    region = RegionSelector.load_region(game_dir)

    if args.select_region or region is None:
        print_step("Chon vung game tren man hinh...")
        selector = RegionSelector()
        region = selector.select_region()

        if region is None:
            print_step("Nguoi dung da huy", "fail")
            sys.exit(1)

        RegionSelector.save_region(game_dir, region)
    else:
        print_step("Da doc vung game tu region.json", "done")

    # Luu region vao config de controller co the dung
    config["_region"] = region
    config["_game_dir"] = game_dir

    # --- Buoc 4: Override config tu CLI ---
    if args.provider:
        config["ai_provider"] = args.provider
    if args.interval:
        config["loop_interval"] = args.interval
    if args.model:
        config["model"] = args.model

    print(f"\n  [CFG] Cau hinh:")
    print(f"     AI Provider: {config.get('ai_provider', 'gemini')}")
    print(f"     Model:       {config.get('model', 'default')}")
    print(f"     Interval:    {config.get('loop_interval', 0.3)}s")
    print(f"     Vung game:   {region['width']}x{region['height']} "
          f"tai ({region['left']}, {region['top']})")
    print()

    # --- Buoc 5: Khoi tao cac module ---
    print_step("Khoi tao modules...")

    try:
        capture = ScreenCapture()
        vision = GameVision(config)
        brain = BaseBrain(config)
        controller = GameController(config)
    except Exception as e:
        print_step(f"Loi khoi tao: {e}", "fail")
        sys.exit(1)

    print_step("Tat ca modules da san sang", "done")
    print()

    # --- Buoc 6: Doc prompt ---
    prompt_path = os.path.join(game_dir, "prompt.txt")
    if not os.path.exists(prompt_path):
        print_step(f"Khong tim thay {prompt_path}", "fail")
        sys.exit(1)

    prompt_template = brain.load_prompt(prompt_path)
    print_step("Da doc prompt.txt", "done")
    print()

    # --- Buoc 7: Vong lap chinh ---
    print("=" * 60)
    print("  [START] BAT DAU CHOI!")
    print("  Nhan Ctrl+C de dung")
    print("=" * 60)
    print()

    loop_count = 0
    interval = config.get("loop_interval", 0.3)

    try:
        while True:
            loop_count += 1
            print(f"\n--- Luot {loop_count} ---")

            # 7a. Chup man hinh
            game_image = capture.capture_region(region)

            # 7b. Nhan dien board
            board_state = vision.analyze(game_image)
            print(f"  Board:\n{board_state}")

            # 7c. Format prompt
            prompt = brain.format_prompt(prompt_template, board_state)

            # 7d. AI suy nghi
            try:
                action = brain.think(prompt)
                print(f"  [AI] Quyet dinh: {action.upper()}")
            except AIConnectionError as e:
                print(f"  [FAIL] Loi AI: {e}")
                print("  [WAIT] Cho 5 giay roi thu lai...")
                time.sleep(5)
                continue
            except Exception as e:
                print(f"  [FAIL] Loi AI: {e}")
                break

            # 7e. Thuc thi hanh dong
            controller.act(action)

            # 7f. Cho
            time.sleep(interval)

    except KeyboardInterrupt:
        print("\n\n  [STOP] Da dung boi nguoi dung")
    except Exception as e:
        print(f"\n  [FAIL] Loi: {e}")
        import traceback
        traceback.print_exc()

    print("\n" + "=" * 60)
    print(f"  [SUM] Tong ket: {loop_count} luot choi")
    print("=" * 60)




def list_workflows():
    workflows_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows")
    if not os.path.exists(workflows_dir):
        print("  Khong co thu muc workflows")
        return
    workflows = []
    for d in os.listdir(workflows_dir):
        if d.startswith("workflow_") and os.path.isdir(os.path.join(workflows_dir, d)):
            steps_file = os.path.join(workflows_dir, d, "steps.json")
            if os.path.exists(steps_file):
                try:
                    with open(steps_file, "r", encoding="utf-8-sig") as f:
                        wf = json.load(f)
                    workflows.append((d.replace("workflow_", ""), wf))
                except Exception:
                    pass
    if not workflows:
        print("  Khong co workflow nao")
        return
    print("\n  Cac workflow hien co:")
    for name, wf in workflows:
        steps = wf.get("steps", [])
        repeat = wf.get("repeat", 0)
        print(f"    - {name}: {len(steps)} buoc, lap {'vo han' if repeat == 0 else repeat} lan")
    print()


def run_workflow(args):
    import json
    workflows_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "workflows")
    workflow_dir = os.path.join(workflows_dir, f"workflow_{args.workflow}")
    if not os.path.exists(workflow_dir):
        print(f"Khong tim thay workflow: {args.workflow}")
        print(f"  -> Kiem tra thu muc: {workflow_dir}")
        sys.exit(1)

    steps_path = os.path.join(workflow_dir, "steps.json")
    if not os.path.exists(steps_path):
        print(f"Khong tim thay {steps_path}")
        sys.exit(1)

    with open(steps_path, "r", encoding="utf-8-sig") as f:
        workflow_config = json.load(f)

    print("=" * 60)
    wf_name = workflow_config.get("name", args.workflow)
    print(f"  [WORKFLOW] {wf_name}")
    steps = workflow_config.get("steps", [])
    repeat = workflow_config.get("repeat", 0)
    if args.repeat:
        repeat = args.repeat
    print(f"  {len(steps)} buoc, lap {'vo han' if repeat == 0 else repeat} lan")
    print("=" * 60)

    base_dir = os.path.dirname(os.path.abspath(__file__))
    region_path = os.path.join(workflow_dir, "region.json")
    game_dir = workflow_dir

    # --- Buoc 0: Chon vung man hinh ---
    print()
    print("  [B0] CHON VUNG MAN HINH")
    print("  " + "-" * 50)

    region = None
    if args.region == "fullscreen":
        import mss
        with mss.mss() as sct:
            monitor = sct.monitors[1]
            region = dict(monitor)
        print(f"  Dung toan man hinh")
    elif args.region and os.path.exists(args.region):
        try:
            with open(args.region, "r", encoding="utf-8-sig") as f:
                region = json.load(f)
        except (OSError, ValueError) as e:
            print(f"  [FAIL] Khong doc duoc region '{args.region}': {e}")
            sys.exit(1)
        if not all(k in region for k in ("left", "top", "width", "height")):
            print(f"  [FAIL] {args.region} phai co left/top/width/height")
            sys.exit(1)
        print(f"  Dung region tu {args.region}")
    elif args.no_region_prompt and not args.select_region:
        print("  --no-region-prompt: dung region.json neu co")
        if os.path.exists(region_path):
            with open(region_path, "r", encoding="utf-8-sig") as f:
                region = json.load(f)
            print(f"  Da doc vung tu region.json")
        else:
            if args.mock_ai:
                import mss
                with mss.mss() as sct:
                    monitor = sct.monitors[1]
                    region = dict(monitor)
                print("  Khong co region.json -> dung toan man hinh (mock mode)")
            else:
                print(f"  [FAIL] Khong co {region_path}")
                print("  -> Bo --no-region-prompt de chon vung, hoac dung --region fullscreen")
                sys.exit(1)
    else:
        if args.mock_ai:
            import mss
            with mss.mss() as sct:
                monitor = sct.monitors[1]
                region = dict(monitor)
            print("  [MOCK] Bo qua GUI chon vung -> dung toan man hinh")
        else:
            selector = RegionSelector(save_path=region_path)
            print("  * Keo chuot de chon vung game")
            print("  * R = dung lai vung da luu")
            print("  * Enter = xac nhan")
            print("  * Esc = huy")
            region = selector.select_region()
            if region is None:
                print("  [FAIL] Nguoi dung da huy")
                sys.exit(1)
        rw = region["width"]
        rh = region["height"]
        rl = region["left"]
        rt = region["top"]
        print(f"  Da chon: {rw}x{rh} tai ({rl}, {rt})")

    # Validate region (luon thuc hien, ke ca doc tu file): width/height phai > 0
    if (not region or not isinstance(region, dict)
            or region.get("width", 0) <= 0 or region.get("height", 0) <= 0
            or not all(k in region for k in ("left", "top", "width", "height"))):
        print(f"  [FAIL] Region khong hop le (can left/top/width/height va width,height > 0): {region}")
        print("  -> Chon lai vung (bo --no-region-prompt) hoac sua region.json")
        sys.exit(1)

    # --- Khoi tao modules ---
    base_config = {
        "_region": region,
        "_game_dir": game_dir,
        "_base_dir": base_dir,
    }

    # Doc config.json cua workflow neu co
    wf_config_path = os.path.join(workflow_dir, "config.json")
    if os.path.exists(wf_config_path):
        with open(wf_config_path, "r", encoding="utf-8-sig") as f:
            wf_config = json.load(f)
        base_config.update(wf_config)

    # Merge workflow config
    base_config["steps"] = steps
    base_config["repeat"] = repeat
    base_config["image_dir"] = workflow_config.get("image_dir", "input_picture")

    # --- Ghep ai theo thu tu uu tien thap -> cao ---
    # 1) config.json (ai_provider/model)  2) steps.json ai block
    # 3) CLI --provider/--model/--api-key (uu tien cao nhat, ghi de TRUC TIEP)
    ai_cfg = dict(base_config.get("ai") or {})
    for k, v in (workflow_config.get("ai") or {}).items():
        ai_cfg.setdefault(k, v)

    if args.provider:
        ai_cfg["provider"] = args.provider
    if args.model:
        ai_cfg["model"] = args.model
    elif args.provider:
        # Provider doi -> lay model mac dinh cua provider do (config.json providers)
        # de trong -> AIVision se chon VISION_DEFAULT_MODEL
        ai_cfg["model"] = (base_config.get("providers") or {}).get(
            args.provider, {}).get("model", "")

    if args.api_key:
        ai_cfg["api_key"] = args.api_key
        prov_key = args.provider or ai_cfg.get("provider", "gemini")
        base_config.setdefault("providers", {}).setdefault(prov_key, {})
        base_config["providers"][prov_key]["api_key"] = args.api_key

    ai_cfg.setdefault("provider", base_config.get("ai_provider", "gemini"))
    ai_cfg.setdefault("model", base_config.get("model", ""))
    ai_cfg.setdefault("min_interval", 1.0)
    ai_cfg.setdefault("find_timeout", 25.0)
    ai_cfg.setdefault("find_retry_interval", 2.0)
    base_config["ai"] = ai_cfg

    # Giu top-level cho brain/compat
    base_config["ai_provider"] = ai_cfg["provider"]
    base_config["model"] = ai_cfg["model"]

    print(f"\n  [CFG] AI Provider: {ai_cfg['provider']}")
    print(f"  [CFG] Model: {ai_cfg['model'] or '(mac dinh theo provider)'}")
    if args.api_key:
        print(f"  [CFG] API key: nhan tu --api-key")
    if args.mock_ai:
        print("  [CFG] MOCK AI: bat (khong goi API)")
    if args.dry_run:
        print("  [CFG] DRY-RUN: bat (khong click/phim that)")

    from core.capture import ScreenCapture
    from core.brain import BaseBrain
    from core.controller import GameController
    from core.ai_vision import AIVision

    capture = ScreenCapture()
    brain = BaseBrain(base_config)
    controller = GameController(base_config)
    vision = AIVision(brain, base_config, region=region,
                      debug=args.debug_ai, mock=args.mock_ai)

    from core.workflow import WorkflowRunner
    runner = WorkflowRunner(
        base_config, vision, controller,
        debug=args.debug_ai, dry_run=args.dry_run, repeat=repeat
    )

    runner.run()


if __name__ == "__main__":
    main()