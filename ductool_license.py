# -*- coding: utf-8 -*-
from __future__ import annotations

import hashlib
import csv
import io
import unicodedata
import email.utils
import json
import os
import platform
import re
import subprocess
import sys
import time
import urllib.parse
import urllib.request
import urllib.error
from datetime import datetime, timezone
from pathlib import Path

# Thư mục lưu dữ liệu bản quyền nội bộ
DATA_DIR = Path(r"C:\duc")
LICENSE_CACHE_FILE = DATA_DIR / "license.dat"

# Secret salt để ký HMAC cache bản quyền offline (chống khách tự sửa file license.dat)
CACHE_SALT = "DUC_TOOL_SECRET_SALT_2026_@v20"

# Link Google Sheet chính thức của bạn
DEFAULT_LICENSE_URL = "https://docs.google.com/spreadsheets/d/1-M7C_FKjCYAdeWOCKgYjuDRluyTNYfofpuJlhU5Jcr8/edit?gid=0#gid=0"


def get_license_url() -> str:
    """Lấy URL Google Sheet hoặc Google Apps Script từ config.json hoặc mặc định."""
    try:
        from ductool_config import load_config
        cfg = load_config()
        url = str(cfg.get("license", {}).get("api_url", "") or "").strip()
        if url:
            return url
    except Exception:
        pass
    return DEFAULT_LICENSE_URL


def get_saved_key() -> str:
    """Lấy mã License Key mà khách đã lưu trong config.json."""
    try:
        from ductool_config import load_config
        cfg = load_config()
        return str(cfg.get("license", {}).get("key", "") or "").strip()
    except Exception:
        return ""


def save_license_key(key: str):
    """Lưu mã License Key vào config.json."""
    try:
        from ductool_config import load_config, save_config
        cfg = load_config()
        cfg.setdefault("license", {})["key"] = key.strip().upper()
        save_config(cfg)
    except Exception:
        pass


def get_hwid() -> str:
    """
    Lấy Mã Máy (HWID) duy nhất từ phần cứng Windows.
    Kết hợp UUID bo mạch chủ (Motherboard UUID) và Windows MachineGuid.
    Đảm bảo 1 máy tính chỉ có duy nhất 1 mã cố định.
    """
    raw_id = ""

    # 1. Lấy UUID bo mạch chủ qua wmic
    try:
        cmd = "wmic csproduct get uuid"
        output = subprocess.check_output(cmd, shell=True, stderr=subprocess.DEVNULL).decode().split()
        if len(output) > 1 and "UUID" not in output[1]:
            raw_id = output[1].strip()
    except Exception:
        raw_id = ""

    # 2. Nếu wmic không được hoặc trả về rác, lấy Windows MachineGuid từ Registry
    if not raw_id or raw_id == "FFFFFFFF-FFFF-FFFF-FFFF-FFFFFFFFFFFF":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, r"SOFTWARE\Microsoft\Cryptography") as key:
                raw_id, _ = winreg.QueryValueEx(key, "MachineGuid")
        except Exception:
            raw_id = ""

    # 3. Fallback theo tên máy và thông số CPU
    if not raw_id:
        raw_id = platform.node() + "-" + platform.processor() + "-" + os.environ.get("USERNAME", "")

    # Băm SHA256 tạo mã máy định dạng: DUC-XXXX-XXXX-XXXX
    h = hashlib.sha256((raw_id.strip() + "DUC_HWID_SEED").encode("utf-8")).hexdigest().upper()
    return f"DUC-{h[:4]}-{h[4:8]}-{h[8:12]}"


def _compute_cache_sig(hwid: str, key: str, expire_date: str, timestamp: int, hwid_bound: bool = True) -> str:
    """Tạo chữ ký bảo vệ file cache tránh bị khách hàng chỉnh sửa ngày giờ."""
    payload = f"LICENSE_V3|{hwid}|{key}|{expire_date}|{timestamp}|{hwid_bound}|{CACHE_SALT}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def save_license_cache(hwid: str, key: str, expire_date: str, hwid_bound: bool = True):
    """Lưu cache bản quyền xuống C:\\duc\\license.dat."""
    try:
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        now_ts = int(time.time())
        sig = _compute_cache_sig(hwid, key, expire_date, now_ts, hwid_bound)
        data = {
            "hwid": hwid,
            "key": key,
            "expire_date": expire_date,
            "timestamp": now_ts,
            "sig": sig,
            "hwid_bound": hwid_bound,
        }
        LICENSE_CACHE_FILE.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    except Exception:
        pass


