import hashlib
import re
import sqlite3
from pathlib import Path
from datetime import datetime

try:
    from ductool_config import CONFIG_PATH
    DB_PATH = CONFIG_PATH.parent / "messages.db"
except Exception:
    DB_PATH = Path.home() / "DUCTOOL" / "messages.db"


def _conn():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS seen_messages (
            fingerprint TEXT PRIMARY KEY,
            source TEXT,
            sender TEXT,
            preview TEXT,
            created_at TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS thread_state (
            thread_key TEXT PRIMARY KEY,
            source TEXT,
            sender TEXT,
            href TEXT,
            normalized_preview TEXT,
            last_age_minutes INTEGER,
            last_seen_at TEXT
        )
    """)
    conn.commit()
    return conn


def normalize_preview(value: str) -> str:
    """
    Chuẩn hóa preview nhưng loại bỏ timestamp tương đối của Messenger.
    Vì vậy "Xin chào · 1 phút" và "Xin chào · 2 phút" được coi là
    cùng một snapshot nội dung, không phải hai tin nhắn mới.
    """
    value = (value or "").lower()

    # Remove Vietnamese relative time.
    value = re.sub(
        r'(?<!\d)\d+\s*(?:phút|giờ|ngày)(?:\s*trước)?',
        ' ',
        value,
        flags=re.I,
    )

    # Remove English long relative time.
    value = re.sub(
        r'(?<!\d)\d+\s*(?:min(?:ute)?s?|hours?|days?)(?:\s*ago)?',
        ' ',
        value,
        flags=re.I,
    )

    # Remove compact 1m / 2h / 3d.
    value = re.sub(r'(?<!\d)\d+\s*[mhd]\b', ' ', value, flags=re.I)

    # Remove "now" variants.
    value = re.sub(
        r'\b(?:just now|now|vừa xong|bây giờ)\b',
        ' ',
        value,
        flags=re.I,
    )

    # Clean separators left behind by removed timestamp.
    value = re.sub(r'\s*[·•]\s*$', '', value)
    value = re.sub(r'\s+', ' ', value).strip(" ·•-|")
    return value.strip()


def make_thread_key(source: str, sender: str, href: str) -> str:
    # href is the best stable identity for a Messenger conversation.
    identity = href.strip().lower() if href else sender.strip().lower()
    raw = f"{source.strip().lower()}|{identity}"
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def get_thread_state(source: str, sender: str, href: str):
    key = make_thread_key(source, sender, href)
    with _conn() as conn:
        row = conn.execute(
            """
            SELECT normalized_preview, last_age_minutes
            FROM thread_state
            WHERE thread_key=?
            """,
            (key,),
        ).fetchone()

    if not row:
        return None
    return {
        "normalized_preview": row[0] or "",
        "last_age_minutes": row[1],
    }


def update_thread_state(
    source: str,
    sender: str,
    href: str,
    preview: str,
    age_minutes: int | None,
):
    key = make_thread_key(source, sender, href)
    normalized = normalize_preview(preview)
    now = datetime.now().isoformat(timespec="seconds")

    with _conn() as conn:
        conn.execute(
            """
            INSERT INTO thread_state(
                thread_key, source, sender, href,
                normalized_preview, last_age_minutes, last_seen_at
            )
            VALUES(?,?,?,?,?,?,?)
            ON CONFLICT(thread_key) DO UPDATE SET
                source=excluded.source,
                sender=excluded.sender,
                href=excluded.href,
                normalized_preview=excluded.normalized_preview,
                last_age_minutes=excluded.last_age_minutes,
                last_seen_at=excluded.last_seen_at
            """,
            (
                key, source, sender, href,
                normalized, age_minutes, now,
            ),
        )
        conn.commit()


def is_new_message_snapshot(
    source: str,
    sender: str,
    href: str,
    preview: str,
    age_minutes: int | None,
) -> bool:
    """
    Quy tắc:
    - Chưa từng thấy thread snapshot => mới.
    - Nội dung preview thay đổi => mới.
    - Cùng nội dung nhưng age reset nhỏ hơn lần trước => tin mới giống nội dung cũ.
    - Cùng nội dung và age giữ nguyên/tăng 1 -> 2 -> 3... => KHÔNG mới.
    """
    state = get_thread_state(source, sender, href)
    if state is None:
        return True

    current = normalize_preview(preview)
    previous = state["normalized_preview"]

    if current != previous:
        return True

    old_age = state["last_age_minutes"]
    if age_minutes is not None and old_age is not None and age_minutes < old_age:
        return True

    return False
