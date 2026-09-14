@echo off
setlocal
cd /d "%~dp0"

where uv >nul 2>nul
if errorlevel 1 (
  echo ERROR: uv is not installed or is not available in PATH.
  echo Install uv, then run this file again.
  pause
  exit /b 1
)

echo Preparing Calyx...
uv sync
if errorlevel 1 (
  echo.
  echo ERROR: The Python environment could not be prepared.
  pause
  exit /b 1
)

echo.
echo Local store: http://127.0.0.1:8080
echo Public store: http://YOUR-VPS-IP:8080
echo Press Ctrl+C in this window to stop the store.
start "" /min powershell -NoProfile -WindowStyle Hidden -Command "Start-Sleep -Seconds 2; Start-Process 'http://127.0.0.1:8080'"
uv run uvicorn app.main:app --host 0.0.0.0 --port 8080

endlocal
