@echo off
setlocal
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" (
    echo [WinCare Manager] Sanal ortam bulunamadi.
    echo PowerShell ile once su komutu calistirin:
    echo     powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
    pause
    exit /b 1
)

rem pythonw hatalari sessizce yutar; once paketlerin yuklenebildigini gorunur sekilde kontrol et.
".venv\Scripts\python.exe" -c "import PySide6.QtWidgets, psutil" 2>nul
if errorlevel 1 (
    echo [WinCare Manager] Gerekli paketler eksik veya bozuk. Ayrinti:
    ".venv\Scripts\python.exe" -c "import PySide6.QtWidgets, psutil"
    echo.
    echo Cozum: powershell -ExecutionPolicy Bypass -File scripts\setup_windows.ps1
    pause
    exit /b 1
)

start "WinCare Manager" ".venv\Scripts\pythonw.exe" main.py
exit /b 0
