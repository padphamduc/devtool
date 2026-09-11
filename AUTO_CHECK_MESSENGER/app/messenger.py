import asyncio
import os
import shutil
import subprocess
import urllib.request
import time
import hashlib
import re
from dataclasses import dataclass
from typing import List
from pathlib import Path

from playwright.async_api import async_playwright, Page, Browser, BrowserContext

from .chrome_selector import resolve_chrome
from ductool_config import load_config
from ductool_chrome import chrome_settings, find_chrome, proxy_args
from .config import MESSENGER_INBOX_URL, MESSENGER_REQUESTS_URL, MESSENGER_SPAM_URL, FB_NOTIFICATIONS_URL


@dataclass
class ConversationPreview:
    source: str
    sender: str
    preview: str
    href: str = ""
    age_minutes: int | None = None

    @property
    def fingerprint(self) -> str:
        value = "|".join([
            self.source.strip().lower(),
            self.sender.strip().lower(),
            self.preview.strip().lower(),
            self.href.strip().lower(),
        ])
        return hashlib.sha256(value.encode("utf-8")).hexdigest()


_PRESENCE_RE = re.compile(
    r"^(?:"
    r"(?:đang\s+)?hoạt\s+động(?:\s+(?:hiện\s+tại|bây\s+giờ|gần\s+đây|hôm\s+qua|trên\s+\w+|\d+\s*(?:phút|giờ|ngày|tuần|tháng)(?:\s*trước)?|lúc\s+[\d:]+))?|"
    r"active(?:\s+(?:now|recently|today|yesterday|on\s+\w+|\d+\s*(?:minutes?|mins?|hours?|hrs?|days?|weeks?|months?|[mhdw])(?:\s*ago)?|at\s+[\d:]+))?|"
    r"(?:đang\s+)?(?:online|offline|trực\s+tuyến|ngoại\s+tuyến)|"
    r"vừa\s+(?:mới\s+)?(?:truy\s+cập|xong)"
    r")$",
    re.I,
)

_UI_JUNK_RE = re.compile(
    r"^(?:"
    r"(?:đoạn\s+chat\s*[·•\-]\s*)?\d+\s*tin\s+nhắn\s+chưa\s+đọc|"
    r"\d+\s*unread\s+messages?|"
    r"tin\s+nhắn\s+chưa\s+đọc|chưa\s+đọc|unread|"
    r"đoạn\s+chat(?:\s+mới)?|tin\s+nhắn(?:\s+mới)?|new\s+chat|new\s+message|"
    r"cộng\s+đồng|communities|kho\s+lưu\s+trữ|lưu\s+trữ|archive(?:d\s+chats)?|"
    r"tin\s+nhắn\s+(?:đang\s+)?chờ|message\s+requests|thư\s+rác|spam|"
    r"cài\s+đặt|settings|marketplace|search\s+messenger|tìm\s+kiếm(?:\s+trên\s+messenger)?"
    r")$",
    re.I,
)


def _clean_line_text(line: str) -> str:
    cleaned = re.sub(r"\s+", " ", line).strip()
    return cleaned.strip(" \t\r\n·•*-|~🟢⚪⚫.")


def is_presence_line(line: str) -> bool:
    cleaned = _clean_line_text(line)
    if not cleaned:
        return True
    return bool(_PRESENCE_RE.match(cleaned))


def is_ui_junk_line(line: str) -> bool:
    cleaned = _clean_line_text(line)
    if not cleaned:
        return True
    return bool(_UI_JUNK_RE.match(cleaned))


def _conversation_lines(raw: str) -> list[str]:
    """Skip leading presence badges and UI labels before reading the conversation name."""
    lines = [re.sub(r"\s+", " ", line).strip() for line in raw.splitlines()]
    lines = [line for line in lines if line]

    while lines and (is_presence_line(lines[0]) or is_ui_junk_line(lines[0])):
        lines.pop(0)

    return lines


