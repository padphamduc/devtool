# -*- coding: utf-8 -*-
import re
import csv
import io
import asyncio
import os
import subprocess
import time
from pathlib import Path
from datetime import datetime
from urllib.request import Request, urlopen

from playwright.async_api import async_playwright

from ductool_config import load_config, save_config
from ductool_chrome import chrome_settings, find_chrome, proxy_args

DATA_ROOT = Path(r"C:\duc\FacebookChrome")
STATE_FILE = Path(r"C:\duc\fb_group_join_state.txt")
LOG_FILE = Path(r"C:\duc\fb_group_join_log.csv")
CRASH_LOG = Path(r"C:\duc\fb_group_join_crash.log")

PAGE_WAIT_MS = 1800

C_RESET = "\033[0m"
C_CYAN = "\033[96m"
C_GREEN = "\033[92m"
C_YELLOW = "\033[93m"
C_RED = "\033[91m"


def enable_colors():
    try:
        import os
        os.system("")
    except Exception:
        pass


def box(title, lines, color=C_CYAN, width=78):
    print()
    print(color + "╔" + "═" * width + "╗" + C_RESET)
    print(color + "║" + f" {title} ".center(width) + "║" + C_RESET)
    print(color + "╠" + "═" * width + "╣" + C_RESET)
    for line in lines:
        line = str(line)
        while len(line) > width:
            print(color + "║" + line[:width].ljust(width) + "║" + C_RESET)
            line = line[width:]
        print(color + "║" + line.center(width) + "║" + C_RESET)
    print(color + "╚" + "═" * width + "╝" + C_RESET)


def menu_box(title, items, footer=None, color=C_CYAN, width=78):
    print()
    print(color + "╔" + "═" * width + "╗" + C_RESET)
    print(color + "║" + f" {title} ".center(width) + "║" + C_RESET)
    print(color + "╠" + "═" * width + "╣" + C_RESET)
    for key, label in items:
        print(color + "║" + f"  [{key}] {label}".ljust(width) + "║" + C_RESET)
    if footer:
        print(color + "╠" + "─" * width + "╣" + C_RESET)
        for line in footer:
            print(color + "║" + str(line).center(width) + "║" + C_RESET)
    print(color + "╚" + "═" * width + "╝" + C_RESET)


def choose_profile():
    menu_box(
        "CHỌN CHROME PROFILE",
        [
            ("1", "Chrome_1"),
            ("2", "Chrome_2"),
            ("3", "Chrome_3"),
            ("4", "Chrome_4"),
        ],
        footer=["Profile cần đăng nhập Facebook"],
    )
    while True:
        v = input("Chọn Chrome [1-4]: ").strip()
        if v in {"1", "2", "3", "4"}:
            return int(v)
        print("Vui lòng chọn 1, 2, 3 hoặc 4.")



def selected_profile_from_ductool():
    try:
        cfg = load_config()
        value = int(cfg.get("general", {}).get("selected_chrome", 1))
        return max(1, min(4, value))
    except Exception:
        return 1


def _cdp_ready(port):
    try:
        from urllib.request import urlopen
        with urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_shared_chrome(slot):
    configured, profile_root, port, proxy = chrome_settings(slot)
    profile_dir = profile_root / f"Chrome_{slot}"

    if _cdp_ready(port):
        return port, profile_dir

    profile_dir.mkdir(parents=True, exist_ok=True)

    args = [
        find_chrome(configured),
        f"--user-data-dir={profile_dir}",
        f"--remote-debugging-port={port}",
        "--start-maximized",
        "--no-first-run",
        "--no-default-browser-check",
    ]
    args.extend(proxy_args(slot, proxy))

    creationflags = 0
    if os.name == "nt":
        creationflags = (
            getattr(subprocess, "DETACHED_PROCESS", 0x8)
            | getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0x200)
        )

    subprocess.Popen(
        args,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
        stdin=subprocess.DEVNULL,
        creationflags=creationflags,
        close_fds=True,
    )

    for _ in range(50):
        if _cdp_ready(port):
            return port, profile_dir
        time.sleep(0.2)

    raise RuntimeError(
        f"Đã thử mở Chrome {slot} nhưng chưa thấy cổng CDP {port}. "
        "Nếu profile này đang mở không có remote-debugging, hãy đóng Chrome đó rồi chạy lại."
    )


