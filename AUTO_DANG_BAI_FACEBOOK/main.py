import shutil
import urllib.request
import subprocess
# -*- coding: utf-8 -*-
import csv
import io
import json
import os
import sys
import time
import traceback
from datetime import datetime
from pathlib import Path
from urllib.parse import urlparse

ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from ductool_config import load_config, sheet_csv_from_edit_url
from ductool_chrome import chrome_settings, find_chrome, proxy_args

from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

# ============================================================
# DUC TOOL - FACEBOOK GROUP POSTER v1.23 (STAGED POST DELAYS)
# ============================================================

SHEET_ID = "13liLEM_fsEfuR2KJDYX-vdKRuAqZv-Dlg2RaAHGC6zY"
SHEET_GID = "0"
SHEET_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/edit?gid={SHEET_GID}#gid={SHEET_GID}"
SHEET_CSV_URL = f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/export?format=csv&gid={SHEET_GID}"

DATA_ROOT = Path(r"C:\duc\FacebookChrome")
STATE_PATH = Path(r"C:\duc\fb_post_state.json")
LOG_PATH = Path(r"C:\duc\fb_post_log.csv")
CRASH_LOG_PATH = Path(r"C:\duc\fb_tool_crash.log")
FAILED_GROUPS_PATH = Path(r"C:\duc\fb_group_loi.txt")

BASE_DIR = Path(__file__).resolve().parent
CONTENT_DIR = Path(r"C:\duc\baiviet")
IMAGE_DIR = CONTENT_DIR / "anhdangbai"
CONTENT_COUNT = 10
GROUPS_PER_CONTENT = 10

SLOT_COUNT = 4

# AUTO BATCH: không cần Enter để chuyển group.
DELAY_BETWEEN_GROUPS_SECONDS = 10
DELAY_AFTER_TEXT_SECONDS = 1
DELAY_AFTER_IMAGES_SECONDS = 1
DELAY_BEFORE_POST_SECONDS = 1
JOBS_BEFORE_BREAK = 10
BREAK_AFTER_JOBS_SECONDS = 120
BREAK_AFTER_CYCLE_SECONDS = 600
PREPARE_RETRIES = 1
GOOGLE_LOGIN_WAIT_SECONDS = 120


# Runtime settings from DUCTOOL/config.json.
def reload_facebook_config():
    global _CFG, _GEN, _FB, DATA_ROOT, SLOT_COUNT, STATE_PATH, LOG_PATH
    global CRASH_LOG_PATH, FAILED_GROUPS_PATH, CONTENT_DIR, IMAGE_DIR
    global CONTENT_FILES, CONTENT_COUNT, GROUPS_PER_CONTENT, IMAGE_FILES, IMAGE_COUNT
    global SHEET_URL, SHEET_CSV_URL, DELAY_MIN, DELAY_MAX, DELAY_BETWEEN_GROUPS_SECONDS
    global DELAY_AFTER_TEXT_SECONDS, DELAY_AFTER_IMAGES_SECONDS, DELAY_BEFORE_POST_SECONDS
    global JOBS_BEFORE_BREAK, BREAK_AFTER_JOBS_SECONDS, BREAK_AFTER_CYCLE_SECONDS, GOOGLE_LOGIN_WAIT_SECONDS

    _CFG = load_config()
    _GEN = _CFG.get("general", {})
    _FB = _CFG.get("facebook", {})

    DATA_ROOT = Path(_CFG.get("chrome", {}).get("profile_root") or _GEN.get("chrome_profile_root", r"C:\duc\FacebookChrome"))
    SLOT_COUNT = max(1, int(_GEN.get("chrome_slots", 4)))
    STATE_PATH = Path(_FB.get("state_path", r"C:\duc\fb_post_state.json"))
    LOG_PATH = Path(_FB.get("log_file") or _FB.get("log_path", r"C:\duc\fb_post_log.csv"))
    CRASH_LOG_PATH = Path(_FB.get("crash_log_path", r"C:\duc\fb_tool_crash.log"))
    FAILED_GROUPS_PATH = Path(_FB.get("failed_groups_path", r"C:\duc\fb_group_loi.txt"))
    CONTENT_DIR = Path(_FB.get("content_dir", r"C:\duc\baiviet"))
    IMAGE_DIR = Path(_FB.get("image_dir", r"C:\duc\baiviet\anhdangbai"))

    raw_content_files = _FB.get("content_files") or _FB.get("txt_files") or []
    CONTENT_FILES = [Path(x) for x in raw_content_files if str(x).strip()]
    CONTENT_COUNT = len(CONTENT_FILES) if CONTENT_FILES else max(1, int(_FB.get("content_count", 10)))
    GROUPS_PER_CONTENT = max(1, int(_FB.get("groups_per_content", 10)))

    IMAGE_FILES = [Path(x) for x in _FB.get("image_files", []) if str(x).strip()]
    IMAGE_COUNT = len(IMAGE_FILES) if IMAGE_FILES else max(1, int(_FB.get("image_count", 20)))

    SHEET_URL = str(_FB.get("sheet_url", "")).strip()
    SHEET_CSV_URL = str(_FB.get("sheet_csv_url", "")).strip() or sheet_csv_from_edit_url(SHEET_URL)

    DELAY_MIN = max(0.0, float(_FB.get("delay_min", _FB.get("delay_between_groups_seconds", 5.0))))
    DELAY_MAX = max(DELAY_MIN, float(_FB.get("delay_max", DELAY_MIN)))
    DELAY_BETWEEN_GROUPS_SECONDS = DELAY_MIN

    DELAY_AFTER_TEXT_SECONDS = max(0.0, float(_FB.get("delay_after_text_seconds", 1.0)))
    DELAY_AFTER_IMAGES_SECONDS = max(0.0, float(_FB.get("delay_after_images_seconds", 1.0)))
    DELAY_BEFORE_POST_SECONDS = max(0.0, float(_FB.get("delay_before_post_seconds", 1.0)))

    JOBS_BEFORE_BREAK = max(0, int(_FB.get("rest_every", _FB.get("jobs_before_break", 0))))
    BREAK_AFTER_JOBS_SECONDS = max(0.0, float(_FB.get("rest_seconds", _FB.get("break_after_jobs_seconds", 0.0))))
    BREAK_AFTER_CYCLE_SECONDS = max(0.0, float(_FB.get("break_after_cycle_seconds", 600.0)))
    GOOGLE_LOGIN_WAIT_SECONDS = max(10, int(_FB.get("google_login_wait_seconds", 120)))

