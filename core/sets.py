"""
sets.py - Quan ly cac BO thao tac (input sets)

Moi bo = 1 thu muc doc lap trong input/<ten>/
  - steps.json : mo ta cac buoc
  - images/    : anh do nguoi dung cung cap (1.jpg, 1x.png, ...)

Muc dich: chuyen doi qua lai giua bo cu va bo moi ma khong sua file chung,
khong gay conflict khi luu code.
"""

import os
import json
import shutil

# Thu muc goc chua "input"
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
INPUT_ROOT = os.path.join(BASE_DIR, "input")
LEGACY_IMAGE_DIR = os.path.join(BASE_DIR, "input_picture")
IMAGE_EXTS = (".png", ".jpg", ".jpeg", ".webp")


class SetError(Exception):
    """Loi lien quan den bo thao tac"""
    pass


def set_dir(set_name):
    """Duong dan thu muc cua 1 bo"""
    return os.path.join(INPUT_ROOT, set_name)


def images_dir(set_name):
    """Duong dan thu muc anh cua 1 bo"""
    return os.path.join(set_dir(set_name), "images")


def steps_path(set_name):
    """Duong dan steps.json cua 1 bo"""
    return os.path.join(set_dir(set_name), "steps.json")


def list_sets():
    """Liet ke ten cac bo co trong input/"""
    if not os.path.isdir(INPUT_ROOT):
        return []
    names = []
    for name in os.listdir(INPUT_ROOT):
        full = os.path.join(INPUT_ROOT, name)
        if not os.path.isdir(full):
            continue
        if name.startswith(".") or name.startswith("_"):
            continue
        if os.path.exists(os.path.join(full, "steps.json")) or os.path.isdir(
            os.path.join(full, "images")
        ):
            names.append(name)
    return sorted(names)


def set_exists(set_name):
    """Kiem tra 1 bo da ton tai chua"""
    return os.path.isdir(set_dir(set_name))


def search_dirs(set_name):
    """Thu tu tim anh: bo hien tai truoc, bo khac va input_picture/ sau"""
    dirs = []
    if set_name:
        dirs.append(images_dir(set_name))

    # Cac bo khac (de hinh dung chung)
    if os.path.isdir(INPUT_ROOT):
        for name in sorted(os.listdir(INPUT_ROOT)):
            if set_name and name == set_name:
                continue
            sub = os.path.join(INPUT_ROOT, name, "images")
            if os.path.isdir(sub):
                dirs.append(sub)

    # Anh goc cua project
    if os.path.isdir(LEGACY_IMAGE_DIR):
        dirs.append(LEGACY_IMAGE_DIR)
    return dirs


def resolve_image(name, set_name):
    """Tim file anh theo ten trong bo, neu khong co thi fallback ve bo khac

    Args:
        name: ten khong can extension, vi du "1", "1x"
        set_name: ten bo hien tai

    Returns:
        str|None: duong dan file tim thay, None neu khong co
    """
    if not name:
        return None
    # Ten da co san extension -> dung truc tiep
    if os.path.splitext(name)[1]:
        direct = name if os.path.isabs(name) else os.path.join(BASE_DIR, name)
        return direct if os.path.exists(direct) else None

    for folder in search_dirs(set_name):
        for ext in IMAGE_EXTS:
            path = os.path.join(folder, name + ext)
            if os.path.exists(path):
                return path
    return None


def load_steps(set_name):
    """Doc steps.json cua 1 bo"""
    path = steps_path(set_name)
    if not os.path.exists(path):
        raise SetError(f"Khong tim thay steps.json cua bo '{set_name}': {path}")
    with open(path, "r", encoding="utf-8-sig") as f:
        return json.load(f)


def save_steps(set_name, data):
    """Ghi steps.json cua 1 bo"""
    path = steps_path(set_name)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    return path


def create_set(set_name, from_set=None, workflow_dir=None):
    """Tao bo moi: thu muc images/ + steps.json

    Args:
        set_name: ten bo moi
        from_set: ten bo duoc copy (None = lay steps.json mau cua workflow)
        workflow_dir: thu muc workflow de lay steps.json mau

    Returns:
        str: duong dan thu muc bo vua tao
    """
    if not set_name:
        raise SetError("Ten bo rong")
    if set_exists(set_name):
        raise SetError(f"Bo '{set_name}' da ton tai")

    target = set_dir(set_name)
    os.makedirs(images_dir(set_name), exist_ok=True)

    if from_set and set_exists(from_set):
        shutil.copyfile(steps_path(from_set), steps_path(set_name))
    elif workflow_dir:
        src = os.path.join(workflow_dir, "steps.json")
        if os.path.exists(src):
            shutil.copyfile(src, steps_path(set_name))
        else:
            save_steps(set_name, {"name": set_name, "image_dir": "images",
                                 "repeat": 0, "steps": []})
    else:
        save_steps(set_name, {"name": set_name, "image_dir": "images",
                             "repeat": 0, "steps": []})
    return target


