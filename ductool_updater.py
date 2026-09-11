# -*- coding: utf-8 -*-
from __future__ import annotations

import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path
from typing import Any, Dict, Optional, Tuple
from urllib.parse import urlparse


GITHUB_REPOSITORY = "padphamduc/devtool"
RELEASE_API_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/releases/latest"
VERSION_URL = f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/version.json"
FALLBACK_VERSION_URL = f"https://api.github.com/repos/{GITHUB_REPOSITORY}/contents/version.json"
DEFAULT_RELEASE_PAGE = f"https://github.com/{GITHUB_REPOSITORY}/releases/latest"
TRUSTED_DOWNLOAD_HOSTS = {
    "api.github.com",
    "github.com",
    "objects.githubusercontent.com",
    "release-assets.githubusercontent.com",
    "raw.githubusercontent.com",
}


def _resource_root() -> Path:
    bundle_dir = getattr(sys, "_MEIPASS", None)
    if bundle_dir:
        return Path(bundle_dir)
    return Path(__file__).resolve().parent


def _read_local_version() -> str:
    try:
        data = json.loads((_resource_root() / "version.json").read_text(encoding="utf-8-sig"))
        version = str(data.get("version", "")).strip()
        if version:
            return version
    except (OSError, ValueError, TypeError):
        pass
    return "1.1.0"


CURRENT_VERSION = _read_local_version()


def parse_version(value: str) -> Tuple[int, int, int, int]:
    """Chuyển v1.2.3 thành tuple để so sánh phiên bản ổn định."""
    numbers = [int(item) for item in re.findall(r"\d+", str(value))[:4]]
    numbers.extend([0] * (4 - len(numbers)))
    return tuple(numbers)  # type: ignore[return-value]


def _as_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def _request_json(url: str, timeout: int = 8) -> Any:
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/vnd.github+json, application/json",
            "Cache-Control": "no-cache",
            "Pragma": "no-cache",
            "User-Agent": f"DUCTOOL-Updater/{CURRENT_VERSION}",
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        return json.loads(response.read().decode("utf-8-sig"))


def _fetch_version_policy() -> Optional[Dict[str, Any]]:
    try:
        data = _request_json(VERSION_URL)
        return data if isinstance(data, dict) else None
    except Exception:
        pass

    try:
        payload = _request_json(FALLBACK_VERSION_URL)
        encoded = payload.get("content", "") if isinstance(payload, dict) else ""
        data = json.loads(base64.b64decode(encoded).decode("utf-8-sig"))
        return data if isinstance(data, dict) else None
    except Exception:
        return None


def _find_asset(release: Dict[str, Any], name: str) -> Dict[str, Any]:
    for asset in release.get("assets", []):
        if isinstance(asset, dict) and str(asset.get("name", "")).lower() == name.lower():
            return asset
    return {}


def _asset_digest(asset: Dict[str, Any]) -> str:
    digest = str(asset.get("digest", "") or "").strip().lower()
    if digest.startswith("sha256:"):
        digest = digest.split(":", 1)[1]
    return digest if re.fullmatch(r"[a-f0-9]{64}", digest) else ""


def fetch_latest_version_info() -> Optional[Dict[str, Any]]:
    """
    Chỉ coi một phiên bản là sẵn sàng khi GitHub Release đã được xuất bản.
    version.json vẫn giữ chính sách bắt buộc cập nhật và nội dung thông báo.
    """
    policy = _fetch_version_policy() or {}

    try:
        release = _request_json(RELEASE_API_URL)
    except Exception:
        release = None

    if isinstance(release, dict) and not release.get("draft"):
        latest_version = str(release.get("tag_name", "")).strip().lstrip("vV")
        if latest_version:
            exe_asset = _find_asset(release, "DUCTOOL.exe")
            setup_asset = _find_asset(release, "DUCTOOL-Setup.exe")
            sums_asset = _find_asset(release, "SHA256SUMS.txt")
            policy_matches = parse_version(policy.get("version", "0")) == parse_version(latest_version)

            return {
                "version": latest_version,
                "min_version": policy.get("min_version", "0.0.0") if policy_matches else "0.0.0",
                "force_update": policy.get("force_update", False) if policy_matches else False,
                "title": (
                    policy.get("title") if policy_matches else None
                ) or release.get("name") or f"Bản cập nhật {latest_version}",
                "changelog": (
                    policy.get("changelog") if policy_matches else None
                ) or release.get("body") or "Cập nhật nâng cấp và vá lỗi.",
                "exe_url": exe_asset.get("browser_download_url", "") or policy.get("exe_url", ""),
                "setup_url": setup_asset.get("browser_download_url", "") or policy.get("setup_url", ""),
                "checksum_url": sums_asset.get("browser_download_url", "") or policy.get("checksum_url", ""),
                "exe_sha256": _asset_digest(exe_asset),
                "setup_sha256": _asset_digest(setup_asset),
                "release_page": release.get("html_url") or policy.get("release_page") or DEFAULT_RELEASE_PAGE,
            }

    # Tương thích khi repository chưa có Release. URL tải có thể trống; lúc đó
    # giao diện sẽ hướng người dùng tới trang Releases thay vì tải file sai.
    return policy or None


