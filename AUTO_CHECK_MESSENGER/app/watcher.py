import asyncio
import traceback
from datetime import datetime

from .config import POLL_SECONDS, MAX_MESSAGE_AGE_MINUTES, CHECK_NOTIFICATIONS
from .messenger import MessengerClient, is_presence_line, is_ui_junk_line
from .storage import is_new_message_snapshot, update_thread_state
from ductool_notifications import send_notification


class Watcher:
    def __init__(self):
        self.task = None
        self.running = False
        self.last_check = None
        self.last_error = None
        self.notifications_sent = 0
        self.client = None

    async def _scan_once(self):
        inbox = await self.client.scan_inbox()
        requests = await self.client.scan_requests()
        spam = await self.client.scan_spam()

        notifs = []
        if CHECK_NOTIFICATIONS:
            try:
                notifs = await self.client.scan_notifications()
            except Exception as e:
                print(f"[Watcher] Lỗi quét thông báo FB: {e}")

        for item in inbox + requests + spam + notifs:
            # Chỉ dùng mốc phút trong DUCTOOL Settings để quyết định
            # tin/thông báo còn đủ mới để gửi hay không.
            if item.age_minutes is None or item.age_minutes > MAX_MESSAGE_AGE_MINUTES:
                update_thread_state(
                    item.source, item.sender, item.href,
                    item.preview, item.age_minutes
                )
                continue

            is_new = is_new_message_snapshot(
                item.source, item.sender, item.href,
                item.preview, item.age_minutes
            )

            if not is_new:
                update_thread_state(item.source, item.sender, item.href, item.preview, item.age_minutes)
                continue

            if item.source == "requests":
                source = "Tin nhắn chờ"
                icon = "📩"
                title = "Messenger mới"
            elif item.source == "spam":
                source = "Spam"
                icon = "📩"
                title = "Messenger mới"
            elif item.source == "notifications":
                source = "Thông báo FB (Chưa đọc)"
                icon = "🔔"
                title = "Thông báo Facebook mới"
            else:
                source = "Tin nhắn chính"
                icon = "📩"
                title = "Messenger mới"

            sender = item.sender
            preview = item.preview

            # Phản vệ an toàn: nếu sender vẫn là trạng thái hoạt động hoặc rác UI
            if is_presence_line(sender) or is_ui_junk_line(sender):
                if " · " in preview:
                    p_sender, p_msg = preview.split(" · ", 1)
                    if p_sender.strip() and not is_presence_line(p_sender) and not is_ui_junk_line(p_sender):
                        sender = p_sender.strip()
                        preview = p_msg.strip()

            # Nếu vẫn không lấy được tên người hợp lệ (vẫn là "Đang hoạt động", v.v.), bỏ qua không gửi nhầm
            if is_presence_line(sender) or is_ui_junk_line(sender):
                update_thread_state(item.source, item.sender, item.href, item.preview, item.age_minutes)
                continue

            text = (
                f"{icon} {title}\n"
                f"Nguồn: {source}\n"
                f"Từ: {sender}\n"
                f"Nội dung: {preview}"
            )
            if item.href and item.source == "notifications":
                text += f"\nLink: {item.href}"

            await send_notification(text)
            # Only acknowledge after delivery so API failures can be retried next scan.
            update_thread_state(item.source, sender, item.href, preview, item.age_minutes)
            self.notifications_sent += 1

        self.last_check = datetime.now().isoformat(timespec="seconds")
        self.last_error = None

    async def run(self):
        self.running = True
        self.last_error = None
        self.client = MessengerClient()

        try:
            await self.client.start()
            await self.client.ensure_login()

            while self.running:
                try:
                    await self._scan_once()
                except asyncio.CancelledError:
                    raise
                except Exception as exc:
                    self.last_error = f"{type(exc).__name__}: {exc}"
                    traceback.print_exc()
                await asyncio.sleep(POLL_SECONDS)

        except asyncio.CancelledError:
            raise
        except Exception as exc:
            self.last_error = f"{type(exc).__name__}: {exc}"
            traceback.print_exc()
        finally:
            try:
                if self.client:
                    await self.client.stop()
            except Exception:
                traceback.print_exc()
            self.client = None
            self.running = False

    def start(self):
        if self.task and not self.task.done():
            return False
        self.last_error = None
        self.task = asyncio.create_task(self.run())
        return True

    async def stop(self):
        self.running = False
        if self.task and not self.task.done():
            self.task.cancel()
            try:
                await self.task
            except asyncio.CancelledError:
                pass
        self.task = None

    def status(self):
        return {
            "running": bool(self.task and not self.task.done()),
            "last_check": self.last_check,
            "last_error": self.last_error,
            "notifications_sent": self.notifications_sent,
        }
