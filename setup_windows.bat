@echo off
cd /d "%~dp0"
py -m venv .venv
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failed
echo Setup complete. Double-click start_gui.bat to open Website QA.
pause
exit /b 0
:failed
echo Setup failed. Read the error above. Python must be installed.
pause
exit /b 1
