@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m pip install -r requirements-company.txt
if errorlevel 1 exit /b 1
.venv\Scripts\python.exe -m playwright install chromium firefox webkit
if errorlevel 1 exit /b 1
echo Setup complete. See COMPANY_README.md for demo commands.
pause
