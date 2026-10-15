@echo off
rem Umay GPT Next: backend (FastAPI) and frontend (Next.js) in two windows, then opens the browser.
rem Change BACKEND_PORT if needed; the frontend proxy follows it through BACKEND_URL.
setlocal
cd /d "%~dp0"
set BACKEND_PORT=8001

if not exist "backend\.venv\Scripts\python.exe" (
  echo [!] backend\.venv not found. Create it:  py -3.13 -m venv backend\.venv ^&^& backend\.venv\Scripts\pip install -r backend\requirements.txt
  pause
  exit /b 1
)
if not exist "frontend\node_modules" (
  echo [i] Installing frontend dependencies...
  pushd frontend && call npm.cmd install && popd
)

start "Umay backend :%BACKEND_PORT%" cmd /k "cd /d "%~dp0backend" && set PYTHONIOENCODING=utf-8&& .venv\Scripts\python.exe -m uvicorn app.main:app --port %BACKEND_PORT%"
rem 127.0.0.1 instead of localhost: on Windows localhost tries IPv6 first and adds latency to every proxied request
start "Umay frontend :3000" cmd /k "cd /d "%~dp0frontend" && set BACKEND_URL=http://127.0.0.1:%BACKEND_PORT%&& npm.cmd run dev"

echo Waiting for the frontend on http://localhost:3000 ...
:wait
timeout /t 2 /nobreak >nul
powershell -NoProfile -Command "try { (Invoke-WebRequest -UseBasicParsing -TimeoutSec 60 http://localhost:3000/).StatusCode } catch { exit 1 }" >nul 2>&1
if errorlevel 1 goto wait
start "" http://localhost:3000
endlocal
