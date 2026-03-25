@echo off
setlocal EnableExtensions

cd /d "%~dp0"

set "ROOT=%~dp0"
if "%ROOT:~-1%"=="\" set "ROOT=%ROOT:~0,-1%"

set "HIVE_PORT=8765"
set "PYTHONUTF8=1"
set "PYTHONIOENCODING=utf-8"
set "PYTHONPATH=%ROOT%\src"
set "HIVE_DB_PATH=%ROOT%\data\hive.db"

where codex >nul 2>nul
if errorlevel 1 (
    set "HIVE_ADAPTER=mock"
    echo [WARN] codex not found, fallback to mock adapter.
) else (
    set "HIVE_ADAPTER=codex"
    echo [INFO] codex found, using codex adapter.
)

set "PY_CMD="
for %%V in (3.13 3.12 3.11 3.10) do (
    py -%%V -c "import sys" >nul 2>nul
    if not defined PY_CMD set "PY_CMD=py -%%V"
)

if not defined PY_CMD (
    echo [ERROR] Python 3.10+ was not found.
    pause
    exit /b 1
)

%PY_CMD% -c "import importlib.util as u; mods=['pydantic','loguru','yaml','fastapi','uvicorn','sqlalchemy','aiosqlite','websockets']; missing=[m for m in mods if not u.find_spec(m)]; raise SystemExit(0 if not missing else 1)" >nul 2>nul
if errorlevel 1 (
    echo [ERROR] Missing runtime deps in selected Python.
    echo [ERROR] Run: %PY_CMD% -m pip install -e .
    pause
    exit /b 1
)

if not exist "%ROOT%\data" mkdir "%ROOT%\data"

echo [INFO] Root: %ROOT%
echo [INFO] Health: http://127.0.0.1:%HIVE_PORT%/health
echo [INFO] Dashboard: http://127.0.0.1:%HIVE_PORT%/dashboard
echo [INFO] Run: %PY_CMD% start.py
echo.

start "" "http://127.0.0.1:%HIVE_PORT%/dashboard"
%PY_CMD% start.py

set "EXIT_CODE=%ERRORLEVEL%"
if not "%EXIT_CODE%"=="0" (
    echo.
    echo [ERROR] Service exited with code %EXIT_CODE%.
    pause
)
exit /b %EXIT_CODE%