def choose_tab_count(default=1):
    default = max(1, min(10, default if default else 1))
    box(
        "CHỌN SỐ TAB THAM GIA NHÓM",
        [
            "Có thể chạy song song từ 1 đến 10 tab",
            f"Mặc định từ SETUP: {default} tab",
        ],
        C_YELLOW,
    )
    while True:
        raw = input(f"Số tab [1-10, Enter = {default}]: ").strip()
        if not raw:
            return default
        try:
            n = int(raw)
            if 1 <= n <= 10:
                return n
        except Exception:
            pass
        print("Vui lòng nhập số từ 1 đến 10.")


def choose_delay_seconds(default=10):
    default = max(0, int(default if default is not None else 10))
    box(
        "CHỌN DELAY GIỮA CÁC GROUP",
        [
            "Thời gian nghỉ giữa các lần tham gia group (giây)",
            f"Mặc định từ SETUP: {default}s",
        ],
        C_YELLOW,
    )
    while True:
        raw = input(f"Delay (giây) [Enter = {default}]: ").strip()
        if not raw:
            return default
        try:
            n = int(raw)
            if n >= 0:
                return n
        except Exception:
            pass
        print("Vui lòng nhập số nguyên giây (>= 0).")



def normalize_group_url(value):
    if not value:
        return None

    value = str(value).strip()
    if "facebook.com/groups/" not in value:
        return None

    m = re.search(
        r"https?://(?:www\.|m\.)?facebook\.com/groups/([^/?#]+)",
        value,
        re.I,
    )
    if not m:
        return None

    ident = m.group(1)
    if ident.lower() in {"feed", "discover", "joins", "create"}:
        return None

    return f"https://www.facebook.com/groups/{ident}/"


def sheet_to_csv_url(sheet_link):
    sheet_link = sheet_link.strip()
    m = re.search(r"/spreadsheets/d/([A-Za-z0-9_-]+)", sheet_link)
    if not m:
        raise ValueError("Link Google Sheet không hợp lệ.")

    sheet_id = m.group(1)
    gid_match = re.search(r"[#?&]gid=(\d+)", sheet_link)
    gid = gid_match.group(1) if gid_match else "0"

    return (
        f"https://docs.google.com/spreadsheets/d/{sheet_id}"
        f"/export?format=csv&gid={gid}"
    )


def fetch_group_links(sheet_link):
    csv_url = sheet_to_csv_url(sheet_link)
    text = ""

    # 1. Thử tải bằng httpx (hỗ trợ chuyển hướng redirect của Google tự động, không bị lỗi 400)
    try:
        import httpx
        resp = httpx.get(csv_url, follow_redirects=True, timeout=30.0, headers={
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        })
        if resp.status_code == 200 and resp.text:
            text = resp.text
    except Exception:
        pass

    # 2. Fallback sang curl nếu httpx gặp vấn đề mạng
    if not text:
        try:
            cmd = [
                "curl.exe", "-L", "-s", "-k",
                "-H", "User-Agent: Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
                csv_url
            ]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=30)
            if res.returncode == 0 and res.stdout:
                text = res.stdout.decode("utf-8-sig", errors="replace")
        except Exception:
            pass

    # 3. Fallback cuối cùng bằng urllib
    if not text:
        req = Request(csv_url, headers={"User-Agent": "Mozilla/5.0"})
        with urlopen(req, timeout=30) as response:
            text = response.read().decode("utf-8-sig", errors="replace")

    if not text:
        raise ValueError("Không thể lấy dữ liệu CSV từ trang tính.")

    rows = list(csv.reader(io.StringIO(text)))
    found = []
    seen = set()

    for row in rows:
        for cell in row:
            url = normalize_group_url(cell)
            if url and url not in seen:
                seen.add(url)
                found.append(url)
                break

    return found


