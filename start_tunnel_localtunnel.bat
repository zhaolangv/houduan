@echo off
chcp 65001 >nul
echo ========================================
echo 使用 localtunnel 启动内网穿透
echo ========================================
echo.
echo 启动隧道到 http://localhost:5000
echo 按 Ctrl+C 停止
echo.
echo 提示：如果提示找不到命令，请确保：
echo   1. 已安装 Node.js
echo   2. 已运行: npm install -g localtunnel
echo   3. 或者直接使用: npx localtunnel --port 5000
echo.
echo ========================================
echo.

REM 检查 Node.js 是否安装
where node >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未找到 Node.js
    echo 请先安装 Node.js: https://nodejs.org/
    pause
    exit /b 1
)

REM 检查 npx 是否可用
where npx >nul 2>&1
if %errorlevel% neq 0 (
    echo 错误：未找到 npx
    echo 请确保 Node.js 已正确安装
    pause
    exit /b 1
)

echo 使用 npx 启动 localtunnel...
echo.
echo 注意：如果看到 "your url is: https://xxx.loca.lt"，说明成功！
echo 按 Ctrl+C 停止服务
echo.
echo ========================================
echo.

REM 尝试使用 npx（推荐，不需要配置 PATH）
npx localtunnel --port 5000

if %errorlevel% neq 0 (
    echo.
    echo ========================================
    echo 使用 npx 失败，尝试直接使用 lt 命令...
    echo ========================================
    echo.
    lt --port 5000
)