def get_cached_license(hwid: str, key: str = "") -> dict | None:
    """
    Đọc cache bản quyền đã lưu.
    Cho phép sử dụng offline trong tối đa 24 giờ kể từ lần xác thực online gần nhất.
    """
    if not LICENSE_CACHE_FILE.exists():
        return None

    try:
        data = json.loads(LICENSE_CACHE_FILE.read_text(encoding="utf-8"))
        if data.get("hwid") != hwid:
            return None

        cached_key = data.get("key", "")
        if not key or key.strip().upper() != cached_key.strip().upper():
            return None

        expire_date = data.get("expire_date", "")
        ts = int(data.get("timestamp", 0))
        sig = data.get("sig", "")

        # Kiểm tra chữ ký tính toàn vẹn
        bound = data.get("hwid_bound") is True
        if _compute_cache_sig(hwid, cached_key, expire_date, ts, bound) != sig:
            return None

        # Kiểm tra thời hạn cache offline (tối đa 24 giờ = 86400 giây)
        now_ts = int(time.time())
        if not 0 <= (now_ts - ts) <= 86400:
            return None

        # Kiểm tra ngày hết hạn
        exp = _parse_date_str(expire_date)
        if not exp:
            return None

        now_dt = datetime.now().date()
        if now_dt > exp:
            return None

        days_left = (exp - now_dt).days
        return {
            "status": "ACTIVE",
            "key": cached_key,
            "expire_date": expire_date,
            "days_left": days_left,
            "cached": True,
            "hwid": hwid,
            "hwid_bound": bound,
            "message": "Bản quyền hợp lệ (Cached)"
        }
    except Exception:
        return None


def _parse_date_str(s: str):
    """Chuyển đổi chuỗi ngày thành datetime.date (hỗ trợ YYYY-MM-DD, DD/MM/YYYY, MM/DD/YYYY)."""
    s = str(s).strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y", "%m/%d/%Y", "%d-%m-%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            pass
    return None


def _license_header(value):
    value = unicodedata.normalize("NFD", value.lower().replace("đ", "d"))
    return re.sub(r"[^a-z0-9]", "", value)


def check_license_sheet(url, hwid, key, timeout=12):
    """Read the existing public sheet. Only its HWID column can bind a key."""
    match = re.search(r"/spreadsheets/d/([a-zA-Z0-9_-]+)", url)
    if not match:
        return {"status": "ERROR", "message": "Link kiểm tra key không hợp lệ."}
    gid_match = re.search(r"[#&?]gid=(\d+)", url)
    gid = gid_match.group(1) if gid_match else "0"
    csv_url = f"https://docs.google.com/spreadsheets/d/{match.group(1)}/export?format=csv&gid={gid}"
    req = urllib.request.Request(csv_url, headers={"User-Agent": "DUCTOOL-License/3.0", "Cache-Control": "no-cache"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as response:
            rows = list(csv.reader(io.StringIO(response.read().decode("utf-8-sig"))))
            today = datetime.now().date()
            if response.headers.get("Date"):
                try:
                    today = email.utils.parsedate_to_datetime(response.headers["Date"]).date()
                except (TypeError, ValueError):
                    pass
        if not rows:
            return {"status": "NOT_FOUND", "message": "Chưa có dữ liệu key."}
        headers = [_license_header(value) for value in rows[0]]
        aliases = {"key": ("makey", "key", "licensekey"), "hwid": ("mamayhwid", "mamay", "hwid"),
                   "expiry": ("ngayhethan", "expiredate"), "status": ("trangthai", "status")}
        cols = {}
        for name, names in aliases.items():
            indexes = [i for i, header in enumerate(headers) if header in names]
            if len(indexes) != 1:
                return {"status": "ERROR", "message": "Cột dữ liệu bản quyền chưa hợp lệ. Liên hệ Admin."}
            cols[name] = indexes[0]
        def cell(row, name):
            i = cols[name]
            return row[i].strip() if i < len(row) else ""
        matches = [row for row in rows[1:] if cell(row, "key").upper() == key]
        if not matches:
            return {"status": "NOT_FOUND", "message": "Không tìm thấy key trong hệ thống."}
        if len(matches) != 1:
            return {"status": "ERROR", "message": "Key bị trùng trong hệ thống. Liên hệ Admin."}
        row = matches[0]
        state = _license_header(cell(row, "status"))
        if state in ("blocked", "block", "khoa"):
            return {"status": "BLOCKED", "message": "Key đã bị khóa."}
        if state not in ("active", "hoatdong", "ok"):
            return {"status": "ERROR", "message": "Key chưa được phép kích hoạt."}
        expiry = _parse_date_str(cell(row, "expiry"))
        if not expiry:
            return {"status": "ERROR", "message": "Ngày hết hạn không hợp lệ."}
        if today > expiry:
            return {"status": "EXPIRED", "expire_date": expiry.isoformat(), "message": "Key đã hết hạn."}
        assigned = cell(row, "hwid").upper()
        if assigned and assigned != hwid:
            return {"status": "HWID_MISMATCH", "message": "Key đã được cấp cho máy khác."}
        save_license_key(key)
        save_license_cache(hwid, key, expiry.isoformat(), hwid_bound=bool(assigned))
        return {"status": "ACTIVE", "key": key, "hwid": hwid, "hwid_bound": bool(assigned),
                "expire_date": expiry.isoformat(), "days_left": (expiry - today).days,
                "message": "Bản quyền hợp lệ."}
    except urllib.error.HTTPError:
        return {"status": "ERROR", "message": "Không đọc được link kiểm tra key. Liên hệ Admin."}
    except (urllib.error.URLError, OSError, TimeoutError):
        return get_cached_license(hwid, key) or {"status": "NETWORK_ERROR", "message": "Không kết nối được để kiểm tra key. Vui lòng thử lại."}


def check_license_online(hwid: str, key: str = "", timeout: int = 12, *, activate: bool = False) -> dict:
    """Check a bound key; only an explicit activation may bind a new machine."""
    url = get_license_url()
    hwid_clean, key_clean = hwid.strip().upper(), key.strip().upper()
    if not key_clean:
        return {"status": "NOT_FOUND", "message": "Vui lòng nhập key bản quyền."}
    if not re.fullmatch(r"DUC-[A-F0-9]{4}-[A-F0-9]{4}-[A-F0-9]{4}", hwid_clean):
        return {"status": "ERROR", "message": "Không xác định được mã máy hợp lệ."}
    parsed = urllib.parse.urlparse(url)
    if parsed.scheme == "https" and parsed.hostname == "docs.google.com":
        return check_license_sheet(url, hwid_clean, key_clean, timeout)
    if parsed.scheme != "https" or parsed.hostname != "script.google.com" or not parsed.path.endswith("/exec"):
        return {"status": "NOT_CONFIGURED", "message": "Máy chủ kích hoạt chưa được cấu hình. Vui lòng liên hệ Admin."}
    payload = {"hwid": hwid_clean, "key": key_clean, "action": "activate" if activate else "check"}
    req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), method="POST",
        headers={"Content-Type": "application/json", "Accept": "application/json", "User-Agent": "DUCTOOL-License/2.0"})
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            data = json.loads(resp.read().decode("utf-8"))
        if not isinstance(data, dict) or not isinstance(data.get("status"), str):
            return {"status": "ERROR", "message": "Phản hồi kiểm tra key không hợp lệ."}
        if data["status"] == "ACTIVE":
            if (data.get("hwid_bound") is not True or str(data.get("hwid", "")).upper() != hwid_clean
                    or str(data.get("key", "")).upper() != key_clean or not _parse_date_str(data.get("expire_date", ""))):
                return {"status": "ERROR", "message": "Máy chủ chưa xác nhận key được gắn với máy này."}
            save_license_key(key_clean)
            save_license_cache(hwid_clean, key_clean, data["expire_date"])
        return data
    except (urllib.error.URLError, TimeoutError, OSError):
        # A new activation must receive an online acknowledgement of the binding.
        if not activate:
            cached = get_cached_license(hwid_clean, key_clean)
            if cached:
                return cached
        return {"status": "NETWORK_ERROR", "message": "Không kết nối được máy chủ kiểm tra key. Vui lòng thử lại."}
    except (ValueError, TypeError):
        return {"status": "ERROR", "message": "Máy chủ trả về dữ liệu không hợp lệ. Vui lòng liên hệ Admin."}


