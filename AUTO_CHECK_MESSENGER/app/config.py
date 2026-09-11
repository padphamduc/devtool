from pathlib import Path
import sys
ROOT_DIR = Path(__file__).resolve().parents[2]
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
from ductool_config import load_config

_CFG = load_config()
_MSG = _CFG.get("messenger", {})
TELEGRAM_BOT_TOKEN = str(_MSG.get("telegram_bot_token", "")).strip()
TELEGRAM_CHAT_ID = str(_MSG.get("telegram_chat_id", "")).strip()
POLL_SECONDS = max(5, int(_MSG.get("poll_seconds", 30)))
MAX_MESSAGE_AGE_MINUTES = max(1, int(_MSG.get("max_age_minutes") or _MSG.get("max_message_age_minutes", 30)))
DEDUPE_HOURS = max(1, int(_MSG.get("dedupe_hours", 24)))
MESSENGER_INBOX_URL = str(_MSG.get("inbox_url", "https://www.messenger.com/")).strip()
MESSENGER_REQUESTS_URL = str(_MSG.get("requests_url", "https://www.messenger.com/requests/")).strip()
MESSENGER_SPAM_URL = str(_MSG.get("spam_url", "https://www.messenger.com/requests/spam/")).strip()
FB_NOTIFICATIONS_URL = str(_MSG.get("notifications_url", "https://www.facebook.com/notifications")).strip()
CHECK_NOTIFICATIONS = bool(_MSG.get("check_notifications", True))
DASHBOARD_PORT = max(1024, int(_MSG.get("dashboard_port", 8000)))
