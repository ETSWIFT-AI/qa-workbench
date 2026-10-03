@echo off
cd /d "%~dp0"
if not exist .venv\Scripts\python.exe py -m venv .venv
if errorlevel 1 exit /b 1
set /p QA_SCAN_URL=Enter website URL: 
.venv\Scripts\python.exe thorough.py "%QA_SCAN_URL%" --setup
pause
