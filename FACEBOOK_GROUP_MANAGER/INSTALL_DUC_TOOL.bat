@echo off
chcp 65001 >nul
title DUC TOOL - Cài đặt Facebook Group List
setlocal

echo ╔══════════════════════════════════════╗
echo ║               DUC TOOL               ║
echo ╚══════════════════════════════════════╝
echo.

set "DUC_EXT_DIR=C:\ducextend"
set "DUC_SOURCE_DIR=%~dp0facebook-group-list-extension"

if not exist "%DUC_SOURCE_DIR%\manifest.json" (
  echo [LOI] Không tìm thấy thư mục facebook-group-list-extension.
  echo Hãy giải nén đầy đủ file ZIP rồi chạy lại.
  pause
  exit /b 1
)

if not exist "%DUC_EXT_DIR%" mkdir "%DUC_EXT_DIR%"
xcopy "%DUC_SOURCE_DIR%\*" "%DUC_EXT_DIR%\" /E /I /Y >nul

if errorlevel 1 (
  echo [LOI] Không thể chép extension vào %DUC_EXT_DIR%.
  echo Hãy bấm chuột phải file này và chọn Run as administrator.
  pause
  exit /b 1
)

echo [OK] Đã cài hoặc cập nhật tại: %DUC_EXT_DIR%
echo.
echo Lần đầu: bật Developer mode, chọn Load unpacked và mở C:\ducextend
echo Cập nhật: chạy lại file này, sau đó bấm Reload tại chrome://extensions
echo.
start "" chrome.exe "chrome://extensions"
explorer.exe "%DUC_EXT_DIR%"
pause
