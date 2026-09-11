@echo off
cd /d "%~dp0"
echo.
echo 1 = Chrome 1 - port 9311
echo 2 = Chrome 2 - port 9312
echo 3 = Chrome 3 - port 9313
echo 4 = Chrome 4 - port 9314
echo.
set /p C=Chon Chrome [1-4]: 
python -c "from app.chrome_selector import save_selection; save_selection(int('%C%')); print('Da chon Chrome %C%')"
pause
