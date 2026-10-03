@echo off
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
 echo Run train_ui.bat first.
 pause
 exit /b 1
)
.venv\Scripts\python.exe scan_with_ui.py
pause
