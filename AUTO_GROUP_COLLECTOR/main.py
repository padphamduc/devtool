# -*- coding: utf-8 -*-
import re
import sys
import time
import asyncio
import os
import subprocess
import urllib.request
from pathlib import Path
from datetime import datetime

from playwright.async_api import async_playwright

from ductool_config import load_config, save_config
from ductool_chrome import chrome_settings, find_chrome, proxy_args

DATA_ROOT = Path(r"C:\duc\FacebookChrome")
DEFAULT_SOURCE = "https://www.facebook.com/groups/joins/"
MAX_SCROLLS = 40
SCROLL_WAIT_MS = 1200
GROUP_OPEN_WAIT_MS = 1800

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
    title = str(title).strip()
    print()
    print(color + "╔" + "═" * width + "╗" + C_RESET)
    print(color + "║" + f" {title} ".center(width) + "║" + C_RESET)
    print(color + "╠" + "═" * width + "╣" + C_RESET)
    for line in lines:
        line = str(line)
        if len(line) <= width:
            print(color + "║" + line.center(width) + "║" + C_RESET)
        else:
            while line:
                part, line = line[:width], line[width:]
                print(color + "║" + part.ljust(width) + "║" + C_RESET)
    print(color + "╚" + "═" * width + "╝" + C_RESET)


def menu_box(title, items, footer=None, color=C_CYAN, width=78):
    print()
    print(color + "╔" + "═" * width + "╗" + C_RESET)
    print(color + "║" + f" {title} ".center(width) + "║" + C_RESET)
    print(color + "╠" + "═" * width + "╣" + C_RESET)
    for key, label in items:
        line = f"  [{key}] {label}"
        print(color + "║" + line.ljust(width) + "║" + C_RESET)
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
        footer=["Chọn profile đang đăng nhập Facebook + Google"]
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
        with urllib.request.urlopen(
            f"http://127.0.0.1:{port}/json/version", timeout=1.0
        ) as r:
            return r.status == 200
    except Exception:
        return False


def _ensure_shared_chrome(slot):
    configured, profile_root, port, proxy = chrome_settings(slot)
    if _cdp_ready(port):
        return port, profile_root / f"Chrome_{slot}"

    profile_dir = profile_root / f"Chrome_{slot}"
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
        "Hãy đóng Chrome profile này rồi chạy lại."
    )


def choose_fields(default="123"):
    default = default if default else "123"
    menu_box(
        "CHỌN DỮ LIỆU CẦN LẤY",
        [
            ("1", "Link Group"),
            ("2", "Tên Group"),
            ("3", "Số Thành Viên"),
        ],
        footer=[
            "Có thể nhập: 1, 2, 3, 12, 13, 23 hoặc 123",
            f"Mặc định từ SETUP: {default} (Enter để dùng)"
        ],
        color=C_GREEN,
    )

    while True:
        raw = input(f"Chọn dữ liệu [Enter = {default}]: ").strip()
        if not raw and default:
            raw = default
        digits = []
        for ch in raw:
            if ch in "123" and ch not in digits:
                digits.append(ch)

        if digits:
            selected = []
            if "1" in digits:
                selected.append("link")
            if "2" in digits:
                selected.append("name")
            if "3" in digits:
                selected.append("members")
            return selected

        print("Vui lòng chọn ít nhất 1 mục: 1, 2 hoặc 3.")


