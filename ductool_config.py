from __future__ import annotations
import json, os, sys
from pathlib import Path
from urllib.parse import urlparse, parse_qs

APP_NAME = "DUCTOOL"

def app_root() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent

CONFIG_PATH = Path(r"C:\duc\config.json")

DEFAULT_CONFIG = {
    "general": {
        "chrome_profile_root": r"C:\\duc\\FacebookChrome",
        "chrome_slots": 4,
        "chrome_port_base": 9310,
        "selected_chrome": 1
    },
    "chrome": {
        "executable": "",
        "profile_root": r"C:\\duc\\FacebookChrome",
        "ports": {"1": 9311, "2": 9312, "3": 9313, "4": 9314},
        "proxies": {"1": "", "2": "", "3": "", "4": ""},
        "default_slot": 1
    },
    "facebook": {
        "sheet_url": "https://docs.google.com/spreadsheets/d/13liLEM_fsEfuR2KJDYX-vdKRuAqZv-Dlg2RaAHGC6zY/edit?gid=0#gid=0",
        "sheet_csv_url": "https://docs.google.com/spreadsheets/d/13liLEM_fsEfuR2KJDYX-vdKRuAqZv-Dlg2RaAHGC6zY/export?format=csv&gid=0",
        "content_dir": r"C:\\duc\\baiviet",
        "image_dir": r"C:\\duc\\baiviet\\anhdangbai",
        "content_files": [],
        "txt_files": [],
        "image_files": [],
        "content_count": 10,
        "groups_per_content": 10,
        "image_count": 20,
        "delay_min": 5,
        "delay_max": 12,
        "delay_between_groups_seconds": 10,
        "delay_after_text_seconds": 1,
        "delay_after_images_seconds": 1,
        "delay_before_post_seconds": 1,
        "rest_every": 0,
        "rest_seconds": 0,
        "jobs_before_break": 10,
        "break_after_jobs_seconds": 120,
        "break_after_cycle_seconds": 600,
        "google_login_wait_seconds": 120,
        "log_file": "",
        "state_path": r"C:\\duc\\fb_post_state.json",
        "log_path": r"C:\\duc\\fb_post_log.csv",
        "crash_log_path": r"C:\\duc\\fb_tool_crash.log",
        "failed_groups_path": r"C:\\duc\\fb_group_loi.txt"
    },
    "collector": {
        "sheet_url": "",
        "fields": "123",
        "tab_count": 3
    },
    "joiner": {
        "sheet_url": "",
        "tab_count": 1,
        "delay_seconds": 10
    },
    "messenger": {
        "notification_provider": "telegram",
        "zalo_bot_token": "",
        "zalo_chat_id": "",
        "telegram_bot_token": "",
        "telegram_chat_id": "",
        "poll_seconds": 30,
        "max_age_minutes": 30,
        "max_message_age_minutes": 30,
        "dedupe_hours": 24,
        "inbox_url": "https://www.messenger.com/",
        "requests_url": "https://www.messenger.com/requests/",
        "spam_url": "https://www.messenger.com/requests/spam/",
        "notifications_url": "https://www.facebook.com/notifications",
        "check_notifications": True,
        "dashboard_port": 8000
    },
    "license": {
        "api_url": ""
    }
}

def _merge(default, saved):
    if isinstance(default, dict):
        out = dict(default)
        if isinstance(saved, dict):
            for k, v in saved.items():
                out[k] = _merge(default.get(k), v) if k in default else v
        return out
    return saved if saved is not None else default

def load_config():
    if CONFIG_PATH.exists():
        try:
            saved = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
        except Exception:
            saved = {}
    else:
        saved = {}
    cfg = _merge(DEFAULT_CONFIG, saved)
    return cfg

def save_config(cfg):
    CONFIG_PATH.parent.mkdir(parents=True, exist_ok=True)
    content = json.dumps(cfg, ensure_ascii=False, indent=2)
    tmp = CONFIG_PATH.with_suffix(CONFIG_PATH.suffix + ".tmp")
    tmp.write_text(content, encoding="utf-8")
    try:
        tmp.replace(CONFIG_PATH)
    except Exception:
        CONFIG_PATH.write_text(content, encoding="utf-8")
        try:
            if tmp.exists():
                tmp.unlink()
        except Exception:
            pass

def ensure_config():
    if not CONFIG_PATH.exists():
        save_config(DEFAULT_CONFIG)
    return load_config()

def sheet_csv_from_edit_url(url: str) -> str:
    url = (url or "").strip()
    m = re_match = __import__('re').search(r"/spreadsheets/d/([^/]+)", url)
    if not m:
        return ""
    sid = m.group(1)
    parsed = urlparse(url)
    q = parse_qs(parsed.query)
    gid = (q.get('gid') or ['0'])[0]
    if 'gid=' in parsed.fragment:
        try: gid = parsed.fragment.split('gid=',1)[1].split('&',1)[0]
        except Exception: pass
    return f"https://docs.google.com/spreadsheets/d/{sid}/export?format=csv&gid={gid}"