def _looks_outgoing_message(raw: str) -> bool:
    """
    Detect Messenger conversation previews where the latest message
    was sent by the logged-in user.
    """
    s = " ".join(raw.lower().split())

    outgoing_markers = (
        "you:",
        "you sent",
        "you sent a",
        "you sent an",
        "you replied",
        "you: ",
        "bạn:",
        "bạn đã gửi",
        "bạn gửi",
        "bạn đã trả lời",
        "bạn trả lời",
    )

    if any(marker in s for marker in outgoing_markers):
        return True

    # Common compact preview forms such as "You · 5m" / "Bạn · 5 phút"
    if re.search(r'(^|\s)(you|bạn)\s*[·•\-:]\s*', s):
        return True

    return False


def _parse_age_minutes(raw: str):
    """
    Parse common Messenger relative-time labels.
    Returns age in minutes, or None if no reliable relative timestamp is visible.
    """
    s = " ".join(raw.lower().split())

    # Vietnamese
    patterns = [
        (r'(?<!\d)(\d+)\s*phút(?:\s*trước)?', 1),
        (r'(?<!\d)(\d+)\s*giờ(?:\s*trước)?', 60),
        (r'(?<!\d)(\d+)\s*ngày(?:\s*trước)?', 1440),

        # English long forms
        (r'(?<!\d)(\d+)\s*min(?:ute)?s?(?:\s*ago)?', 1),
        (r'(?<!\d)(\d+)\s*hour?s?(?:\s*ago)?', 60),
        (r'(?<!\d)(\d+)\s*day?s?(?:\s*ago)?', 1440),

        # Compact forms Messenger may render
        (r'(?<!\d)(\d+)\s*m\b', 1),
        (r'(?<!\d)(\d+)\s*h\b', 60),
        (r'(?<!\d)(\d+)\s*d\b', 1440),
    ]

    for pattern, multiplier in patterns:
        m = re.search(pattern, s)
        if m:
            return int(m.group(1)) * multiplier

    # "now" / "just now" / Vietnamese equivalents
    if any(x in s for x in ("just now", "now", "vừa xong", "bây giờ")):
        return 0

    return None




def _strip_relative_time_from_preview(text: str) -> str:
    """Bỏ 1 phút/2 phút/... khỏi nội dung preview gửi Telegram."""
    value = text or ""
    value = re.sub(
        r'(?<!\d)\d+\s*(?:phút|giờ|ngày)(?:\s*trước)?',
        ' ',
        value,
        flags=re.I,
    )
    value = re.sub(
        r'(?<!\d)\d+\s*(?:min(?:ute)?s?|hours?|days?)(?:\s*ago)?',
        ' ',
        value,
        flags=re.I,
    )
    value = re.sub(r'(?<!\d)\d+\s*[mhd]\b', ' ', value, flags=re.I)
    value = re.sub(
        r'\b(?:just now|now|vừa xong|bây giờ)\b',
        ' ',
        value,
        flags=re.I,
    )
    value = re.sub(r'\s*[·•]\s*$', '', value)
    value = re.sub(r'\s+', ' ', value).strip(" ·•-|")
    return value.strip()


def _chrome_executable(configured: str = "") -> str:
    return find_chrome(configured)

def _cdp_ready(port: int) -> bool:
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/json/version", timeout=1.0) as r:
            return r.status == 200
    except Exception:
        return False

def _ensure_shared_chrome(number: int, port: int) -> None:
    configured, profile_root, port, proxy = chrome_settings(number)
    if _cdp_ready(port): return
    profile_dir=profile_root/f"Chrome_{number}"; profile_dir.mkdir(parents=True,exist_ok=True)
    args=[_chrome_executable(configured), f"--user-data-dir={profile_dir}", f"--remote-debugging-port={port}", "--start-maximized", "--no-first-run", "--no-default-browser-check"]
    args.extend(proxy_args(number, proxy))
    creationflags=0
    if os.name=="nt": creationflags=getattr(subprocess,"DETACHED_PROCESS",0x8)|getattr(subprocess,"CREATE_NEW_PROCESS_GROUP",0x200)
    subprocess.Popen(args,stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,stdin=subprocess.DEVNULL,creationflags=creationflags,close_fds=True)
    for _ in range(40):
        if _cdp_ready(port): return
        time.sleep(0.25)
    raise RuntimeError(f"Đã thử tự mở Chrome {number} nhưng chưa thấy cổng {port}. Hãy đóng Chrome profile này rồi chạy lại.")