def load_done():
    if not STATE_FILE.exists():
        return set()

    done = set()
    try:
        for line in STATE_FILE.read_text(encoding="utf-8").splitlines():
            url = normalize_group_url(line)
            if url:
                done.add(url)
    except Exception:
        pass
    return done


def append_line(path, line):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("a", encoding="utf-8") as f:
        f.write(line + "\n")


def append_log_row(url, status, note=""):
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    new_file = not LOG_FILE.exists()

    with LOG_FILE.open("a", encoding="utf-8-sig", newline="") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["Thời gian", "Link Group", "Trạng thái", "Ghi chú"])
        writer.writerow([
            datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            url,
            status,
            note,
        ])


async def is_login_block(page):
    u = page.url.lower()
    return "login" in u or "checkpoint" in u or "recover" in u


async def already_member(page):
    selectors = [
        'text="Đã tham gia"',
        'text="Joined"',
        '[aria-label="Đã tham gia"]',
        '[aria-label="Joined"]',
    ]

    for sel in selectors:
        try:
            if await page.locator(sel).count():
                return True
        except Exception:
            pass

    return False


async def click_join(page):
    selectors = [
        'div[role="button"]:has-text("Tham gia nhóm")',
        'div[role="button"]:has-text("Tham gia")',
        'button:has-text("Tham gia nhóm")',
        'button:has-text("Tham gia")',
        'div[role="button"]:has-text("Join group")',
        'div[role="button"]:has-text("Join Group")',
        'button:has-text("Join group")',
        'button:has-text("Join Group")',
        '[aria-label="Tham gia nhóm"]',
        '[aria-label="Join group"]',
        '[aria-label="Join Group"]',
    ]

    for sel in selectors:
        try:
            loc = page.locator(sel)
            count = await loc.count()
            for i in range(min(count, 5)):
                item = loc.nth(i)
                try:
                    if await item.is_visible(timeout=1000):
                        await item.click(timeout=4000)
                        return True
                except Exception:
                    pass
        except Exception:
            pass

    return False


async def needs_questions(page):
    await page.wait_for_timeout(1000)

    markers = [
        "Trả lời câu hỏi",
        "Answer questions",
        "Membership questions",
        "Câu hỏi thành viên",
        "Đồng ý với quy tắc",
        "Agree to group rules",
    ]

    try:
        body = await page.locator("body").inner_text(timeout=3000)
    except Exception:
        body = ""

    low = body.lower()
    return any(x.lower() in low for x in markers)


async def process_group(page, url):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(PAGE_WAIT_MS)
    except Exception as e:
        return "OPEN_FAILED", str(e)

    if await is_login_block(page):
        return "AUTH_REQUIRED", "Facebook yêu cầu đăng nhập/checkpoint."

    if await already_member(page):
        return "ALREADY_JOINED", ""

    if not await click_join(page):
        return "NO_JOIN_BUTTON", ""

    if await needs_questions(page):
        return "QUESTIONS_REQUIRED", "Group yêu cầu câu hỏi/quy tắc."

    await page.wait_for_timeout(1200)

    if await already_member(page):
        return "JOIN_REQUEST_SENT", ""

    try:
        body = (await page.locator("body").inner_text(timeout=3000)).lower()
    except Exception:
        body = ""

    pending_markers = [
        "đang chờ",
        "pending",
        "chờ phê duyệt",
        "request sent",
    ]

    if any(x in body for x in pending_markers):
        return "JOIN_REQUEST_SENT", ""

    return "JOIN_CLICKED", ""


