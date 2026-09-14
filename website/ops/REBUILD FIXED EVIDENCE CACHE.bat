@echo off
setlocal
cd /d "%~dp0"
echo Rebuilding fixed native MT5 evidence for every recommended EA...
echo Periods: 6 months, 1 year, 3 years, 5 years
echo This is resumable and reuses unchanged completed source reports.
uv run python tools\precompute_evidence_cache.py --period all --safe
if errorlevel 1 (
  echo.
  echo One or more evidence runs failed. Completed caches were preserved; run this file again to retry.
  pause
  exit /b 1
)
echo.
echo Evidence cache completed successfully.
pause
