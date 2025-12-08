#!/bin/bash

echo "正在启动开发服务器..."
echo

# 检查Python是否安装
if ! command -v python3 &> /dev/null && ! command -v python &> /dev/null; then
    echo "错误：未检测到Python，请先安装Python"
    exit 1
fi

# 检查Node.js是否安装
if ! command -v node &> /dev/null; then
    echo "错误：未检测到Node.js，请先安装Node.js"
    exit 1
fi

# 进入前端目录
cd FrontEnd

# 检查是否已安装依赖
if [ ! -d "node_modules" ]; then
    echo "正在安装前端依赖..."
    npm install
fi

# 检查是否安装了concurrently
if ! npm list concurrently &> /dev/null; then
    echo "正在安装concurrently..."
    npm install --save-dev concurrently
fi

echo
echo "启动前端和后端服务器..."
echo "前端地址: http://localhost:5173"
echo "后端地址: http://localhost:5000"
echo
echo "按 Ctrl+C 停止服务器"
echo

# 使用concurrently同时启动前端和后端
npm run dev:full

