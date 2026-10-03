@echo off
cd /d "%~dp0"
call train_ui.bat
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m playwright install chromium
if errorlevel 1 goto failed
echo Ready. Double-click scan_with_ui.bat to enter your website URL.
pause
exit /b 0
:failed
echo Browser setup failed. Training results remain saved. Read the error above.
pause
exit /b 1
