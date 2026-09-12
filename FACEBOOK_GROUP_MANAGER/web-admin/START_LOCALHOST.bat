@echo off
chcp 65001 >nul
title DUC TOOL - Local Group Manager
setlocal
echo ╔══════════════════════════════════════╗
echo ║               DUC TOOL               ║
echo ╚══════════════════════════════════════╝
set "DUC_PHP=php"
where php >nul 2>nul
if errorlevel 1 set "DUC_PHP=C:\xampp\php\php.exe"
if not exist config.php copy /Y config.local.example.php config.php >nul
if not exist "%DUC_PHP%" (
  echo [LOI] Không tìm thấy PHP. Hãy cài XAMPP hoặc thêm PHP vào PATH.
  pause
  exit /b 1
)
"%DUC_PHP%" init-local.php
if errorlevel 1 pause & exit /b 1
start "" http://127.0.0.1:8787/login.php
echo Web đang chạy tại http://127.0.0.1:8787
echo API: http://127.0.0.1:8787/api/groups.php
echo Mật khẩu mặc định: DUC@12345
echo Không đóng cửa sổ này khi đang sử dụng.
"%DUC_PHP%" -S 127.0.0.1:8787