reload_facebook_config()

# XPath do bạn cung cấp - dùng làm fallback.
X_CREATE_POST = "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[4]/div/div/div/div[2]/div/div/div/div[1]/div/div/div/div[1]/div"
X_CREATE_POST_ALT = "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[4]/div/div/div[2]/div/div/div/div[1]/div/div/div/div[1]/div"
X_CREATE_POST_ALT2 = "/html/body/div[1]/div/div[1]/div/div[3]/div/div/div[1]/div[1]/div[4]/div/div/div[2]/div/div/div/div[1]/div/div/div/div[1]/div/div[1]/span"
X_TEXT = "/html/body/div[1]/div/div[1]/div/div[4]/div/div[4]/div[1]/div/div[2]/div/div/div/div/div[1]/form/div/div[1]/div/div/div/div[2]/div[1]/div[1]/div[1]/div[1]/div/div/div[1]/p"
X_PHOTO = "/html/body/div[1]/div/div[1]/div/div[4]/div/div[4]/div[1]/div/div[2]/div/div/div/div/div[1]/form/div/div[1]/div/div/div/div[3]/div[1]/div[2]/div[1]/div/span/div/div/div[1]/div/div/div[1]/img"
X_POST = "/html/body/div[1]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div/div[1]/form/div/div[1]/div/div/div/div[3]/div[3]/div/div/div"
X_POST_ALT = r'//*[@id="mount_0_0_CU"]/div/div[1]/div/div[4]/div/div/div[1]/div/div[2]/div/div/div/div/div[1]/form/div/div[1]/div/div/div/div[3]/div[3]/div/div/div'

BANNER = "DUC TOOL • FACEBOOK GROUP POSTER"

SUPPORTED_IMAGES = {".jpg", ".jpeg", ".png", ".webp", ".gif"}

# Console theme: màu chỉ để hiển thị, không ảnh hưởng logic.
C_RESET = "\033[0m"
C_DIM = "\033[2m"
C_BOLD = "\033[1m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"
C_CYAN = "\033[96m"

def enable_console_colors():
    try:
        if os.name == "nt":
            os.system("")
    except Exception:
        pass

UI_WIDTH = 82

def _fit_ui(text, width=UI_WIDTH - 4):
    text = str(text or "").replace("\n", " ")
    return text if len(text) <= width else text[: max(0, width - 3)] + "..."

def ui_header(subtitle=""):
    width = UI_WIDTH
    print(C_CYAN + "╔" + "═" * width + "╗" + C_RESET)
    title = "DUC TOOL • FACEBOOK GROUP POSTER"
    print(C_CYAN + "║" + C_RESET + C_BOLD + f"{title:^{width}}" + C_RESET + C_CYAN + "║" + C_RESET)
    if subtitle:
        print(C_CYAN + "╠" + "═" * width + "╣" + C_RESET)
        print(C_CYAN + "║" + C_RESET + C_DIM + f"{_fit_ui(subtitle, width):^{width}}" + C_RESET + C_CYAN + "║" + C_RESET)
    print(C_CYAN + "╚" + "═" * width + "╝" + C_RESET)

def ui_box(title, lines, color=C_CYAN):
    width = UI_WIDTH
    title_text = f" {title} "
    side = max(0, width - len(title_text))
    left = side // 2
    right = side - left
    print(color + "╔" + "═" * left + title_text + "═" * right + "╗" + C_RESET)
    for line in lines:
        shown = _fit_ui(line, width - 2)
        print(color + "║" + C_RESET + f" {shown:<{width-1}}" + color + "║" + C_RESET)
    print(color + "╚" + "═" * width + "╝" + C_RESET)

def ui_ok(text):
    ui_box("THÀNH CÔNG", [f"✓ {text}"], C_GREEN)

def ui_warn(text):
    ui_box("THÔNG BÁO", [f"! {text}"], C_YELLOW)

