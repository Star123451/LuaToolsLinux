@echo off
setlocal enableextensions

rem Resolve Steam install path from registry (HKCU\Software\Valve\Steam -> SteamPath)
for /f "tokens=2,*" %%A in ('reg query "HKCU\Software\Valve\Steam" /v SteamPath 2^>nul ^| find "SteamPath"') do set "STEAM_DIR=%%B"

echo Restarting Steam...
taskkill /IM steam.exe /F >nul 2>&1
timeout /t 2 /nobreak >nul

if defined STEAM_DIR (
  start "" "%STEAM_DIR%\Steam.exe" -clearbeta
) else (
  rem Fallback: try launching via path on PATH or shell association
  start "" steam.exe -clearbeta
)

exit