async def run_multitab(context, pending, tab_count, delay_seconds=10):
    queue = asyncio.Queue()
    for idx, url in enumerate(pending):
        queue.put_nowait((idx, url))

    print_lock = asyncio.Lock()
    file_lock = asyncio.Lock()
    stop_event = asyncio.Event()
    completed = {"count": 0}

    async def save_result(url, status, note):
        async with file_lock:
            append_log_row(url, status, note)

            if status in {
                "ALREADY_JOINED",
                "JOIN_REQUEST_SENT",
                "JOIN_CLICKED",
                "QUESTIONS_REQUIRED",
                "NO_JOIN_BUTTON",
            }:
                append_line(STATE_FILE, url)

    # Giữ lại 1 tab có sẵn của persistent context làm worker đầu tiên.
    # Chỉ tạo thêm tab, không đóng tab cuối rồi tạo lại.
    existing_pages = [p for p in context.pages if not p.is_closed()]
    pages = []

    if existing_pages:
        pages.append(existing_pages[0])
        # Đóng các tab dư cũ, nhưng tuyệt đối giữ lại tab đầu.
        for extra in existing_pages[1:]:
            try:
                await extra.close()
            except Exception:
                pass
    else:
        # Trường hợp hiếm: context không có tab nào.
        try:
            pages.append(await context.new_page())
        except Exception as e:
            raise RuntimeError(f"Không thể tạo tab đầu tiên: {e}")

    desired_workers = max(1, min(tab_count, len(pending)))

    # Tạo thêm tab lần lượt. Nếu Chrome từ chối mở thêm, vẫn chạy với số tab đã tạo được.
    while len(pages) < desired_workers:
        try:
            pg = await context.new_page()
            pages.append(pg)
            # Chỉ là nhịp tạo tab để Chrome ổn định, không phải delay tham gia group.
            await asyncio.sleep(0.15)
        except Exception as e:
            async with print_lock:
                print(
                    f"Không mở thêm được tab {len(pages)+1}: {e}\n"
                    f"Tool sẽ tiếp tục với {len(pages)} tab đang hoạt động."
                )
            break

    async def worker(worker_no, page):
        try:
            while not stop_event.is_set():
                try:
                    idx, url = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                try:
                    status, note = await process_group(page, url)
                    await save_result(url, status, note)

                    async with print_lock:
                        completed["count"] += 1
                        print(
                            f"[Tab {worker_no}] "
                            f"[{completed['count']}/{len(pending)}] "
                            f"{status} | {url}"
                        )

                    if status == "AUTH_REQUIRED":
                        stop_event.set()

                except Exception as e:
                    await save_result(url, "ERROR", str(e))
                    async with print_lock:
                        completed["count"] += 1
                        print(
                            f"[Tab {worker_no}] "
                            f"[{completed['count']}/{len(pending)}] "
                            f"ERROR | {url}"
                        )

                finally:
                    queue.task_done()

                if delay_seconds > 0 and not queue.empty() and not stop_event.is_set():
                    async with print_lock:
                        print(
                            f"[Tab {worker_no}] Nghỉ {delay_seconds}s trước khi sang group tiếp theo..."
                        )
                    await asyncio.sleep(delay_seconds)

        finally:
            # Không đóng tab worker đầu tiên ở đây; context.close() sẽ xử lý cuối cùng.
            # Các tab phụ có thể đóng sau khi worker xong.
            if worker_no != 1:
                try:
                    await page.close()
                except Exception:
                    pass

    tasks = [
        asyncio.create_task(worker(i + 1, page))
        for i, page in enumerate(pages)
    ]

    await asyncio.gather(*tasks)

    return len(pages)


