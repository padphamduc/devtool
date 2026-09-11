import asyncio
from playwright.async_api import async_playwright
from app.chrome_selector import resolve_chrome
from app.messenger import _ensure_shared_chrome

async def main():
    number, port = resolve_chrome()
    print(f"Đang kiểm tra Chrome {number} - port {port}...")
    await asyncio.to_thread(_ensure_shared_chrome, number, port)
    async with async_playwright() as p:
        browser = await p.chromium.connect_over_cdp(f"http://127.0.0.1:{port}")
        print("KẾT NỐI THÀNH CÔNG")
        print(f"Chrome {number} dùng chung tại http://127.0.0.1:{port}")
        print("Tool test sẽ không đóng Chrome.")

if __name__ == "__main__":
    asyncio.run(main())
