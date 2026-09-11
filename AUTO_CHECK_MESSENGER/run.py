import sys
from pathlib import Path

_cur_dir = Path(__file__).resolve().parent
if str(_cur_dir) not in sys.path:
    sys.path.insert(0, str(_cur_dir))

from app.config import DASHBOARD_PORT
import socket
import threading
import time
import webbrowser

import uvicorn


def _open_dashboard_when_ready():
    """Đợi server mở port xong rồi mở dashboard bằng trình duyệt mặc định."""
    host = "127.0.0.1"
    port = int(DASHBOARD_PORT)
    deadline = time.time() + 20

    while time.time() < deadline:
        try:
            with socket.create_connection((host, port), timeout=0.5):
                webbrowser.open(f"http://{host}:{port}")
                return
        except OSError:
            time.sleep(0.25)


def run_messenger_main():
    threading.Thread(target=_open_dashboard_when_ready, daemon=True).start()

    uvicorn.run(
        "app.main:app",
        host="127.0.0.1",
        port=DASHBOARD_PORT,
        reload=False,
        use_colors=False,
    )


if __name__ == "__main__":
    run_messenger_main()