def choose_tab_count(default=3):
    default = max(1, min(10, default if default else 3))
    box(
        "ĐA TAB LẤY TÊN / THÀNH VIÊN",
        [
            "Dùng khi bạn chọn mục 2 = Tên Group hoặc 3 = Số Thành Viên",
            "Cho phép 1 đến 10 tab chạy song song",
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


def normalize_group_url(href):
    if not href:
        return None
    href = href.strip()
    if href.startswith("/groups/"):
        href = "https://www.facebook.com" + href
    if "facebook.com/groups/" not in href:
        return None

    m = re.search(r"https?://(?:www\.|m\.)?facebook\.com/groups/([^/?#]+)", href, re.I)
    if not m:
        return None

    ident = m.group(1)
    if ident.lower() in {"feed", "discover", "joins", "create"}:
        return None

    return f"https://www.facebook.com/groups/{ident}/"


def clean_text(s):
    return " ".join((s or "").split()).strip()


def extract_member_text(text):
    if not text:
        return ""
    text = clean_text(text)

    patterns = [
        r"([\d.,]+\s*[KkMm]?)\s*(?:thành viên|members?)",
        r"(?:Nhóm công khai|Nhóm riêng tư|Public group|Private group)\s*[·•]\s*([\d.,]+\s*[KkMm]?)",
    ]
    for pat in patterns:
        m = re.search(pat, text, re.I)
        if m:
            return clean_text(m.group(1))
    return ""


async def collect_group_items(page):
    await page.goto(DEFAULT_SOURCE, wait_until="domcontentloaded", timeout=60000)
    await page.wait_for_timeout(2500)

    found = []
    seen = set()
    no_new_rounds = 0

    for scroll_no in range(1, MAX_SCROLLS + 1):
        try:
            items = await page.locator('a[href*="/groups/"]').evaluate_all(
                """(els) => els.map(e => ({
                    href: e.href || e.getAttribute('href') || '',
                    text: (e.innerText || e.textContent || '').trim(),
                    aria: e.getAttribute('aria-label') || '',
                    title: e.getAttribute('title') || ''
                }))"""
            )
        except Exception:
            items = []

        before = len(found)

        for item in items:
            url = normalize_group_url(item.get("href", ""))
            if not url or url in seen:
                continue

            raw_name = clean_text(
                item.get("text") or item.get("aria") or item.get("title") or ""
            )

            # Bỏ các text UI quá chung, giữ tên group nếu có.
            bad_names = {
                "xem nhóm", "view group", "nhóm", "groups",
                "truy cập nhóm", "visit group"
            }
            name = "" if raw_name.lower() in bad_names else raw_name

            seen.add(url)
            found.append({
                "url": url,
                "name": name,
                "members": "",
            })

        if len(found) == before:
            no_new_rounds += 1
        else:
            no_new_rounds = 0

        print(
            f"\rĐang lấy danh sách group... {len(found)} group",
            end="",
            flush=True
        )

        if no_new_rounds >= 6 and scroll_no >= 8:
            break

        try:
            await page.mouse.wheel(0, 2400)
            await page.wait_for_timeout(SCROLL_WAIT_MS)
        except Exception:
            break

    print()
    return found


async def scrape_group(page, url, need_name=True, need_members=True):
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(GROUP_OPEN_WAIT_MS)
    except Exception:
        return "", url, ""

    current = page.url.lower()
    if "login" in current or "checkpoint" in current:
        raise RuntimeError("Facebook yêu cầu đăng nhập/checkpoint.")

    name = ""
    if need_name:
        selectors = [
            'h1',
            'h1 a',
            '[role="main"] h1',
        ]
        for sel in selectors:
            try:
                loc = page.locator(sel)
                if await loc.count():
                    candidate = clean_text(await loc.first.inner_text(timeout=2500))
                    if candidate:
                        name = candidate
                        break
            except Exception:
                pass

    member = ""
    if need_members:
        try:
            candidates = page.locator(
                'a:has-text("thành viên"), span:has-text("thành viên"), '
                'a:has-text("members"), span:has-text("members")'
            )
            count = min(await candidates.count(), 30)
            for i in range(count):
                try:
                    t = clean_text(await candidates.nth(i).inner_text(timeout=1200))
                    member = extract_member_text(t)
                    if member:
                        break
                except Exception:
                    pass
        except Exception:
            pass

        if not member:
            try:
                body_text = await page.locator("body").inner_text(timeout=5000)
                member = extract_member_text(body_text[:30000])
            except Exception:
                pass

    return name, url, member


async def scrape_groups_multitab(context, items, selected_fields, tab_count):
    need_name = "name" in selected_fields
    need_members = "members" in selected_fields

    # Chỉ lấy Link thì không cần mở từng group.
    if not need_name and not need_members:
        return [["", item["url"], ""] for item in items]

    worker_count = max(1, min(tab_count, len(items) if items else 1))
    queue = asyncio.Queue()
    results = [None] * len(items)
    print_lock = asyncio.Lock()
    fatal_error = {"error": None}

    for idx, item in enumerate(items):
        queue.put_nowait((idx, item))

    async def worker(worker_no):
        page = await context.new_page()
        try:
            while True:
                if fatal_error["error"] is not None:
                    break

                try:
                    idx, item = queue.get_nowait()
                except asyncio.QueueEmpty:
                    break

                url = item["url"]

                try:
                    name, link, member = await scrape_group(
                        page,
                        url,
                        need_name=need_name,
                        need_members=need_members,
                    )
                    results[idx] = [name, link, member]

                    async with print_lock:
                        parts = [f"[{idx + 1}/{len(items)}]"]
                        if need_name:
                            parts.append(name or "(không lấy được tên)")
                        if need_members:
                            parts.append(member or "?")
                        parts.append(link)
                        print(" | ".join(parts))

                except Exception as e:
                    results[idx] = ["", url, ""]
                    msg = str(e).lower()

                    if "checkpoint" in msg or "đăng nhập" in msg:
                        fatal_error["error"] = e

                    async with print_lock:
                        print(f"[{idx + 1}/{len(items)}] Lỗi khi đọc group | {url}")

                finally:
                    queue.task_done()
        finally:
            try:
                await page.close()
            except Exception:
                pass

    tasks = [
        asyncio.create_task(worker(i + 1))
        for i in range(worker_count)
    ]
    await asyncio.gather(*tasks)

    if fatal_error["error"] is not None:
        raise fatal_error["error"]

    return [
        row if row is not None else ["", items[i]["url"], ""]
        for i, row in enumerate(results)
    ]


def validate_sheet_link(link):
    link = link.strip()
    return bool(
        re.match(
            r"^https://docs\.google\.com/spreadsheets/d/[A-Za-z0-9_-]+",
            link
        )
    )


def make_sheet_url(link):
    link = link.strip()
    if "/edit" in link:
        return link

    base = link.split("#")[0].split("?")[0].rstrip("/")
    return base + "/edit"


async def write_rows_to_sheet(context, sheet_link, rows, selected_fields):
    page = await context.new_page()
    sheet_url = make_sheet_url(sheet_link)

    try:
        await page.goto(sheet_url, wait_until="domcontentloaded", timeout=60000)
        await page.wait_for_timeout(5000)
    except Exception as e:
        await page.close()
        return False, f"Không mở được Google Sheet: {e}"

    if "accounts.google.com" in page.url:
        await page.close()
        return False, "Chrome này chưa đăng nhập Google."

    headers_map = {
        "link": "Link Group",
        "name": "Tên Group",
        "members": "Số Thành Viên",
    }
    index_map = {
        "name": 0,
        "link": 1,
        "members": 2,
    }

    headers = [headers_map[field] for field in selected_fields]
    filtered_rows = [
        [row[index_map[field]] for field in selected_fields]
        for row in rows
    ]

    all_rows = [headers] + filtered_rows

    tsv = "\n".join(
        "\t".join(
            str(v or "").replace("\t", " ").replace("\n", " ")
            for v in row
        )
        for row in all_rows
    )

    try:
        await context.grant_permissions(
            ["clipboard-read", "clipboard-write"],
            origin="https://docs.google.com"
        )
    except Exception:
        pass

    selected = False
    name_box_selectors = [
        'input.waffle-name-box',
        'input[aria-label="Name box"]',
        'input[aria-label="Hộp tên"]',
    ]

    for sel in name_box_selectors:
        try:
            loc = page.locator(sel)
            if await loc.count():
                await loc.first.click(timeout=3000)
                await loc.first.fill("A1")
                await page.keyboard.press("Enter")
                await page.wait_for_timeout(600)
                selected = True
                break
        except Exception:
            pass

    if not selected:
        try:
            grid = page.locator("#waffle-grid-container")
            if await grid.count():
                box_ = await grid.bounding_box()
                if box_:
                    await page.mouse.click(box_["x"] + 55, box_["y"] + 18)
                    selected = True
        except Exception:
            pass

    if not selected:
        await page.close()
        return False, "Không chọn được ô A1 trên Google Sheet."

    try:
        await page.evaluate(
            """async (text) => {
                await navigator.clipboard.writeText(text);
            }""",
            tsv,
        )
        await page.keyboard.press("Control+V")
        await page.wait_for_timeout(2500)
    except Exception as e:
        await page.close()
        return False, f"Không paste được dữ liệu: {e}"

    if "accounts.google.com" in page.url:
        await page.close()
        return False, "Google yêu cầu đăng nhập lại khi đang ghi."

    await page.wait_for_timeout(1500)
    await page.close()

    return True, (
        f"Đã gửi {len(rows)} group vào trang tính từ ô A1 "
        f"với {len(selected_fields)} cột đã chọn."
    )


async def async_main():
    enable_colors()

    box("DUC FB GROUP COLLECTOR v1.7", [
        "Nguồn cố định: Nhóm của tôi trên Facebook",
        "Link | Tên Group | Số Thành Viên → Google Sheet",
        "Tên + Member hỗ trợ đa tab Async 1-10",
    ], C_CYAN)

    profile = selected_profile_from_ductool()
    box("CHROME ĐANG DÙNG", [
        f"DUCTOOL đang chọn Chrome_{profile}",
        "Có thể đổi Chrome trong SETUP của Group Collector, Auto Đăng Bài hoặc Messenger.",
    ], C_GREEN)
    cfg = load_config()
    col_cfg = cfg.get("collector", {})
    saved_fields = str(col_cfg.get("fields", "123") or "123").strip()
    saved_tab_count = int(col_cfg.get("tab_count", 3) or 3)
    sheet_link = str(col_cfg.get("sheet_url", "") or "").strip()

    selected_fields = choose_fields(default=saved_fields)

    # Chỉ hỏi số tab khi có chọn Member hoặc Tên.
    need_name = "name" in selected_fields
    need_members = "members" in selected_fields
    need_detail_tabs = need_name or need_members
    tab_count = choose_tab_count(default=saved_tab_count) if need_detail_tabs else 1

    while True:
        if not sheet_link:
            print()
            sheet_link = input("Vui lòng nhập link trang tính để ghi: ").strip()
        if validate_sheet_link(sheet_link):
            print(f"Đang dùng Google Sheet: {sheet_link}")
            if col_cfg.get("sheet_url") != sheet_link:
                cfg.setdefault("collector", {})["sheet_url"] = sheet_link
                save_config(cfg)
            break
        print("Link không hợp lệ. Ví dụ: https://docs.google.com/spreadsheets/d/.../edit")
        sheet_link = ""

    async with async_playwright() as p:
        browser = None
        page = None
        try:
            port, profile_dir = _ensure_shared_chrome(profile)
            browser = await p.chromium.connect_over_cdp(
                f"http://127.0.0.1:{port}"
            )
            if not browser.contexts:
                raise RuntimeError("Chrome chung đã mở nhưng không có browser context.")

            context = browser.contexts[0]
            page = await context.new_page()

            items = await collect_group_items(page)

            if not items:
                box("KHÔNG CÓ GROUP", [
                    "Không tìm thấy group trong mục Nhóm của tôi.",
                    "Kiểm tra Facebook đã đăng nhập và tài khoản có group.",
                ], C_YELLOW)
                return

            unique_items = []
            seen = set()
            for item in items:
                url = item["url"]
                if url not in seen:
                    seen.add(url)
                    unique_items.append(item)

            if need_detail_tabs:
                selected_labels = []
                if need_name:
                    selected_labels.append("Tên Group")
                if need_members:
                    selected_labels.append("Số Thành Viên")

                box("ĐA TAB LẤY DỮ LIỆU", [
                    f"Dữ liệu: {' + '.join(selected_labels)}",
                    f"Số tab chạy song song: {tab_count}",
                    f"Tổng group cần xử lý: {len(unique_items)}",
                    "Mỗi tab mở group và lấy dữ liệu đã chọn",
                ], C_CYAN)
            else:
                box("LẤY LINK GROUP", [
                    "Không mở từng group",
                    f"Tổng link lấy được: {len(unique_items)}",
                ], C_GREEN)

            rows = await scrape_groups_multitab(
                context,
                unique_items,
                selected_fields,
                tab_count,
            )

            ok, message = await write_rows_to_sheet(
                context,
                sheet_link,
                rows,
                selected_fields,
            )

            if ok:
                label_map = {
                    "link": "Link Group",
                    "name": "Tên Group",
                    "members": "Số Thành Viên",
                }
                selected_text = " | ".join(
                    label_map[x] for x in selected_fields
                )

                box("ĐÃ GHI TRANG TÍNH", [
                    message,
                    f"Tổng số group: {len(rows)}",
                    f"Cột đã ghi: {selected_text}",
                ], C_GREEN)

            else:
                backup = Path(r"C:\duc\group_backup.tsv")
                backup.parent.mkdir(parents=True, exist_ok=True)

                backup.write_text(
                    "Tên Group\tLink Group\tSố Thành Viên\n"
                    + "\n".join(
                        "\t".join(str(v or "") for v in row)
                        for row in rows
                    ),
                    encoding="utf-8"
                )

                box("GHI SHEET THẤT BẠI", [
                    message,
                    f"Đã lưu backup: {backup}",
                    "Dữ liệu quét không bị mất.",
                ], C_RED)

        finally:
            # Chỉ đóng tab chính do collector tạo. Không đóng Chrome dùng chung.
            try:
                if page is not None:
                    await page.close()
            except Exception:
                pass


def main():
    asyncio.run(async_main())


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print("\nĐã dừng.")
    except Exception as e:
        print(f"\nLỗi: {e}")
        try:
            Path(r"C:\duc\group_collector_crash.log").write_text(
                f"{datetime.now():%Y-%m-%d %H:%M:%S}\n"
                f"{type(e).__name__}: {e}\n",
                encoding="utf-8"
            )
        except Exception:
            pass
        input("\nNhấn Enter để thoát...")
