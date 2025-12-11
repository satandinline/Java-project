@echo off
REM 设置UTF-8编码，避免中文乱码
chcp 65001 >nul
setlocal

echo 正在启动开发服务器...
echo.

REM 检查Python是否安装
python --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到Python，请先安装Python
    pause
    exit /b 1
)

REM 检查Node.js是否安装
node --version >nul 2>&1
if errorlevel 1 (
    echo 错误：未检测到Node.js，请先安装Node.js
    pause
    exit /b 1
)

REM 启动搜索服务
echo 正在启动全文检索服务 (Port: 5050)...
REM "start" 命令会打开一个新的 cmd 窗口运行 python
REM "Search Service" 是窗口标题
REM cmd /k 保证窗口不会自动关闭，方便你看报错
start "Search Service (5050)" cmd /k "python search_service.py"

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
echo 启动前端和后端服务器...
echo 前端地址: http://localhost:5173
echo 后端地址: http://localhost:5000
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

