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
    parser.add_argument("game", help="Game name (e.g. 2048)")
    parser.add_argument("--select-region", action="store_true",
                        help="Select game region manually")
    parser.add_argument("--provider",
                        choices=["gemini", "openai", "claude", "groq", "deepseek", "openrouter", "ollama"],
                        help="AI provider")
    parser.add_argument("--interval", type=float,
                        help="Loop interval in seconds")
    parser.add_argument("--model",
                        help="AI model (e.g. gemini-2.0-flash, gpt-4o-mini, llama3.2)")

    args = parser.parse_args()

    print_banner()
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

    with open(config_path, "r", encoding="utf-8") as f:
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


if __name__ == "__main__":
    main()