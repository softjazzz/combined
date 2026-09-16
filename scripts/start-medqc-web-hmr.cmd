@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0.."
set "APP_DIR=%ROOT_DIR%\apps\medqc-web"
set "NPM_CMD=C:\Program Files\nodejs\npm.cmd"

if not exist "%APP_DIR%\package.json" (
  echo [ERROR] medqc-web package.json not found:
  echo         %APP_DIR%\package.json
  pause
  exit /b 1
)

if not exist "%NPM_CMD%" (
  set "NPM_CMD=npm.cmd"
)

echo [INFO] App directory: %APP_DIR%
echo [INFO] Checking port 3000 ...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":3000 .*LISTENING"') do (
  echo [INFO] Killing stale process on 3000: PID %%P
  taskkill /PID %%P /F >nul 2>nul
)

pushd "%APP_DIR%" >nul

if exist "node_modules\.vite" (
  echo [INFO] Clearing Vite cache: node_modules\.vite
  rmdir /s /q "node_modules\.vite" >nul 2>nul
)

echo [INFO] Starting HMR server at http://localhost:3000/workstation-v5
echo.
"%NPM_CMD%" run dev -- --host 127.0.0.1 --port 3000 --strictPort --force

set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
echo.
echo [INFO] Dev server exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%