def ui_error(text):
    ui_box("THẤT BẠI", [f"✕ {text}"], C_RED)

def ui_post_result(content_file, group_name, result_text=None):
    """Chỉ hiển thị job đã xử lý, không kết luận Thành Công/Thất Bại."""
    current_time = datetime.now().strftime("%H:%M:%S")

    def cut(value, width):
        value = str(value or "")
        if len(value) <= width:
            return value
        if width <= 3:
            return value[:width]
        return value[:width - 3] + "..."

    w_time = 10
    w_content = 18
    w_group = 42

    top = "╔" + "═" * w_time + "╦" + "═" * w_content + "╦" + "═" * w_group + "╗"
    sep = "╠" + "═" * w_time + "╬" + "═" * w_content + "╬" + "═" * w_group + "╣"
    bot = "╚" + "═" * w_time + "╩" + "═" * w_content + "╩" + "═" * w_group + "╝"

    header = (
        "║"
        + "Thời Gian".center(w_time)
        + "║"
        + "Nội Dung".center(w_content)
        + "║"
        + "Tên Nhóm".center(w_group)
        + "║"
    )
    row = (
        "║"
        + current_time.center(w_time)
        + "║"
        + cut(content_file, w_content).ljust(w_content)
        + "║"
        + cut(group_name, w_group).ljust(w_group)
        + "║"
    )

    print(C_CYAN + top + C_RESET)
    print(C_CYAN + header + C_RESET)
    print(C_CYAN + sep + C_RESET)
    print(row)
    print(C_CYAN + bot + C_RESET)

def write_crash_log(exc):
    try:
        CRASH_LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
        with CRASH_LOG_PATH.open("a", encoding="utf-8") as f:
            f.write("\n" + "=" * 80 + "\n")
            f.write(now_text() + "\n")
            f.write("".join(traceback.format_exception(type(exc), exc, exc.__traceback__)))
    except Exception:
        pass


def clear():
    os.system("cls" if os.name == "nt" else "clear")

def now_text():
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")

def canonical_group_url(url):
    try:
        u = urlparse((url or "").strip())
        host = (u.hostname or "").lower()
        if host != "facebook.com" and not host.endswith(".facebook.com"):
            return ""
        parts = [p for p in u.path.split("/") if p]
        if len(parts) < 2 or parts[0].lower() != "groups":
            return ""
        key = parts[1].strip()
        if not key:
            return ""
        return f"https://www.facebook.com/groups/{key}/"
    except Exception:
        return ""

def ensure_dirs():
    DATA_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    CONTENT_DIR.mkdir(parents=True, exist_ok=True)
    IMAGE_DIR.mkdir(parents=True, exist_ok=True)

    # Tạo file mặc định nếu không dùng danh sách content_files tùy chỉnh.
    if not CONTENT_FILES:
        for i in range(1, CONTENT_COUNT + 1):
            text_file = CONTENT_DIR / f"dangbai{i}.txt"
            if not text_file.exists():
                text_file.write_text("", encoding="utf-8")

    for i in range(1, SLOT_COUNT + 1):
        (DATA_ROOT / f"Chrome_{i}").mkdir(parents=True, exist_ok=True)

def choose_slot():
    """Tự dùng Chrome mặc định từ cấu hình chung, không hỏi 1/2/3/4."""
    try:
        cfg = load_config()
        return int(cfg.get("general", {}).get("selected_chrome", 1))
    except Exception:
        return 1

def content_slot_for_group_position(position):
    """Mỗi 10 nhóm đổi 1 nội dung; sau 100 nhóm quay lại dangbai1.txt."""
    if position < 1:
        return None
    block_index = (position - 1) // GROUPS_PER_CONTENT
    slot = (block_index % CONTENT_COUNT) + 1
    return slot

def load_content_slot(slot):
    if CONTENT_FILES:
        idx = (slot - 1) % len(CONTENT_FILES)
        text_file = CONTENT_FILES[idx]
    else:
        text_file = CONTENT_DIR / f"dangbai{slot}.txt"

    text = ""
    if text_file.exists():
        text = text_file.read_text(encoding="utf-8-sig").strip()

    if IMAGE_FILES:
        images = [str(p.resolve()) for p in IMAGE_FILES if p.exists() and p.suffix.lower() in SUPPORTED_IMAGES]
    else:
        images = []
        for i in range(1, IMAGE_COUNT + 1):
            found = None
            for ext in (".png", ".jpg", ".jpeg", ".webp", ".gif"):
                candidate = IMAGE_DIR / f"{i}{ext}"
                if candidate.exists():
                    found = candidate
                    break
            if found:
                images.append(str(found.resolve()))
    return text_file, text, images

def has_any_content():
    for slot in range(1, CONTENT_COUNT + 1):
        _, text, images = load_content_slot(slot)
        if text or images:
            return True
    return False

def count_content_characters(text):
    # Đếm ký tự của nội dung sau khi bỏ khoảng trắng ở đầu/cuối.
    return len((text or "").strip())

