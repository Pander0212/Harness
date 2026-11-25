@echo off
REM Startet den Harness unter Windows. Legt beim ersten Start ein venv an.
cd /d "%~dp0"
if not exist .venv (
  py -3 -m venv .venv || python -m venv .venv
  .venv\Scripts\python -m pip install --upgrade pip
  .venv\Scripts\pip install -r requirements.txt
)
.venv\Scripts\python main.py %*
pause