class MessengerClient:
    def __init__(self):
        self._pw = None
        self.browser: Browser | None = None
        self.context: BrowserContext | None = None
        self.page: Page | None = None
        self.chrome_number: int | None = None
        self.cdp_url: str | None = None

    async def start(self):
        number, port = resolve_chrome()
        _configured, _profile_root, port, _proxy = chrome_settings(number)
        self.chrome_number = number
        self.cdp_url = f"http://127.0.0.1:{port}"

        # Tool Messenger không phụ thuộc FB Poster:
        # nếu Chrome chung chưa mở thì tự mở đúng profile/port.
        await asyncio.to_thread(_ensure_shared_chrome, number, port)

        self._pw = await async_playwright().start()
        try:
            self.browser = await self._pw.chromium.connect_over_cdp(self.cdp_url)
        except Exception as exc:
            await self._pw.stop()
            self._pw = None
            raise RuntimeError(
                f"Không kết nối được Chrome {number} tại {self.cdp_url}."
            ) from exc

        if not self.browser.contexts:
            raise RuntimeError("Kết nối Chrome thành công nhưng không có browser context.")

        self.context = self.browser.contexts[0]
        await self._ensure_page()

    async def _ensure_page(self):
        if self.context is None:
            raise RuntimeError("Chrome context chưa sẵn sàng.")

        if self.page and not self.page.is_closed():
            return

        # Reuse an existing Messenger tab if present; otherwise create one.
        for p in self.context.pages:
            try:
                if "messenger.com" in (p.url or "").lower():
                    self.page = p
                    return
            except Exception:
                pass

        self.page = await self.context.new_page()
        await self.page.goto(MESSENGER_INBOX_URL, wait_until="domcontentloaded")

    async def stop(self):
        # IMPORTANT: disconnect Playwright only. Do not close shared Chrome.
        self.page = None
        self.context = None
        self.browser = None
        if self._pw:
            await self._pw.stop()
            self._pw = None

    async def ensure_login(self):
        await self._ensure_page()
        assert self.page
        await self.page.goto(MESSENGER_INBOX_URL, wait_until="domcontentloaded")
        await asyncio.sleep(2)

        url = (self.page.url or "").lower()
        body = (await self.page.locator("body").inner_text()).lower()
        signals = [
            "log into facebook",
            "log in to facebook",
            "email or phone",
            "password",
            "đăng nhập facebook",
            "mật khẩu",
        ]
        if "login" in url or any(s in body for s in signals):
            raise RuntimeError(
                f"Chrome {self.chrome_number} chưa đăng nhập Messenger/Facebook."
            )

    async def _safe_goto(self, url: str):
        await self._ensure_page()
        assert self.page
        try:
            await self.page.goto(url, wait_until="domcontentloaded")
        except Exception:
            if self.page.is_closed():
                self.page = None
                await self._ensure_page()
                assert self.page
                await self.page.goto(url, wait_until="domcontentloaded")
            else:
                raise

    async def _extract(self, source: str) -> List[ConversationPreview]:
        assert self.page
        candidates = await self.page.locator(
            'a[href*="/t/"], a[href*="e2ee/t/"], a[href*="/messages/t/"]'
        ).all()

        out: list[ConversationPreview] = []
        seen_href: set[str] = set()
        bad = {
            "chats", "marketplace", "requests", "archive",
            "tin nhắn", "đoạn chat", "tin nhắn đang chờ",
            "search messenger", "tìm kiếm trên messenger",
            "thư rác", "spam", "chưa đọc", "unread",
            "đang hoạt động", "active now", "online", "offline",
        }

        for item in candidates[:250]:
            try:
                if not await item.is_visible():
                    continue
                href = (await item.get_attribute("href")) or ""
                # Bỏ qua liên kết accessibility focus target và link gốc không có thread id
                if "focus_target" in href.lower():
                    continue
                if href.rstrip("/") in ("/t", "https://www.messenger.com/t", "https://www.facebook.com/messages/t"):
                    continue

                raw = (await item.inner_text()).strip()
                if not raw:
                    continue

                lines = _conversation_lines(raw)
                if not lines:
                    continue
                content_raw = "\n".join(lines)
                # Ignore our outgoing previews after discarding presence badges.
                if _looks_outgoing_message(content_raw):
                    continue

                looks_thread = "/t/" in href or "e2ee" in href or "message" in href.lower()
                if not looks_thread:
                    continue

                # Nếu sau tên người có badge trạng thái hoạt động và vẫn còn dòng nội dung thật phía sau
                # (ví dụ: ['Đào Đức', 'Đang hoạt động', 'Đức đã gửi...', '1 phút'])
                # loại bỏ dòng trạng thái đó để không dính vào preview tin nhắn.
                # Ngược lại nếu không có nội dung khác ngoài timestamp, dòng đó có thể là nội dung tin nhắn.
                if len(lines) > 2 and is_presence_line(lines[1]):
                    has_subsequent_content = not _parse_age_minutes(lines[2]) and not is_presence_line(lines[2])
                    if has_subsequent_content:
                        lines.pop(1)

                sender = lines[0][:160]

                # Nếu dòng đầu vô tình vẫn là trạng thái hoặc rác UI, thử lấy dòng kế tiếp
                if is_presence_line(sender) or is_ui_junk_line(sender) or sender.lower() in bad:
                    if len(lines) > 1 and not is_presence_line(lines[1]) and not is_ui_junk_line(lines[1]):
                        sender = lines[1][:160]
                        lines = lines[1:]
                    else:
                        continue

                if sender.lower() in bad or is_presence_line(sender) or is_ui_junk_line(sender):
                    continue

                if href and href in seen_href:
                    continue

                preview_raw = " · ".join(lines[1:4])[:500] if len(lines) > 1 else "(không có preview)"
                preview = _strip_relative_time_from_preview(preview_raw) or "(không có preview)"

                # Tránh lặp tên người ở đầu preview nếu đã tách đúng sender
                if preview.startswith(f"{sender} · "):
                    preview = preview[len(f"{sender} · "):].strip() or "(không có preview)"
                elif preview.startswith(f"{sender}: "):
                    preview = preview[len(f"{sender}: "):].strip() or "(không có preview)"

                out.append(ConversationPreview(source, sender, preview, href, _parse_age_minutes(content_raw)))
                if href:
                    seen_href.add(href)
            except Exception:
                continue
        return out

    async def scan_inbox(self):
        await self._safe_goto(MESSENGER_INBOX_URL)
        await asyncio.sleep(2)
        return await self._extract("inbox")

    async def scan_requests(self):
        await self._safe_goto(MESSENGER_REQUESTS_URL)
        await asyncio.sleep(2)
        return await self._extract("requests")


    async def scan_spam(self):
        """
        Quét mục Spam nằm trong Message Requests.
        Ưu tiên mở /requests/ rồi click tab/nút Spam vì URL Messenger có thể thay đổi.
        Nếu không tìm thấy nút, thử URL /requests/spam/.
        """
        await self._safe_goto(MESSENGER_REQUESTS_URL)
        await asyncio.sleep(2)
        assert self.page

        clicked = False
        selectors = [
            'a:has-text("Spam")',
            'div[role="tab"]:has-text("Spam")',
            'div[role="button"]:has-text("Spam")',
            'span:has-text("Spam")',
            'a:has-text("Thư rác")',
            'div[role="tab"]:has-text("Thư rác")',
            'div[role="button"]:has-text("Thư rác")',
            'span:has-text("Thư rác")',
        ]

        for selector in selectors:
            try:
                loc = self.page.locator(selector).first
                if await loc.count() and await loc.is_visible():
                    await loc.click()
                    await asyncio.sleep(2)
                    clicked = True
                    break
            except Exception:
                continue

        if not clicked:
            fallback = MESSENGER_SPAM_URL
            await self._safe_goto(fallback)
            await asyncio.sleep(2)

        return await self._extract("spam")

    async def scan_notifications(self) -> List[ConversationPreview]:
        """
        Quét trang thông báo Facebook: https://www.facebook.com/notifications
        Lọc mục chưa đọc (Unread), lọc thời gian <= MAX_MESSAGE_AGE_MINUTES, chống spam.
        """
        await self._safe_goto(FB_NOTIFICATIONS_URL)
        await asyncio.sleep(2.5)
        assert self.page

        # Chuyển sang filter 'Chưa đọc' / 'Unread' nếu có tab/nút lọc
        filter_selectors = [
            'div[role="tab"]:has-text("Chưa đọc")',
            'div[role="button"]:has-text("Chưa đọc")',
            'a:has-text("Chưa đọc")',
            'div[role="tab"]:has-text("Unread")',
            'div[role="button"]:has-text("Unread")',
            'a:has-text("Unread")',
        ]
        for sel in filter_selectors:
            try:
                loc = self.page.locator(sel).first
                if await loc.count() and await loc.is_visible():
                    # Kiểm tra xem có đang active chưa
                    attr = await loc.get_attribute("aria-selected")
                    if attr != "true":
                        await loc.click()
                        await asyncio.sleep(1.5)
                    break
            except Exception:
                continue

        # Thu thập các thẻ item thông báo
        # Trên Facebook web, thông báo thường nằm trong div/a có role="link" hoặc aria-label
        # Chưa đọc thường có chấm tròn xanh (aria-label="Chưa đọc", hoặc indicator xanh)
        selectors = [
            'div[role="listitem"]',
            'div[data-visualcompletion="ignore-dynamic"]',
            'a[role="link"][href*="/notifications"]',
            'a[role="link"][href*="notif_id"]',
            'div[role="feed"] > div',
        ]

        items_loc = None
        for sel in selectors:
            candidate = self.page.locator(sel)
            cnt = await candidate.count()
            if cnt > 1:
                items_loc = candidate
                break

        if not items_loc:
            # Fallback lấy toàn bộ liên kết có vẻ là thông báo
            items_loc = self.page.locator('a[role="link"]')

        out: list[ConversationPreview] = []
        seen_href: set[str] = set()
        count = min(await items_loc.count(), 60)

        for i in range(count):
            try:
                item = items_loc.nth(i)
                if not await item.is_visible():
                    continue

                raw = (await item.inner_text()).strip()
                if not raw or len(raw) < 5:
                    continue

                # Lấy link dẫn đến bài viết/thông báo
                href = ""
                tag = await item.evaluate("el => el.tagName.toLowerCase()")
                if tag == "a":
                    href = (await item.get_attribute("href")) or ""
                else:
                    inner_a = item.locator("a").first
                    if await inner_a.count():
                        href = (await inner_a.get_attribute("href")) or ""

                if href and href in seen_href:
                    continue

                # Nhận diện thông báo 'Chưa đọc' (Unread)
                # Facebook thường có text ẩn hoặc aria-label hoặc dấu chấm chưa đọc
                is_unread = False
                html_snippet = await item.inner_html()
                if any(x in html_snippet.lower() for x in ("chưa đọc", "unread", "mark as read", "đánh dấu là đã đọc")):
                    is_unread = True
                else:
                    # Kiểm tra có chấm xanh (blue dot indicator)
                    dots = item.locator('div[style*="background-color: var(--accent)"], div[style*="background-color: rgb(24, 119, 242)"], div[style*="rgb(49, 162, 76)"], span[aria-label*="chưa đọc"], span[aria-label*="Unread"]')
                    if await dots.count():
                        is_unread = True

                # Nếu đang ở tab 'Chưa đọc', mặc định mọi item trong danh sách là chưa đọc
                current_url = (self.page.url or "").lower()
                if "filter=unread" in current_url or is_unread:
                    pass
                elif not is_unread:
                    # Bỏ qua thông báo đã đọc
                    continue

                lines = [
                    re.sub(r"\s+", " ", x).strip()
                    for x in raw.splitlines()
                    if re.sub(r"\s+", " ", x).strip()
                ]
                if not lines:
                    continue

                # Trích xuất người gửi và nội dung
                sender = lines[0][:120] if len(lines) > 0 else "Facebook Notification"
                preview_raw = " ".join(lines[1:])[:400] if len(lines) > 1 else lines[0][:400]
                preview = _strip_relative_time_from_preview(preview_raw) or "(không có nội dung)"
                age = _parse_age_minutes(raw)

                out.append(ConversationPreview(
                    source="notifications",
                    sender=sender,
                    preview=preview,
                    href=href,
                    age_minutes=age
                ))
                if href:
                    seen_href.add(href)
            except Exception:
                continue

        return out