def count_images_in_folder():
    """Đếm số ảnh đăng bài theo bộ 1.png -> 20.png."""
    try:
        return sum(1 for i in range(1, IMAGE_COUNT + 1) if (IMAGE_DIR / f"{i}.png").exists())
    except Exception:
        return 0

def print_content_check():
    counts = []
    for slot in range(1, CONTENT_COUNT + 1):
        tfile, text, _ = load_content_slot(slot)
        name = Path(tfile).name if tfile else f"dangbai{slot}.txt"
        counts.append((name, count_content_characters(text)))

    lines = [
        f"{name} : {cnt} chữ"
        for name, cnt in counts
    ]
    lines.append(f"Ảnh đăng bài : {len(IMAGE_FILES)} file" if IMAGE_FILES else f"Ảnh trong folder : {count_images_in_folder()} file")
    ui_box("KIỂM TRA NỘI DUNG", lines, C_CYAN)

def default_state():
    return {
        "cycle": 1,
        "posted_current_cycle": {},
        "history": [],
        "last_updated": None
    }

def load_state():
    if not STATE_PATH.exists():
        return default_state()
    try:
        data = json.loads(STATE_PATH.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            return default_state()
        data.setdefault("cycle", 1)
        data.setdefault("posted_current_cycle", {})
        data.setdefault("history", [])
        return data
    except Exception:
        return default_state()

def save_state(state):
    state["last_updated"] = now_text()
    tmp = STATE_PATH.with_suffix(".tmp")
    backup = STATE_PATH.with_suffix(".bak")
    payload = json.dumps(state, ensure_ascii=False, indent=2)
    tmp.write_text(payload, encoding="utf-8")
    try:
        if STATE_PATH.exists():
            backup.write_text(STATE_PATH.read_text(encoding="utf-8"), encoding="utf-8")
    except Exception:
        pass
    tmp.replace(STATE_PATH)

def append_log(status, group, content_file=""):
    """Ghi lịch sử ngắn gọn: Thời gian | Nội dung | Tên nhóm | Link nhóm | Kết quả."""
    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)

    # Nếu đang tồn tại log định dạng cũ, đổi tên để không trộn cột.
    if LOG_PATH.exists():
        try:
            first_line = LOG_PATH.read_text(encoding="utf-8-sig", errors="ignore").splitlines()[0]
            if first_line and "Thời gian" not in first_line:
                legacy = LOG_PATH.with_name("fb_post_log_legacy.csv")
                if not legacy.exists():
                    LOG_PATH.replace(legacy)
        except Exception:
            pass

    exists = LOG_PATH.exists()
    result_text = "Thành Công" if status == "SUCCESS" else "Thất Bại"
    content_name = Path(str(content_file)).name if content_file else ""

    with LOG_PATH.open("a", encoding="utf-8-sig", newline="") as f:
        w = csv.writer(f, delimiter="|")
        if not exists:
            w.writerow(["Thời gian", "Nội dung", "Tên Nhóm", "Link Nhóm", "Kết Quả"])
        w.writerow([
            now_text(),
            content_name,
            group.get("name", ""),
            group.get("url", ""),
            result_text,
        ])

