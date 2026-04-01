@echo off
setlocal ENABLEDELAYEDEXPANSION
cd /d %~dp0

echo ========================================
echo   Sentinel-CR one-click startup
echo ========================================
echo.

set ROOT=%~dp0
set FRONTEND_DIR=%ROOT%frontend-ui
set BACKEND_DIR=%ROOT%backend-java
set AI_DIR=%ROOT%ai-engine-python

if not exist "%FRONTEND_DIR%" (
  echo [ERROR] frontend-ui not found.
  goto :end
)

if not exist "%BACKEND_DIR%" (
  echo [ERROR] backend-java not found.
  goto :end
)

echo [1/3] Starting Spring Boot backend...
start "Sentinel-CR Backend" cmd /k "cd /d "%BACKEND_DIR%" && if exist mvnw.cmd (mvnw.cmd spring-boot:run) else mvn spring-boot:run"

timeout /t 2 /nobreak >nul

echo [2/3] Starting Vue frontend...
start "Sentinel-CR Frontend" cmd /k "cd /d "%FRONTEND_DIR%" && npm run dev"

timeout /t 2 /nobreak >nul

echo [3/3] Starting AI engine...
if exist "%AI_DIR%" (
  if exist "%AI_DIR%\main.py" (
    start "Sentinel-CR AI Engine" cmd /k "cd /d "%AI_DIR%" && if exist .venv\Scripts\python.exe (.venv\Scripts\python.exe main.py) else if exist venv\Scripts\python.exe (venv\Scripts\python.exe main.py) else python main.py"
  ) else (
    start "Sentinel-CR AI Engine" cmd /k "cd /d "%AI_DIR%" && echo AI engine folder exists, but main.py was not found. && echo Day0 can still run with backend mock AI."
  )
) else (
  echo [WARN] ai-engine-python not found. Skipping AI engine.
)

echo.
echo All startup commands have been launched in separate windows.
echo Frontend default: http://localhost:5173
echo Backend default:  http://localhost:8080
echo.

goto :eof

:end
echo.
echo Startup aborted.
pause