async def async_main():
    enable_colors()

    box(
        "DUC FB GROUP AUTO JOIN v1.4",
        [
            "Đọc link group từ Google Sheet",
            "Đa tab Async 1-10, tự giảm tab nếu Chrome giới hạn",
            "Có delay giữa các group (mặc định 10s, 1 tab)",
        ],
    )

    profile = selected_profile_from_ductool()
    box("CHROME ĐANG DÙNG", [
        f"DUCTOOL đang chọn Chrome_{profile}",
        "Đổi Chrome trong SETUP của Auto Join / Auto Đăng Bài / Messenger sẽ đồng bộ.",
    ], C_GREEN)
    cfg = load_config()
    joiner_cfg = cfg.get("joiner", {})
    saved_tab = int(joiner_cfg.get("tab_count", 1) or 1)
    tab_count = choose_tab_count(default=saved_tab)

    saved_delay = int(joiner_cfg.get("delay_seconds", 10) if joiner_cfg.get("delay_seconds") is not None else 10)
    delay_seconds = choose_delay_seconds(default=saved_delay)

    # Cập nhật lại config nếu có thay đổi
    cfg_changed = False
    if joiner_cfg.get("tab_count") != tab_count:
        cfg.setdefault("joiner", {})["tab_count"] = tab_count
        cfg_changed = True
    if joiner_cfg.get("delay_seconds") != delay_seconds:
        cfg.setdefault("joiner", {})["delay_seconds"] = delay_seconds
        cfg_changed = True
    if cfg_changed:
        save_config(cfg)

    sheet_link = str(joiner_cfg.get("sheet_url", "") or "").strip()

    while True:
        if not sheet_link:
            sheet_link = input(
                "\nChưa có Link Google Sheet trong SETUP. "
                "Vui lòng nhập link trang tính chứa link group: "
            ).strip()

        try:
            group_links = fetch_group_links(sheet_link)
            print(f"Đang dùng Google Sheet: {sheet_link}")
            if joiner_cfg.get("sheet_url") != sheet_link:
                cfg.setdefault("joiner", {})["sheet_url"] = sheet_link
                save_config(cfg)
            break
        except Exception as e:
            print(f"Không đọc được trang tính: {e}")
            print("Kiểm tra Link Google Sheet trong SETUP và quyền đọc bằng link.")
            sheet_link = ""

    if not group_links:
        box(
            "KHÔNG CÓ LINK GROUP",
            ["Không tìm thấy URL facebook.com/groups/... trong trang tính."],
            C_YELLOW,
        )
        return

    done = load_done()
    pending = [u for u in group_links if u not in done]

    box(
        "DANH SÁCH CHUẨN BỊ",
        [
            f"Tổng link trong Sheet: {len(group_links)}",
            f"Đã xử lý trước đó: {len(group_links) - len(pending)}",
            f"Còn lại: {len(pending)}",
            f"Số tab chạy song song: {tab_count}",
            f"Delay giữa các group: {delay_seconds}s",
        ],
        C_GREEN,
    )

    if not pending:
        box(
            "HOÀN TẤT",
            [
                "Không còn group mới để xử lý.",
                f"State: {STATE_FILE}",
            ],
            C_GREEN,
        )
        return

    async with async_playwright() as p:
        browser = None
        context = None
        try:
            port, profile_dir = _ensure_shared_chrome(profile)
            browser = await p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}"
            )
            if not browser.contexts:
                raise RuntimeError("Chrome chung đã mở nhưng không có browser context.")
            context = browser.contexts[0]

            box(
                "BẮT ĐẦU ĐA TAB",
                [
                    f"Yêu cầu: {min(tab_count, len(pending))} tab",
                    f"Tổng group: {len(pending)}",
                    f"Delay giữa các group: {delay_seconds}s",
                    "Giữ tab đầu của Chrome làm worker số 1",
                    "Nếu Chrome không mở đủ tab, tool tự giảm số tab",
                ],
                C_CYAN,
            )

            actual_tabs = await run_multitab(context, pending, tab_count, delay_seconds=delay_seconds)

            box(
                "ĐA TAB HOÀN TẤT",
                [
                    f"Số tab thực tế đã chạy: {actual_tabs}",
                    f"Delay giữa các group: {delay_seconds}s",
                ],
                C_GREEN,
            )

        finally:
            # Không đóng Chrome dùng chung của DUCTOOL.
            pass

    box(
        "KẾT THÚC",
        [
            f"Log: {LOG_FILE}",
            f"State: {STATE_FILE}",
        ],
        C_GREEN,
    )


if __name__ == "__main__":
    try:
        asyncio.run(async_main())
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    except Exception as e:
        try:
            CRASH_LOG.parent.mkdir(parents=True, exist_ok=True)
            CRASH_LOG.write_text(
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
                f"{type(e).__name__}: {e}\n",
                encoding="utf-8",
            )
        except Exception:
            pass

        print(f"\nLỗi: {e}")
        input("\nNhấn Enter để thoát...")
