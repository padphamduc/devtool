@echo off
setlocal
chcp 65001 >nul
title DUCTOOL
cd /d "%~dp0"

set "DUCTOOL_HOME=%LOCALAPPDATA%\DUCTOOL"
set "VENV=%DUCTOOL_HOME%\.venv"
set "PYTHON=%VENV%\Scripts\python.exe"

if not exist "%PYTHON%" (
    echo Chua cai dat DUCTOOL. Dang mo SETUP...
    echo.
    call "%~dp0SETUP_APP.bat"
    if errorlevel 1 (
        echo.
        echo Cai dat chua thanh cong.
        pause
        exit /b 1
    )
)

if not exist "%PYTHON%" (
    echo [LOI] Khong tim thay:
    echo %PYTHON%
    pause
    exit /b 1
)

"%PYTHON%" "%~dp0ductool_app.py"
if errorlevel 1 (
    echo.
    echo [LOI] DUCTOOL vua dung voi ma loi %ERRORLEVEL%.
    echo Neu can, chup man hinh nay gui de kiem tra.
    pause
)
