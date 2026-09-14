@echo off
setlocal
cd /d "%~dp0"

net session >nul 2>&1
if errorlevel 1 (
  echo Requesting Administrator access...
  powershell -NoProfile -ExecutionPolicy Bypass -Command "Start-Process -FilePath '%~f0' -ArgumentList '%~1' -Verb RunAs"
  exit /b
)

set "DNS_HOST=%~1"
if not defined DNS_HOST set "DNS_HOST=example.duckdns.org"
if not defined CALYX_EXPECTED_IP set "CALYX_EXPECTED_IP=203.0.113.10"

echo.
echo Calyx DNS and HTTPS configuration
echo Hostname: %DNS_HOST%
echo Expected IP: %CALYX_EXPECTED_IP%
echo.

powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0..\tools\Configure-DnsHttps.ps1" -DnsHostname "%DNS_HOST%" -ExpectedIp "%CALYX_EXPECTED_IP%"
set "RESULT=%ERRORLEVEL%"

echo.
if not "%RESULT%"=="0" (
  echo Configuration did not finish. Read the message above, correct it, then run this BAT again.
) else (
  echo Configuration completed successfully.
)
echo.
pause
exit /b %RESULT%
