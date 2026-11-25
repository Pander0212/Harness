@echo off
REM Startet den Agent-Harness unter Windows (Doppelklick genuegt).
setlocal
cd /d "%~dp0"
chcp 65001 >nul
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1

if exist ".venv\Scripts\python.exe" goto run

REM ---- Python suchen (py-Launcher bevorzugt, Store-Platzhalter ignorieren) ----
set "PY="
py -3 --version >nul 2>nul && set "PY=py -3"
if not defined PY python --version >nul 2>nul && set "PY=python"
if not defined PY goto nopython

echo Gefunden:
%PY% --version
%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3, 9) else 1)"
if errorlevel 1 goto oldpython

echo.
echo Erster Start: lege virtuelle Umgebung .venv an und installiere Pakete ...
%PY% -m venv .venv
if errorlevel 1 goto venvfail
".venv\Scripts\python.exe" -m pip install --upgrade pip
".venv\Scripts\python.exe" -m pip install -r requirements.txt
if errorlevel 1 goto pipfail

:run
where git >nul 2>nul
if errorlevel 1 if not exist "%ProgramFiles%\Git\bin\bash.exe" (
  echo.
  echo HINWEIS: Git for Windows wurde nicht gefunden. Die Agenten brauchen Git Bash.
  echo Download: https://git-scm.com/download/win
  echo.
)
echo Starte Harness ... Die Web-Oberflaeche oeffnet sich im Browser: http://127.0.0.1:8765/
echo Zum Beenden dieses Fenster schliessen oder Strg+C druecken.
echo.
".venv\Scripts\python.exe" main.py %*
echo.
echo Harness wurde beendet.
pause
exit /b 0

:nopython
echo.
echo ============================================================
echo  Python 3 ist nicht installiert.
echo.
echo  1. Auf der gleich geoeffneten Seite "Download Python 3.x" klicken.
echo  2. Im Installer UNBEDINGT unten den Haken setzen bei
echo        "Add python.exe to PATH"
echo     und dann "Install Now" waehlen.
echo  3. Dieses Fenster schliessen und start.bat erneut doppelklicken.
echo ============================================================
start "" "https://www.python.org/downloads/windows/"
pause
exit /b 1

:oldpython
echo Python ist zu alt. Bitte Python 3.9 oder neuer installieren: https://www.python.org/downloads/windows/
pause
exit /b 1

:venvfail
echo Die virtuelle Umgebung konnte nicht angelegt werden.
pause
exit /b 1

:pipfail
echo Paketinstallation fehlgeschlagen - Internetverbindung pruefen.
echo Danach den Ordner .venv loeschen und start.bat erneut starten.
pause
exit /b 1
