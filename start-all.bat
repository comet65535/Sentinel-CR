@echo off
chcp 65001 >nul
setlocal EnableExtensions EnableDelayedExpansion
cd /d "%~dp0"

:: 1. Define paths
set "ROOT=%~dp0"
set "FRONTEND_DIR=%ROOT%frontend-ui"
set "BACKEND_DIR=%ROOT%backend-java"
set "AI_DIR=%ROOT%ai-engine-python"

:: 2. Define ports
set "FRONTEND_PORT=5173"
set "BACKEND_PORT=8080"
set "AI_PORT=8010"
set "AI_BASE_URL=http://localhost:%AI_PORT%"

echo ========================================
echo   Sentinel-CR Auto-Start Script
echo ========================================
echo.

:: 3. Check directory existence
if not exist "%FRONTEND_DIR%" goto err_frontend
if not exist "%BACKEND_DIR%" goto err_backend
if not exist "%AI_DIR%" goto err_ai
if not exist "%AI_DIR%\main.py" goto err_ai_main

:: ==========================================
:: Stage 1: Start AI Engine (Python)
:: ==========================================
echo [1/3] Starting AI Engine on port %AI_PORT% ...
call :get_port_pid %AI_PORT%
if defined PORT_PID (
    echo [INFO] Port %AI_PORT% is already in use by PID !PORT_PID!, skipping AI Engine startup.
) else (
    set "PY_CMD=python"
    if exist "%AI_DIR%\.venv\Scripts\python.exe" set "PY_CMD=.venv\Scripts\python.exe"
    if exist "%AI_DIR%\venv\Scripts\python.exe" set "PY_CMD=venv\Scripts\python.exe"

    start "Sentinel-CR AI Engine" /D "%AI_DIR%" cmd /k ""!PY_CMD!" -m uvicorn main:app --host 0.0.0.0 --port %AI_PORT%"
)

timeout /t 2 /nobreak >nul

:: ==========================================
:: Stage 2: Start Spring Boot Backend (FORCE python mode)
:: ==========================================
echo [2/3] Starting Spring Boot Backend on port %BACKEND_PORT% ...
call :get_port_pid %BACKEND_PORT%
if defined PORT_PID (
    echo [WARN] Port %BACKEND_PORT% is already in use by PID !PORT_PID!. Stopping old process to enforce python mode...
    taskkill /PID !PORT_PID! /F >nul 2>nul
    timeout /t 1 /nobreak >nul
)

set "SERVER_PORT=%BACKEND_PORT%"
set "SENTINEL_AI_MODE=python"
set "SENTINEL_AI_PYTHON_BASE_URL=%AI_BASE_URL%"
start "Sentinel-CR Backend" /D "%BACKEND_DIR%" cmd /k "if exist mvnw.cmd (call mvnw.cmd spring-boot:run) else (call mvn spring-boot:run)"

timeout /t 2 /nobreak >nul

:: ==========================================
:: Stage 3: Start Vue Frontend
:: ==========================================
echo [3/3] Starting Vue Frontend on port %FRONTEND_PORT% ...
call :get_port_pid %FRONTEND_PORT%
if defined PORT_PID (
    echo [INFO] Port %FRONTEND_PORT% is already in use by PID !PORT_PID!, skipping Frontend startup.
) else (
    start "Sentinel-CR Frontend" /D "%FRONTEND_DIR%" cmd /k "npm run dev -- --port %FRONTEND_PORT%"
)

echo.
echo [SUCCESS] Startup commands issued.
echo Frontend: http://localhost:%FRONTEND_PORT%
echo Backend : http://localhost:%BACKEND_PORT%
echo AI      : http://localhost:%AI_PORT%
echo.
echo Press any key to exit this launcher window...
pause >nul
goto :eof

:: ==========================================
:: Helpers
:: ==========================================
:get_port_pid
set "PORT_PID="
for /f "tokens=5" %%P in ('netstat -ano ^| findstr /R /C:":%~1 .*LISTENING"') do (
    set "PORT_PID=%%P"
    goto :get_port_pid_done
)
:get_port_pid_done
exit /b 0

:: ==========================================
:: Error Handlers
:: ==========================================
:err_frontend
echo [ERROR] Startup failed! Cannot find frontend directory: %FRONTEND_DIR%
pause
goto :eof

:err_backend
echo [ERROR] Startup failed! Cannot find backend directory: %BACKEND_DIR%
pause
goto :eof

:err_ai
echo [ERROR] Startup failed! Cannot find AI engine directory: %AI_DIR%
pause
goto :eof

:err_ai_main
echo [ERROR] Startup failed! Cannot find AI entrypoint: %AI_DIR%\main.py
pause
goto :eof
