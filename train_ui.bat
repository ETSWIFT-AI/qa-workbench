@echo off
setlocal
cd /d "%~dp0"
if exist ".venv\Scripts\python.exe" goto install
py -3.12 -m venv .venv
if not errorlevel 1 goto install
py -m venv .venv
if errorlevel 1 goto failed
:install
.venv\Scripts\python.exe -m pip install torch --index-url https://download.pytorch.org/whl/cpu
if errorlevel 1 goto failed
.venv\Scripts\python.exe -m pip install -r requirements-ui.txt
if errorlevel 1 goto failed
.venv\Scripts\python.exe train_ui.py
if errorlevel 1 goto failed
echo.
echo Training finished. See models\calista_ui\ui-model.json for evaluation.
echo Run setup_windows.bat once before scan_with_ui.bat if browser setup is missing.
pause
exit /b 0
:failed
echo Setup or training failed. Read the error above. Python 3.12 is recommended.
pause
exit /b 1
