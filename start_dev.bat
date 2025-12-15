@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
set "SCRIPT_DIR=%~dp0"

echo ============================================================
echo Cultural Resource System - Dev start script
echo ============================================================
echo.

REM Check Python
python --version >nul 2>&1
if errorlevel 1 (
    echo [����] δ��⵽Python�����Ȱ�װPython
    pause
    exit /b 1
)

REM Check Node.js
node --version >nul 2>&1
if errorlevel 1 (
    echo [����] δ��⵽Node.js�����Ȱ�װNode.js
    pause
    exit /b 1
)

REM Check port 5173
echo [CHECK] checking port 5173...
netstat -ano | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [WARN] port 5173 is in use, frontend may fail to start
    echo [TIP ] if an old frontend is running, you can ignore this
)

echo [OK  ] port check done
echo.

REM Enter frontend directory
cd /d "%SCRIPT_DIR%FrontEnd"
if errorlevel 1 (
    echo [����] �޷�����FrontEndĿ¼
    pause
    exit /b 1
)

REM Install deps if missing
if not exist node_modules (
    echo [INSTALL] installing frontend deps...
    call npm install
    if errorlevel 1 (
        echo [ERROR] frontend deps install failed
        pause
        exit /b 1
    )
)

REM Ensure concurrently exists
call npm list concurrently >nul 2>&1
if errorlevel 1 (
    echo [INSTALL] installing concurrently...
    call npm install --save-dev concurrently
    if errorlevel 1 (
        echo [ERROR] concurrently install failed
        pause
        exit /b 1
    )
)

echo.
echo [START] starting dev servers...
echo ============================================================
echo visit: http://localhost:5173
echo ============================================================
echo.
echo press Ctrl+C to stop
echo.

REM Start both frontend and backend
call npm run dev:full

REM Fallback manual start
if errorlevel 1 (
    echo.
    echo [INFO] concurrently failed, please start manually:
    echo 1. In project root: python AIGC\aigc_api_server.py
    echo 2. In FrontEnd   : npm run dev
    pause
)

pause
