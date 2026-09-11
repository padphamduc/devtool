@echo off
setlocal
chcp 65001 >nul
title DUCTOOL - SETUP
cd /d "%~dp0"

set "DUCTOOL_HOME=%LOCALAPPDATA%\DUCTOOL"
set "VENV=%DUCTOOL_HOME%\.venv"

if not exist "%DUCTOOL_HOME%" mkdir "%DUCTOOL_HOME%"

echo ============================================================
echo DUCTOOL - CAI DAT
echo ============================================================
echo.
echo Thu muc app:
echo %CD%
echo.
echo Moi truong Python:
echo %VENV%
echo.

where py >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=py -3"
    goto :HAVE_PY
)

where python >nul 2>nul
if not errorlevel 1 (
    set "PY_CMD=python"
    goto :HAVE_PY
)

echo [LOI] Khong tim thay Python.
echo Cai Python 3.10+ va tick "Add Python to PATH".
echo.
pause
exit /b 1

:HAVE_PY
if not exist "%VENV%\Scripts\python.exe" (
    echo Dang tao moi truong Python...
    %PY_CMD% -m venv "%VENV%"
    if errorlevel 1 (
        echo.
        echo [LOI] Khong tao duoc moi truong Python.
        echo Thu chay file nay bang quyen Administrator hoac kiem tra antivirus.
        pause
        exit /b 1
    )
)

echo Dang cai thu vien...
"%VENV%\Scripts\python.exe" -m pip install --upgrade pip
if errorlevel 1 goto :INSTALL_ERROR

"%VENV%\Scripts\python.exe" -m pip install -r "%~dp0requirements.txt"
if errorlevel 1 goto :INSTALL_ERROR

echo Dang cai Playwright Chromium...
"%VENV%\Scripts\python.exe" -m playwright install chromium
if errorlevel 1 goto :INSTALL_ERROR

echo.
echo ============================================================
echo CAI DAT XONG
echo Chay START_DUCTOOL.bat
echo ============================================================
echo.
pause
exit /b 0

:INSTALL_ERROR
echo.
echo [LOI] Cai dat thu vien that bai.
echo Kiem tra Internet / antivirus roi thu lai.
echo.
pause
exit /b 1
