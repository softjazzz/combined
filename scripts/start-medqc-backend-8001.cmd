@echo off
setlocal EnableExtensions EnableDelayedExpansion

set "ROOT_DIR=%~dp0.."
set "BACKEND_DIR=%ROOT_DIR%\apps\medqc-web\backend"
set "PORT=8001"

if not exist "%BACKEND_DIR%\app\main.py" (
  echo [ERROR] backend app\main.py not found:
  echo         %BACKEND_DIR%\app\main.py
  pause
  exit /b 1
)

echo [INFO] Backend directory: %BACKEND_DIR%
echo [INFO] Checking port %PORT% ...

for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%PORT% .*LISTENING"') do (
  echo [INFO] Killing stale process on %PORT%: PID %%P
  taskkill /PID %%P /F >nul 2>nul
)

set "PY_CMD="
for /f "tokens=2" %%I in ('py -0p 2^>nul ^| findstr /R "3\.[0-9]-64"') do (
  set "PY_CMD=%%I"
  goto :py_found
)

:py_found
if defined PY_CMD (
  echo [INFO] Using python: !PY_CMD!
) else (
  for /f "delims=" %%I in ('where python 2^>nul') do (
    set "PY_CMD=%%I"
    goto :where_found
  )
)

:where_found
if not defined PY_CMD (
  echo [ERROR] No python runtime found.
  echo [HINT] Install Python 3.10+ or ensure py/python is in PATH.
  pause
  exit /b 2
)

pushd "%BACKEND_DIR%" >nul
set "PYTHONIOENCODING=utf-8"
if "%JWT_SECRET%"=="" set "JWT_SECRET=dev-secret"

echo [INFO] Starting backend at http://127.0.0.1:%PORT%
echo.
"!PY_CMD!" -m uvicorn app.main:app --host 0.0.0.0 --port %PORT% --timeout-keep-alive 5

set "EXIT_CODE=%ERRORLEVEL%"
popd >nul
echo.
echo [INFO] Backend exited with code %EXIT_CODE%.
pause
exit /b %EXIT_CODE%