def check_update_status() -> Dict[str, Any]:
    info = fetch_latest_version_info()
    if not info:
        return {
            "has_update": False,
            "is_force": False,
            "error": "Không thể kết nối đến máy chủ cập nhật",
            "current_version": CURRENT_VERSION,
        }

    latest_version = str(info.get("version", CURRENT_VERSION)).strip()
    min_version = str(info.get("min_version", "0.0.0")).strip()
    has_update = parse_version(latest_version) > parse_version(CURRENT_VERSION)
    is_force = (_as_bool(info.get("force_update")) and has_update) or (
        parse_version(CURRENT_VERSION) < parse_version(min_version)
    )

    return {
        "has_update": has_update,
        "is_force": is_force,
        "current_version": CURRENT_VERSION,
        "latest_version": latest_version,
        "min_version": min_version,
        "title": info.get("title", f"Bản cập nhật {latest_version}"),
        "changelog": info.get("changelog", "Cập nhật nâng cấp và vá lỗi."),
        "exe_url": info.get("exe_url", ""),
        "setup_url": info.get("setup_url", ""),
        "checksum_url": info.get("checksum_url", ""),
        "exe_sha256": info.get("exe_sha256", ""),
        "setup_sha256": info.get("setup_sha256", ""),
        "release_page": info.get("release_page", DEFAULT_RELEASE_PAGE),
    }


def _trusted_url(url: str) -> bool:
    try:
        parsed = urlparse(url)
        host = (parsed.hostname or "").lower()
        return parsed.scheme == "https" and (
            host in TRUSTED_DOWNLOAD_HOSTS or host.endswith(".githubusercontent.com")
        )
    except Exception:
        return False


