import asyncio
from app.telegram_client import send_telegram

async def main():
    result = await send_telegram("✅ Test Messenger Watcher → Telegram")
    print("GỬI TELEGRAM THÀNH CÔNG")
    print("message_id:", result.get("result", {}).get("message_id"))

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except Exception as exc:
        print("GỬI TELEGRAM THẤT BẠI:")
        print(exc)
