@echo off
echo ========================================
echo 启动Java后端服务
echo ========================================
cd backend
call mvn spring-boot:run
pause

