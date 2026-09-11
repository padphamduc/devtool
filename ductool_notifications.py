"""Shared notification delivery for the settings test and Messenger watcher."""
import httpx

from ductool_config import load_config

PROVIDERS = {
    "telegram": ("Telegram", "https://api.telegram.org", 4096),
    "zalo": ("Zalo", "https://bot-api.zaloplatforms.com", 2000),
}


async def get_zalo_chat(token: str):
    """Wait for one incoming event without changing the bot's webhook settings."""
    token = token.strip()
    if not token:
        raise RuntimeError("Vui lòng nhập Zalo Bot Token trước khi lấy Chat ID.")
    async with httpx.AsyncClient(timeout=40) as client:
        try:
            response = await client.post(
                f"https://bot-api.zaloplatforms.com/bot{token}/getUpdates",
                json={"timeout": 30},
            )
        except httpx.TimeoutException:
            raise RuntimeError("Chưa nhận được tin nhắn. Bấm Lấy Chat ID rồi nhắn lại cho bot.") from None
        except httpx.RequestError:
            raise RuntimeError("Không kết nối được Zalo. Kiểm tra mạng và thử lại.") from None
    try:
        data = response.json()
    except ValueError:
        raise RuntimeError(f"Zalo trả về dữ liệu không hợp lệ (HTTP {response.status_code}).") from None
    if not isinstance(data, dict) or response.status_code >= 400 or data.get("ok") is not True:
        detail = (data.get("description") or data.get("message") or data.get("error_code") or "Không nhận được dữ liệu") if isinstance(data, dict) else "Phản hồi không hợp lệ"
        detail = str(detail).replace(token, "[ẩn token]")[:500]
        raise RuntimeError(f"Không lấy được Chat ID: {detail}\nNếu bot đang dùng Webhook, hãy lấy ID từ hệ thống nhận Webhook; tool không tự xóa Webhook.")
    result = data.get("result")
    message = result.get("message") if isinstance(result, dict) else None
    chat = message.get("chat") if isinstance(message, dict) else None
    chat_id = chat.get("id") if isinstance(chat, dict) else None
    if not isinstance(chat_id, str) or not chat_id.strip():
        raise RuntimeError("Chưa nhận được tin nhắn có Chat ID. Bấm Lấy Chat ID rồi nhắn lại cho bot.")
    return chat_id.strip()


async def send_notification(text: str, settings=None):
    # Reload on each delivery so saving a channel change also affects a running watcher.
    settings = load_config().get("messenger", {}) if settings is None else settings
    provider = str(settings.get("notification_provider", "telegram")).strip().lower()
    if provider not in PROVIDERS:
        raise RuntimeError("Kênh gửi không hợp lệ. Hãy chọn Telegram hoặc Zalo trong SETUP.")
    label, base_url, limit = PROVIDERS[provider]
    token = str(settings.get(f"{provider}_bot_token", "")).strip()
    chat_id = str(settings.get(f"{provider}_chat_id", "")).strip()
    if not token or not chat_id:
        raise RuntimeError(f"Chưa cấu hình {label} Bot Token / Chat ID trong SETUP.")
    if not text or not text.strip():
        raise RuntimeError("Nội dung tin nhắn không được để trống.")

    # Count UTF-16 units conservatively; never split an emoji's surrogate pair.
    chunks, current, size = [], [], 0
    for char in text:
        units = 2 if ord(char) > 0xFFFF else 1
        if size + units > limit:
            chunks.append("".join(current))
            current, size = [], 0
        current.append(char)
        size += units
    if current:
        chunks.append("".join(current))

    result = None
    async with httpx.AsyncClient(timeout=20) as client:
        for chunk in chunks:
            try:
                response = await client.post(
                    f"{base_url}/bot{token}/sendMessage",
                    json={"chat_id": chat_id, "text": chunk},
                )
            except httpx.RequestError:
                # Request exceptions can contain the URL, which embeds the secret token.
                raise RuntimeError(f"Không kết nối được {label}. Kiểm tra mạng và thử lại.") from None
            try:
                result = response.json()
            except ValueError:
                raise RuntimeError(f"{label} trả về dữ liệu không hợp lệ (HTTP {response.status_code}).") from None
            if not isinstance(result, dict) or response.status_code >= 400 or result.get("ok") is not True:
                detail = (result.get("description") or result.get("message") or result.get("error_code") or "API không xác nhận gửi thành công") if isinstance(result, dict) else "Phản hồi không hợp lệ"
                detail = str(detail).replace(token, "[ẩn token]")[:500]
                raise RuntimeError(f"{label} API lỗi (HTTP {response.status_code}): {detail}")
    return result