def seed_images(set_name, source_dir=None):
    """Copy anh tu input_picture/ sang bo

    Args:
        set_name: ten bo nhan anh
        source_dir: thu muc nguon, mac dinh input_picture/

    Returns:
        int: so file da copy
    """
    source = source_dir or LEGACY_IMAGE_DIR
    if not os.path.isdir(source):
        raise SetError(f"Khong tim thay thu muc anh nguon: {source}")

    os.makedirs(images_dir(set_name), exist_ok=True)
    copied = 0
    for name in sorted(os.listdir(source)):
        if not name.lower().endswith(IMAGE_EXTS):
            continue
        dst = os.path.join(images_dir(set_name), name)
        if not os.path.exists(dst):
            shutil.copyfile(os.path.join(source, name), dst)
            copied += 1
    return copied


def collect_used_images(steps):
    """Lay danh sach ten anh ma cac buoc can dung"""
    needed = []
    for step in steps:
        if not isinstance(step, dict):
            continue
        for key in ("template", "image", "until_template", "count_template"):
            name = step.get(key)
            if isinstance(name, str) and name and name not in needed:
                needed.append(name)
        # Anh dung cho action back_until: wait_for
        action = step.get("action") or {}
        if isinstance(action, dict):
            for key in ("wait_for", "template", "target"):
                name = action.get(key)
                if isinstance(name, str) and name and name not in needed:
                    needed.append(name)
    return needed


def check_set(set_name):
    """Kiem tra bo truoc khi chay: anh thieu, anh thua, steps sai cu phap

    Returns:
        dict: ket qua kiem tra
    """
    result = {
        "ok": False, "n_steps": 0, "missing": [], "unused": [],
        "present": [], "errors": [], "dir": set_dir(set_name),
    }

    if not set_exists(set_name):
        result["errors"].append(f"Khong ton tai bo '{set_name}'")
        return result
    if not os.path.exists(steps_path(set_name)):
        result["errors"].append("Thieu steps.json")
        return result

    try:
        with open(steps_path(set_name), "r", encoding="utf-8-sig") as f:
            data = json.load(f)
    except ValueError as e:
        result["errors"].append(f"steps.json sai cu phap JSON: {e}")
        return result

    steps = data.get("steps", [])
    result["n_steps"] = len(steps)
    if not steps:
        result["errors"].append("steps.json chua co buoc nao")
        return result

    for i, step in enumerate(steps, 1):
        if not isinstance(step, dict):
            result["errors"].append(f"Buoc {i} khong phai object")
            continue
        action_type = (step.get("action") or {}).get("type", "ai")
        if action_type == "ai" and not step.get("image") and not step.get("template"):
            result["errors"].append(
                f"Buoc {i}: action 'ai' can 'image' hoac 'template'")
        if not step.get("description"):
            result["errors"].append(f"Buoc {i}: thieu 'description'")
        threshold = step.get("threshold")
        if threshold is not None:
            try:
                val = float(threshold)
            except (TypeError, ValueError):
                result["errors"].append(f"Buoc {i}: 'threshold' khong phai so")
            else:
                if not (0 < val <= 1):
                    result["errors"].append(
                        f"Buoc {i}: 'threshold' phai trong (0, 1], "
                        f"dang la {threshold}")

    for name in collect_used_images(steps):
        if resolve_image(name, set_name):
            result["present"].append(name)
        else:
            result["missing"].append(name)

    own = images_dir(set_name)
    if os.path.isdir(own):
        for name in sorted(os.listdir(own)):
            if not name.lower().endswith(IMAGE_EXTS):
                continue
            if os.path.splitext(name)[0] not in collect_used_images(steps):
                result["unused"].append(name)

    result["ok"] = not result["errors"] and not result["missing"]
    return result


def print_check(set_name, result):
    """In ket qua kiem tra bo"""
    print("=" * 60)
    print(f"  [CHECK] Bo: {set_name}")
    print("=" * 60)
    print(f"  Thu muc: {result['dir']}")
    print(f"  So buoc: {result['n_steps']}")

    for err in result["errors"]:
        print(f"  [FAIL] {err}")
    if result["present"]:
        print(f"  [OK]   Du anh: {', '.join(result['present'])}")
    if result["missing"]:
        print(f"  [FAIL] Thieu anh: {', '.join(result['missing'])}")
        print(f"  [HINT] Them vao: {images_dir(set_name)}")
    if result["unused"]:
        print(f"  [WARN] Anh thua: {', '.join(result['unused'])}")

    print("=" * 60)
    if result["ok"]:
        print("  [OK] Bo nay san sang chay.")
    else:
        print("  [FAIL] Chua san sang. Sua lai roi chay --check lai.")
    print()
    return result["ok"]


def print_list():
    """In danh sach cac bo"""
    names = list_sets()
    print()
    if not names:
        print("  Chua co bo nao trong input/")
        print("  -> Tao bo moi: python play.py --workflow <ten> --new-set <ten bo>")
        return
    print("  Cac bo hien co:")
    for name in names:
        n_steps = "-"
        p = steps_path(name)
        if os.path.exists(p):
            try:
                with open(p, "r", encoding="utf-8-sig") as f:
                    n_steps = len(json.load(f).get("steps", []))
            except Exception:
                n_steps = "loi JSON"
        n_img = 0
        d = images_dir(name)
        if os.path.isdir(d):
            n_img = len([f for f in os.listdir(d) if f.lower().endswith(IMAGE_EXTS)])
        print(f"    - {name}: {n_steps} buoc, {n_img} anh")
    print()