def _download(url: str, target: Path, progress_callback=None) -> None:
    if not _trusted_url(url):
        raise ValueError("Link cập nhật không thuộc GitHub chính thức.")

    request = urllib.request.Request(
        url,
        headers={"Accept": "application/octet-stream", "User-Agent": f"DUCTOOL-Updater/{CURRENT_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as output:
        final_url = response.geturl()
        if not _trusted_url(final_url):
            raise ValueError("GitHub chuyển hướng tới địa chỉ tải không tin cậy.")

        total_size = int(response.headers.get("Content-Length", 0) or 0)
        downloaded = 0
        while True:
            chunk = response.read(128 * 1024)
            if not chunk:
                break
            output.write(chunk)
            downloaded += len(chunk)
            if progress_callback and total_size > 0:
                progress_callback(downloaded, total_size)


def _checksum_from_file(checksum_url: str, asset_name: str) -> str:
    if not checksum_url or not _trusted_url(checksum_url):
        return ""
    request = urllib.request.Request(
        checksum_url,
        headers={"User-Agent": f"DUCTOOL-Updater/{CURRENT_VERSION}"},
    )
    with urllib.request.urlopen(request, timeout=15) as response:
        if not _trusted_url(response.geturl()):
            return ""
        content = response.read(256 * 1024).decode("ascii", errors="ignore")

    for line in content.splitlines():
        match = re.match(r"^([a-fA-F0-9]{64})\s+\*?(.+?)\s*$", line)
        if match and Path(match.group(2)).name.lower() == asset_name.lower():
            return match.group(1).lower()
    return ""


def _verify_windows_binary(path: Path, expected_sha256: str = "") -> None:
    if not path.exists() or path.stat().st_size < 1_000_000:
        raise ValueError("File tải về không hợp lệ hoặc quá nhỏ.")
    with path.open("rb") as handle:
        if handle.read(2) != b"MZ":
            raise ValueError("File cập nhật không phải ứng dụng Windows hợp lệ.")

    expected = str(expected_sha256 or "").strip().lower()
    if expected:
        digest = hashlib.sha256()
        with path.open("rb") as handle:
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                digest.update(chunk)
        if digest.hexdigest() != expected:
            raise ValueError("Mã SHA-256 không khớp; bản cập nhật đã bị hỏng hoặc thay đổi.")


def _start_installer(installer_path: Path) -> None:
    subprocess.Popen(
        [
            str(installer_path),
            "/VERYSILENT",
            "/SUPPRESSMSGBOXES",
            "/NORESTART",
            "/CLOSEAPPLICATIONS",
            "/RESTARTAPPLICATIONS",
        ],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NEW_PROCESS_GROUP", 0),
    )


def _schedule_portable_replace(downloaded_file: Path) -> None:
    current_exe = Path(sys.executable).resolve()
    backup_file = current_exe.with_suffix(current_exe.suffix + ".old")
    updater_bat = Path(tempfile.gettempdir()) / f"ductool_apply_update_{os.getpid()}.bat"

    def batch_value(value: Path) -> str:
        return str(value).replace("%", "%%")

    bat_content = f"""@echo off
chcp 65001 >nul
setlocal
set "CURRENT={batch_value(current_exe)}"
set "NEWFILE={batch_value(downloaded_file)}"
set "BACKUP={batch_value(backup_file)}"

timeout /t 2 /nobreak >nul
taskkill /F /IM "{current_exe.name}" >nul 2>&1
timeout /t 1 /nobreak >nul

copy /Y "%CURRENT%" "%BACKUP%" >nul 2>&1
move /Y "%NEWFILE%" "%CURRENT%" >nul 2>&1
if errorlevel 1 goto update_failed

start "" "%CURRENT%"
timeout /t 3 /nobreak >nul
del /Q "%BACKUP%" >nul 2>&1
del /Q "%~f0" >nul 2>&1
exit /b 0

:update_failed
if exist "%BACKUP%" copy /Y "%BACKUP%" "%CURRENT%" >nul 2>&1
start "" "%CURRENT%"
echo Khong the cap nhat DUCTOOL. Hay tai bo cai moi tu GitHub.>"%TEMP%\\DUCTOOL-update-error.txt"
exit /b 1
"""
    updater_bat.write_text(bat_content, encoding="utf-8-sig")
    subprocess.Popen(
        ["cmd.exe", "/c", str(updater_bat)],
        close_fds=True,
        creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
    )


def perform_auto_replace(
    exe_url: str,
    progress_callback=None,
    *,
    setup_url: str = "",
    checksum_url: str = "",
    exe_sha256: str = "",
    setup_sha256: str = "",
) -> Tuple[bool, str]:
    """Tải và chạy bộ cài mới; fallback ghi đè EXE cho bản portable cũ."""
    if not getattr(sys, "frozen", False):
        return False, "Đang chạy từ mã nguồn Python nên không thể tự cập nhật file thực thi."

    download_url = setup_url or exe_url
    if not download_url:
        return False, "Release mới chưa có file cài đặt để tải."

    asset_name = "DUCTOOL-Setup.exe" if setup_url else "DUCTOOL.exe"
    expected_hash = setup_sha256 if setup_url else exe_sha256
    suffix = "-Setup.exe" if setup_url else ".exe"
    fd, temp_name = tempfile.mkstemp(prefix="DUCTOOL-update-", suffix=suffix)
    os.close(fd)
    downloaded_file = Path(temp_name)

    try:
        _download(download_url, downloaded_file, progress_callback)
        if not expected_hash:
            expected_hash = _checksum_from_file(checksum_url, asset_name)
        _verify_windows_binary(downloaded_file, expected_hash)

        if setup_url:
            _start_installer(downloaded_file)
            return True, "Đã tải xong bộ cài. Ứng dụng sẽ tự cài và mở lại."

        _schedule_portable_replace(downloaded_file)
        return True, "Đã tải xong. Ứng dụng sẽ tự thay thế và mở lại."
    except Exception as exc:
        try:
            downloaded_file.unlink(missing_ok=True)
        except OSError:
            pass
        return False, f"Lỗi trong quá trình cập nhật tự động: {exc}"
