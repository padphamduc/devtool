from pathlib import Path
import sys
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from ductool_config import load_config, save_config
from ductool_chrome import chrome_settings

def save_selection(number: int) -> None:
    cfg = load_config()
    slots = max(1, int(cfg.get("general", {}).get("chrome_slots", 4)))
    if not (1 <= number <= slots):
        raise ValueError(f"Chỉ chọn Chrome 1..{slots}.")
    cfg.setdefault("general", {})["selected_chrome"] = number
    save_config(cfg)

def load_selection() -> int:
    cfg = load_config()
    g = cfg.get("general", {})
    slots = max(1, int(g.get("chrome_slots", 4)))
    number = int(g.get("selected_chrome", 1))
    return number if 1 <= number <= slots else 1

def resolve_chrome():
    number = load_selection()
    _exe, _root, port, _proxy = chrome_settings(number)
    return number, port
