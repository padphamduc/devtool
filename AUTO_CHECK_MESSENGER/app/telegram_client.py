import httpx
from .config import TELEGRAM_BOT_TOKEN, TELEGRAM_CHAT_ID

async def send_telegram(text: str):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        raise RuntimeError(
            r"Chưa cấu hình Telegram Bot Token / Chat ID trong DUCTOOL Settings"
        )

    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"

    async with httpx.AsyncClient(timeout=20) as client:
        response = await client.post(
            url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
            },
        )

    if response.status_code >= 400:
        detail = ""
        try:
            data = response.json()
            detail = data.get("description") or str(data)
        except Exception:
            detail = response.text[:500]

        raise RuntimeError(
            f"Telegram API lỗi {response.status_code}: {detail}"
        )

    return response.json()