def check_license_quick() -> tuple[bool, str, dict]:
    """
    Kiểm tra nhanh bản quyền máy hiện tại.
    Ưu tiên lấy key đã lưu trong máy.
    Trả về: (is_valid: bool, status: str, full_info: dict)
    """
    hwid = get_hwid()
    saved_key = get_saved_key()

    # Kiểm tra cache trước để mở app tức thì
    cached = get_cached_license(hwid, saved_key)
    if cached:
        return True, "ACTIVE", cached

    res = check_license_online(hwid, saved_key, timeout=8)
    status = res.get("status", "ERROR")
    return (status == "ACTIVE"), status, res


def verify_license_or_exit(module_name: str = "DUCTOOL"):
    """
    Hàm bảo vệ cho các module chạy ngầm/CLI.
    Nếu chưa kích hoạt bản quyền, in thông báo ra console và dừng chương trình.
    """
    valid, status, info = check_license_quick()
    if not valid:
        hwid = get_hwid()
        saved_key = get_saved_key()
        print("\n" + "=" * 62)
        print(f" [!] BẢN QUYỀN CHƯA KÍCH HOẠT — {module_name}")
        print("=" * 62)
        print(f" Mã máy của bạn : {hwid}")
        if saved_key:
            print(f" Mã Key đã lưu  : {saved_key}")
        if status == "EXPIRED":
            print(f" Trạng thái     : Bản quyền đã hết hạn vào ngày {info.get('expire_date')}.")
        elif status == "BLOCKED":
            print(" Trạng thái     : Key / Mã máy này đã bị tạm khóa.")
        elif status == "NOT_FOUND":
            print(" Trạng thái     : Chưa kích hoạt Key bản quyền trong hệ thống.")
        elif status == "HWID_MISMATCH":
            print(" Trạng thái     : Mã Key này thuộc về máy khác, không thể dùng trên máy này.")
        else:
            print(f" Trạng thái     : {info.get('message', status)}")
        print("\n Vui lòng mở DUCTOOL.exe và nhập Key bản quyền để kích hoạt.")
        print("=" * 62)
        try:
            input("\n Nhấn Enter để thoát...")
        except Exception:
            pass
        sys.exit(1)