def note_failed_group(group, reason="NO_CREATE_POST", content_file=""):
    """Ghi nhóm lỗi dạng ngắn để người dùng kiểm tra lại sau."""
    try:
        FAILED_GROUPS_PATH.parent.mkdir(parents=True, exist_ok=True)
        name = (group.get("name") or "Không rõ tên nhóm").strip()
        url = (group.get("url") or "").strip()
        content_name = Path(str(content_file)).name if content_file else ""
        line = f"{now_text()} | {content_name} | {name} | {url} | Thất Bại ({reason})"
        with FAILED_GROUPS_PATH.open("a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass

def looks_like_member_count(value):
    v = (value or "").strip().lower().replace(",", "").replace(".", "")
    if not v:
        return False
    words = ("member", "members", "thành viên", "thanh vien", "k thành viên", "k members")
    if any(w in v for w in words):
        return True
    compact = v.replace(" ", "")
    if compact.isdigit():
        return True
    if compact.endswith(("k", "m")):
        try:
            float(compact[:-1])
            return True
        except Exception:
            pass
    return False

def parse_groups_csv(text):
    """Đọc link group ở bất kỳ cột nào trong mỗi dòng của Google Sheet."""
    rows = []
    seen = set()

    reader = csv.reader(io.StringIO(text))
    for raw in reader:
        if not raw:
            continue

        url = ""
        url_index = None
        for i, cell in enumerate(raw):
            candidate = canonical_group_url((cell or "").strip())
            if candidate:
                url = candidate
                url_index = i
                break

        if not url or url in seen:
            continue

        # Tìm tên nhóm linh hoạt. Nếu ô sau URL trông giống số thành viên,
        # ưu tiên ô chữ gần URL (kể cả nằm trước URL).
        name = ""
        members = ""
        cells = [(i, (cell or "").strip()) for i, cell in enumerate(raw) if i != url_index and (cell or "").strip()]

        if url_index is not None and url_index + 1 < len(raw):
            after = (raw[url_index + 1] or "").strip()
            if after and not looks_like_member_count(after):
                name = after
            elif after:
                members = after

        if not name:
            # Ưu tiên ô không phải số thành viên, gần cột URL nhất.
            candidates = [(i, value) for i, value in cells if not looks_like_member_count(value)]
            if candidates:
                candidates.sort(key=lambda item: abs(item[0] - (url_index or 0)))
                name = candidates[0][1]

        if not members:
            for _, value in cells:
                if looks_like_member_count(value):
                    members = value
                    break

        seen.add(url)
        rows.append({
            "url": url,
            "name": name or url,
            "members": members
        })

    return rows

def fetch_groups_from_sheet(context):
    def try_fetch():
        try:
            resp = context.request.get(SHEET_CSV_URL, timeout=30000)
            if resp.ok:
                groups = parse_groups_csv(resp.text())
                if groups:
                    return groups
        except Exception:
            pass
        return None

    for _ in range(3):
        groups = try_fetch()
        if groups:
            return groups
        time.sleep(1)

    # Nếu chưa đăng nhập Google, mở Sheet và tự polling; không cần Enter.
    ui_warn("Đang chờ đăng nhập Google...")
    page = context.new_page()
    try:
        page.goto(SHEET_URL, wait_until="domcontentloaded", timeout=60000)
        deadline = time.time() + GOOGLE_LOGIN_WAIT_SECONDS
        while time.time() < deadline:
            groups = try_fetch()
            if groups:
                return groups
            page.wait_for_timeout(5000)
    finally:
        page.close()

    return None

def click_first_visible(page, selectors, timeout_each=2500):
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                target = loc.filter(visible=True) if hasattr(loc, "filter") else loc
                loc.first.click(timeout=timeout_each)
                return True
        except Exception:
            continue
    return False

def open_create_post(page):
    selectors = [
        'div[role="button"]:has-text("Viết gì đó")',
        'div[role="button"]:has-text("Tạo bài viết")',
        'span:has-text("Viết gì đó")',
        'text="Viết gì đó..."',
        f'xpath={X_CREATE_POST}',
        f'xpath={X_CREATE_POST_ALT}',
        f'xpath={X_CREATE_POST_ALT2}',
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                loc.first.click(timeout=5000)
                page.wait_for_timeout(1200)
                return True
        except Exception:
            pass

    return False

def fill_post_text(page, text):
    if not text:
        return True

    selectors = [
        'div[role="dialog"] div[role="textbox"][contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        f'xpath={X_TEXT}',
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0:
                target = loc.last
                target.click(timeout=4000)
                try:
                    target.fill(text)
                except Exception:
                    page.keyboard.insert_text(text)
                return True
        except Exception:
            pass

    return False

def attach_images(page, images):
    if not images:
        return True

    # Cách 1: input[type=file] có sẵn.
    try:
        inputs = page.locator('input[type="file"]')
        if inputs.count() > 0:
            inputs.last.set_input_files(images)
            page.wait_for_timeout(1800)
            return True
    except Exception:
        pass

    # Cách 2: click nút ảnh và bắt file chooser.
    photo_selectors = [
        'div[role="button"][aria-label*="Ảnh"]',
        'div[role="button"][aria-label*="Photo"]',
        f'xpath={X_PHOTO}',
    ]

    for selector in photo_selectors:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue

            with page.expect_file_chooser(timeout=5000) as fc_info:
                loc.first.click()
            fc = fc_info.value
            fc.set_files(images)
            page.wait_for_timeout(1800)
            return True
        except Exception:
            continue

    return False

def dialog_still_open(page):
    try:
        return page.locator('div[role="dialog"]').count() > 0
    except Exception:
        return False

def composer_is_open(page):
    selectors = [
        'div[role="dialog"] div[role="textbox"][contenteditable="true"]',
        f'xpath={X_TEXT}',
    ]
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() > 0 and loc.first.is_visible():
                return True
        except Exception:
            pass
    return False

def close_composer_after_post(page):
    """Sau khi đăng thành công, cố đóng sạch composer/modal trước khi sang group khác."""
    try:
        page.wait_for_timeout(2000)
    except Exception:
        pass

    if not composer_is_open(page) and not dialog_still_open(page):
        return True

    # Cách 1: ESC thường đóng composer/modal nhanh nhất.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
        if not composer_is_open(page) and not dialog_still_open(page):
            return True
    except Exception:
        pass

    # Cách 2: thử các nút Đóng / Close / X trong dialog.
    selectors = [
        'div[role="dialog"] div[aria-label="Đóng"][role="button"]',
        'div[role="dialog"] div[aria-label="Close"][role="button"]',
        'div[role="dialog"] [aria-label="Đóng"]',
        'div[role="dialog"] [aria-label="Close"]',
        'div[role="dialog"] div[role="button"]:has(svg)',
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue
            # Ưu tiên nút gần đầu/cuối dialog; thử từ cuối trước.
            for target in (loc.last, loc.first):
                try:
                    target.click(timeout=2500)
                    page.wait_for_timeout(800)
                    if not composer_is_open(page) and not dialog_still_open(page):
                        return True
                except Exception:
                    pass
        except Exception:
            pass

    # Cách 3: ESC thêm lần nữa sau khi Facebook đổi trạng thái modal.
    try:
        page.keyboard.press("Escape")
        page.wait_for_timeout(800)
    except Exception:
        pass

    return not composer_is_open(page) and not dialog_still_open(page)


def click_post_and_verify(page):
    """Bấm Đăng và xác minh composer đã đóng trước khi ghi SUCCESS."""
    selectors = [
        f'xpath={X_POST_ALT}',
        f'xpath={X_POST}',
        'div[role="dialog"] div[role="button"]:has-text("Đăng")',
        'div[role="dialog"] [role="button"]:has-text("Post")',
    ]

    clicked = False
    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue
            target = loc.last
            try:
                if target.get_attribute("aria-disabled") == "true":
                    continue
            except Exception:
                pass
            target.scroll_into_view_if_needed(timeout=3000)
            # Thêm nhịp nghỉ cuối để Facebook kịp cập nhật composer trước khi Đăng.
            page.wait_for_timeout(DELAY_BEFORE_POST_SECONDS * 1000)
            target.click(timeout=5000)
            clicked = True
            break
        except Exception:
            continue

    if not clicked:
        return False

    deadline = time.time() + 25
    while time.time() < deadline:
        page.wait_for_timeout(700)
        current = page.url.lower()
        if "checkpoint" in current or "login" in current:
            return False
        if not composer_is_open(page):
            return True
        try:
            if page.locator(f'xpath={X_POST}').count() == 0:
                return True
        except Exception:
            pass

    return False

def ensure_work_page(context, page=None):
    try:
        if page is not None and not page.is_closed():
            return page
    except Exception:
        pass
    try:
        for candidate in context.pages:
            if not candidate.is_closed():
                return candidate
    except Exception:
        pass
    return context.new_page()

def composer_text_present(page, expected_text):
    """Kiểm tra phần text trong composer còn tồn tại trước khi bấm Đăng."""
    if not expected_text:
        return True

    expected = " ".join(expected_text.split()).strip()
    if not expected:
        return True

    selectors = [
        'div[role="dialog"] div[role="textbox"][contenteditable="true"]',
        'div[role="textbox"][contenteditable="true"]',
        f'xpath={X_TEXT}',
    ]

    for selector in selectors:
        try:
            loc = page.locator(selector)
            if loc.count() == 0:
                continue
            target = loc.last
            current = ""
            try:
                current = target.inner_text(timeout=3000)
            except Exception:
                try:
                    current = target.text_content(timeout=3000) or ""
                except Exception:
                    current = ""
            current = " ".join((current or "").split()).strip()
            if expected in current or current in expected:
                # Tránh coi chuỗi quá ngắn là hợp lệ nếu Facebook chỉ còn placeholder.
                if len(current) >= max(1, min(12, len(expected))):
                    return True
        except Exception:
            pass

    return False


def ensure_post_text_before_submit(page, post_text):
    """Nếu text bị mất sau khi upload ảnh thì tự điền lại một lần."""
    if not post_text:
        return True
    if composer_text_present(page, post_text):
        return True
    if not fill_post_text(page, post_text):
        return False
    page.wait_for_timeout(DELAY_AFTER_TEXT_SECONDS * 1000)
    return composer_text_present(page, post_text)


def prepare_one_group(page, group, post_text, images):
    # Nếu composer cũ còn sót từ group trước, cố đóng trước khi điều hướng.
    try:
        if composer_is_open(page) or dialog_still_open(page):
            close_composer_after_post(page)
    except Exception:
        pass

    try:
        page.goto(group["url"], wait_until="domcontentloaded", timeout=60000)
        page.wait_for_timeout(1800)
    except Exception:
        return "NAVIGATION_FAILED"

    current = page.url.lower()
    if "login" in current or "checkpoint" in current:
        return "AUTH_REQUIRED"

    if not open_create_post(page):
        return "NO_CREATE_POST"

    # Ảnh trước để tránh Facebook rebuild composer làm mất text.
    if images:
        if not attach_images(page, images):
            return "IMAGE_FAILED"
        page.wait_for_timeout(DELAY_AFTER_IMAGES_SECONDS * 1000)

    # Text điền sau cùng.
    if post_text:
        if not fill_post_text(page, post_text):
            return "TEXT_FAILED"
        page.wait_for_timeout(DELAY_AFTER_TEXT_SECONDS * 1000)

    return "READY"

def mark_success(state, group, content_file):
    state["posted_current_cycle"][group["url"]] = {
        "name": group.get("name", ""),
        "members": group.get("members", ""),
        "posted_at": now_text()
    }
    state["history"].append({
        "cycle": state["cycle"],
        "url": group["url"],
        "name": group.get("name", ""),
        "members": group.get("members", ""),
        "posted_at": now_text()
    })
    save_state(state)
    append_log("SUCCESS", group, content_file)

def wait_after_job(page, job_number, total_jobs):
    if job_number >= total_jobs:
        return

    # Tự động nạp cấu hình mới nhất từ config.json
    reload_facebook_config()

    # Nghỉ chặng: chỉ khi user cấu hình rest_every > 0 và rest_seconds > 0
    if JOBS_BEFORE_BREAK > 0 and BREAK_AFTER_JOBS_SECONDS > 0 and (job_number % JOBS_BEFORE_BREAK == 0):
        ui_warn(f"Đã đăng {job_number} nhóm -> Nghỉ chặng {int(BREAK_AFTER_JOBS_SECONDS)}s theo SETUP...")
        remain = int(BREAK_AFTER_JOBS_SECONDS)
        while remain > 0:
            sys.stdout.write(f"\r{C_YELLOW}⏸ Nghỉ theo cấu hình: còn {remain}s...{C_RESET}   ")
            sys.stdout.flush()
            step = min(remain, 1)
            page.wait_for_timeout(step * 1000)
            remain -= step
        print()
    else:
        # Delay ngẫu nhiên giữa các nhóm đúng theo min và max trong SETUP
        import random
        sec = round(random.uniform(DELAY_MIN, DELAY_MAX), 1) if DELAY_MAX > DELAY_MIN else round(DELAY_MIN, 1)
        if sec > 0:
            remain = sec
            while remain > 0:
                sys.stdout.write(f"\r{C_CYAN}⏳ Chờ {round(remain, 1)}s trước nhóm kế tiếp (delay {DELAY_MIN}-{DELAY_MAX}s)...{C_RESET}   ")
                sys.stdout.flush()
                step = min(remain, 1.0)
                page.wait_for_timeout(int(step * 1000))
                remain = round(remain - step, 1)
            print()


def run_cycle(context, groups, state):
    posted = set(state["posted_current_cycle"].keys())

    # Giữ vị trí gốc trong Google Sheet để resume không làm lệch dangbaiX.txt.
    remaining = [
        (position, group)
        for position, group in enumerate(groups, 1)
        if group["url"] not in posted
    ]

    if not remaining:
        posted_in_sheet = sum(1 for group in groups if group["url"] in posted)
        ui_ok(f"Đã lấy {len(groups)} nhóm - vòng hiện tại đã đăng {posted_in_sheet}/{len(groups)} nhóm.")
        return "DONE"

    page = ensure_work_page(context)

    for index, (position, group) in enumerate(remaining, 1):
        page = ensure_work_page(context, page)
        slot = content_slot_for_group_position(position)
        if slot is None:
            append_log("NO_CONTENT_SLOT", group, "")
            ui_post_result("-", group.get("name", ""), "Thất Bại")
            wait_after_job(page, index, len(remaining))
            continue

        text_file, post_text, images = load_content_slot(slot)
        if not post_text and not images:
            append_log("CONTENT_EMPTY", group, text_file.name)
            ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
            wait_after_job(page, index, len(remaining))
            continue

        prepared = False
        skip_group = False
        last_prepare_status = "PREPARE_FAILED"
        for attempt in range(PREPARE_RETRIES + 1):
            if attempt:
                try:
                    page.goto(group["url"], wait_until="domcontentloaded", timeout=60000)
                    page.wait_for_timeout(1200)
                except Exception:
                    pass

            prepare_status = prepare_one_group(page, group, post_text, images)
            last_prepare_status = prepare_status
            if prepare_status == "READY":
                prepared = True
                break

            # Không thấy khu vực/nút tạo bài: note lại và chuyển nhóm ngay.
            if prepare_status == "NO_CREATE_POST":
                append_log("NO_CREATE_POST", group, text_file.name)
                note_failed_group(group, "NO_CREATE_POST", text_file.name)
                ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
                skip_group = True
                break

            if prepare_status == "AUTH_REQUIRED":
                append_log("AUTH_REQUIRED", group, text_file.name)
                note_failed_group(group, "AUTH_REQUIRED", text_file.name)
                ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
                save_state(state)
                ui_warn("Facebook yêu cầu đăng nhập/checkpoint. Tool đã dừng.")
                return "QUIT"

        if not prepared and not skip_group:
            append_log(last_prepare_status, group, text_file.name)
            note_failed_group(group, last_prepare_status, text_file.name)
            ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
            skip_group = True

        if skip_group:
            wait_after_job(page, index, len(remaining))
            continue

        if prepared:
            if post_text and not ensure_post_text_before_submit(page, post_text):
                append_log("TEXT_VERIFY_FAILED", group, text_file.name)
                note_failed_group(group, "TEXT_VERIFY_FAILED", text_file.name)
                ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
                wait_after_job(page, index, len(remaining))
                continue

            ok = click_post_and_verify(page)
            if ok:
                mark_success(state, group, text_file.name)
                posted.add(group["url"])

                composer_closed = close_composer_after_post(page)
                if not composer_closed:
                    ui_warn("Composer chưa đóng hoàn toàn; tool sẽ tiếp tục làm sạch trước group kế tiếp.")

                ui_post_result(text_file.name, group.get("name", ""), "Thành Công")
            else:
                append_log("POST_FAILED", group, text_file.name)
                note_failed_group(group, "POST_FAILED", text_file.name)
                ui_post_result(text_file.name, group.get("name", ""), "Thất Bại")
                current = page.url.lower()
                if "checkpoint" in current or "login" in current:
                    save_state(state)
                    ui_warn("Facebook yêu cầu đăng nhập/checkpoint. Tool đã dừng.")
                    return "QUIT"

        wait_after_job(page, index, len(remaining))

    return "DONE"


def _chrome_exe(configured=""):
    return find_chrome(configured)

def _cdp_ready(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False

def _ensure_shared_chrome(slot, profile_dir):
    configured, profile_root, port, proxy = chrome_settings(slot)
    if _cdp_ready(port): return port
    profile_dir = profile_root / f"Chrome_{slot}"
    profile_dir.mkdir(parents=True, exist_ok=True)
    args=[_chrome_exe(configured), f"--user-data-dir={profile_dir}", f"--remote-debugging-port={port}", "--start-maximized", "--no-first-run", "--no-default-browser-check"]
    args.extend(proxy_args(slot, proxy))
    creationflags=0
    if os.name=="nt": creationflags=getattr(subprocess,"DETACHED_PROCESS",0x8)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0x200)
    subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,creationflags=creationflags,close_fds=True)
    for _ in range(40):
        if _cdp_ready(port): return port
        time.sleep(0.25)
    raise RuntimeError(f"Đã thử mở Chrome {slot} nhưng chưa thấy cổng CDP {port}. Hãy đóng Chrome profile này rồi chạy lại.")


def main():
    enable_console_colors()
    reload_facebook_config()
    ensure_dirs()
    slot = choose_slot()
    if slot is None:
        return

    clear()
    ui_header(f"Chrome {slot} • {GROUPS_PER_CONTENT} nhóm / 1 nội dung")
    print(f"\n{C_BOLD}TOOL Hoạt Động{C_RESET}")
    print_content_check()

    rest_info = (
        f"Sau mỗi {JOBS_BEFORE_BREAK} nhóm nghỉ {int(BREAK_AFTER_JOBS_SECONDS)}s"
        if (JOBS_BEFORE_BREAK > 0 and BREAK_AFTER_JOBS_SECONDS > 0)
        else "Tắt (không nghỉ chặng)"
    )
    ui_box(
        "THÔNG SỐ SETUP ĐANG ÁP DỤNG",
        [
            f"1 Bài đăng cho   : {GROUPS_PER_CONTENT} nhóm",
            f"Delay giữa nhóm  : {DELAY_MIN}s - {DELAY_MAX}s (ngẫu nhiên)",
            f"Nghỉ sau N nhóm  : {rest_info}",
            f"Nghỉ hết vòng    : {int(BREAK_AFTER_CYCLE_SECONDS)}s rồi tự chạy lại",
        ],
        C_CYAN,
    )

    if not has_any_content():
        ui_warn(r"Chưa có nội dung. Đã tạo sẵn C:\duc\baiviet\dangbai1.txt ... dangbai10.txt")
        ui_warn(r"Ảnh đặt tại C:\duc\baiviet\anhdangbai\1.png ... 20.png")
        input("\nNhấn Enter để thoát...")
        return

    profile_dir = DATA_ROOT / f"Chrome_{slot}"

    with sync_playwright() as p:
        context = None
        browser = None
        try:
            port = _ensure_shared_chrome(slot, profile_dir)
            browser = p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
            if not browser.contexts:
                raise RuntimeError("Chrome chung đã mở nhưng không có browser context.")
            context = browser.contexts[0]

            groups = fetch_groups_from_sheet(context)
            if not groups:
                ui_error("Không đọc được link nhóm từ Google Sheet.")
                ui_warn("Tool đã tìm link Facebook Group ở tất cả các cột nhưng không thấy link hợp lệ.")
                input("\nNhấn Enter để thoát...")
                return

            ui_ok(f"Đã lấy {len(groups)} nhóm từ Google Sheet.")
            state = load_state()

            while True:
                result = run_cycle(context=context, groups=groups, state=state)

                if result == "QUIT":
                    break

                # Hết một vòng: nghỉ 10 phút rồi tự chạy lại từ đầu danh sách.
                ui_warn("Đã hết 1 vòng - nghỉ 10 phút rồi tự chạy lại từ nhóm đầu.")
                time.sleep(BREAK_AFTER_CYCLE_SECONDS)

                state["cycle"] += 1
                state["posted_current_cycle"] = {}
                save_state(state)

                # Làm mới Sheet trước vòng kế tiếp; nếu lỗi thì dùng danh sách cũ.
                new_groups = fetch_groups_from_sheet(context)
                if new_groups:
                    groups = new_groups
                    ui_ok(f"Bắt đầu vòng {state['cycle']} - {len(groups)} nhóm.")
                else:
                    ui_warn(f"Không làm mới được Sheet, vòng mới dùng lại {len(groups)} nhóm hiện tại.")

        finally:
            # Không đóng context/browser chung. Khi tool Poster dừng,
            # Chrome vẫn mở để Messenger hoặc tool khác tiếp tục dùng.
            context = None
            browser = None

def guarded_main():
    try:
        main()
        return 0
    except KeyboardInterrupt:
        return 0
    except Exception as exc:
        write_crash_log(exc)
        ui_error("Tool gặp lỗi ngoài dự kiến.")
        print(r"Chi tiết đã lưu tại C:\duc\fb_tool_crash.log")
        try:
            input("Nhấn Enter để đóng...")
        except Exception:
            pass
        return 1

if __name__ == "__main__":
    raise SystemExit(guarded_main())
