@echo off
REM 设置UTF-8编码，避免中文乱码
chcp 65001 >nul
setlocal

echo ============================================================
echo 公共文化资源管理系统 - 开发服务器启动脚本
echo ============================================================
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查Node.js是否安装
node --version >nul 2>&1
if errorlevel 1 (
    echo [错误] 未检测到Node.js，请先安装Node.js
    pause
    exit /b 1
)

REM 检查5173端口是否被占用（前端端口）
echo [检查] 正在检查端口5173是否被占用...
netstat -ano | findstr ":5173" >nul 2>&1
if not errorlevel 1 (
    echo [警告] 端口5173已被占用，前端服务可能无法正常启动
    echo [提示] 如果这是之前启动的前端服务，可以忽略此警告
)

echo [成功] 端口检查完成
echo.

REM 进入前端目录
cd FrontEnd

REM 检查是否已安装依赖
if not exist "node_modules" (
    echo 正在安装前端依赖...
    call npm install
)

REM 检查是否安装了concurrently
call npm list concurrently >nul 2>&1
if errorlevel 1 (
    echo 正在安装concurrently...
    call npm install --save-dev concurrently
)

echo.
echo 启动开发服务器...
echo ============================================================
echo 访问地址: http://localhost:5173
echo ============================================================
echo.
echo 按 Ctrl+C 停止服务器
echo.

REM 使用concurrently同时启动前端和后端
call npm run dev:full

REM 如果concurrently失败，尝试分别启动
if errorlevel 1 (
    echo.
    echo 使用concurrently启动失败，尝试分别启动...
    echo 请手动打开两个终端窗口：
    echo 1. 在项目根目录运行: python AIGC/aigc_api_server.py
    echo 2. 在FrontEnd目录运行: npm run dev
    pause
)

pause

