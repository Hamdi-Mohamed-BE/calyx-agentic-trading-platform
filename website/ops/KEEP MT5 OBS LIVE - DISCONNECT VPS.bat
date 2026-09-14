@echo off
setlocal EnableExtensions
title Calyx - Keep MT5 and OBS Live

rem This script must run on the Windows VPS from the active RDP session.
rem It transfers that session to the VPS console instead of logging it off.

fltmc >nul 2>&1
if errorlevel 1 (
    echo Requesting Administrator access...
    powershell.exe -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -Verb RunAs"
    exit /b
)

echo.
echo Calyx - Keep MT5 and OBS Live
echo ==============================
echo.

tasklist /FI "IMAGENAME eq obs64.exe" 2>nul | find /I "obs64.exe" >nul
if errorlevel 1 (
    echo WARNING: OBS Studio does not appear to be running.
) else (
    echo OK: OBS Studio is running.
)

tasklist /FI "IMAGENAME eq terminal64.exe" 2>nul | find /I "terminal64.exe" >nul
if errorlevel 1 (
    echo WARNING: MetaTrader 5 does not appear to be running.
) else (
    echo OK: MetaTrader 5 is running.
)

for /f "usebackq delims=" %%S in (`powershell.exe -NoProfile -Command "(Get-Process -Id $PID).SessionId"`) do set "CALYX_SESSION_ID=%%S"

if not defined CALYX_SESSION_ID (
    echo.
    echo ERROR: The active Windows session could not be detected.
    echo Nothing was disconnected.
    pause
    exit /b 1
)

echo.
echo The RDP window will disconnect in 8 seconds.
echo MT5 and OBS will remain running in Windows session %CALYX_SESSION_ID%.
echo Do not sign out or lock the VPS after running this file.
echo Press Ctrl+C now to cancel.
timeout /t 8 /nobreak >nul

%SystemRoot%\System32\tscon.exe %CALYX_SESSION_ID% /dest:console
if errorlevel 1 (
    echo.
    echo ERROR: Windows could not transfer the RDP session to the console.
    echo If the stream still turns black, the VPS needs a persistent virtual display.
    pause
    exit /b 1
)

endlocal
