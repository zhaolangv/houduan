@echo off
chcp 65001 >nul
echo ========================================
echo 内网穿透启动脚本
echo ========================================
echo.

REM 检查 cpolar 是否存在
if exist "cpolar.exe" (
    echo 使用 cpolar...
    echo.
    echo 启动隧道到 http://localhost:5000
    echo 按 Ctrl+C 停止
    echo.
    cpolar.exe http 5000
    goto :end
)

REM 检查 ngrok 是否存在
if exist "ngrok.exe" (
    echo 使用 ngrok...
    echo.
    echo 启动隧道到 http://localhost:5000
    echo 按 Ctrl+C 停止
    echo.
    ngrok.exe http 5000
    goto :end
)

REM 检查 localtunnel (使用 npx)
where npx >nul 2>&1
if %errorlevel% == 0 (
    echo 使用 localtunnel (npx)...
    echo.
    echo 启动隧道到 http://localhost:5000
    echo 按 Ctrl+C 停止
    echo.
    npx localtunnel --port 5000
    goto :end
)

REM 检查 localtunnel (直接命令)
where lt >nul 2>&1
if %errorlevel% == 0 (
    echo 使用 localtunnel...
    echo.
    echo 启动隧道到 http://localhost:5000
    echo 按 Ctrl+C 停止
    echo.
    lt --port 5000
    goto :end
)

REM 如果都没找到
echo 错误：未找到内网穿透工具
echo.
echo 请选择以下方案之一：
echo.
echo 【方案1】下载 cpolar（推荐，国内速度快）
echo   1. 访问: https://www.cpolar.com/download
echo   2. 下载 Windows 版本
echo   3. 将 cpolar.exe 放在项目根目录
echo.
echo 【方案2】下载 ngrok
echo   1. 访问: https://ngrok.com/download
echo   2. 下载 Windows 版本
echo   3. 将 ngrok.exe 放在项目根目录
echo.
echo 【方案3】使用 localtunnel（已安装，但可能需要配置 PATH）
echo   运行: npx localtunnel --port 5000
echo.
pause

:end

