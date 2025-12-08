@echo off
chcp 65001 >nul
echo ========================================
echo 内网穿透可用性测试脚本
echo ========================================
echo.

REM 检查本地服务是否运行
echo [步骤1] 检查本地服务是否运行...
echo.

REM 使用 PowerShell 测试（更可靠）
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/test' -Method GET -UseBasicParsing -TimeoutSec 3; exit 0 } catch { exit 1 }" >nul 2>&1
if %errorlevel% == 0 (
    echo ✅ 本地服务运行正常 (http://localhost:5000)
    echo.
) else (
    echo ❌ 本地服务未运行或无法访问
    echo.
    echo 请先启动 Flask 服务：
    echo   python app.py
    echo.
    echo 提示：确保在项目目录下运行 python app.py
    echo.
    pause
    exit /b 1
)

REM 测试本地API（使用测试接口，更快）
echo [步骤2] 测试本地API接口...
echo.
echo 发送请求到: http://localhost:5000/api/test
echo.

REM 使用 PowerShell 获取并显示响应
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/test' -Method GET -UseBasicParsing; Write-Host $response.Content } catch { Write-Host '错误:' $_.Exception.Message; exit 1 }"

if %errorlevel% == 0 (
    echo.
    echo ✅ 本地API测试成功
    echo.
) else (
    echo.
    echo ❌ 本地API测试失败
    echo.
    pause
    exit /b 1
)

echo ========================================
echo 本地服务测试完成
echo ========================================
echo.
echo 接下来需要：
echo 1. 启动内网穿透工具（在另一个终端）
echo    运行: .\start_tunnel_localtunnel.bat
echo    或: npx localtunnel --port 5000
echo.
echo 2. 复制显示的公网URL（如: https://xxxx.loca.lt）
echo.
echo 3. 运行测试脚本验证公网访问：
echo    .\test_tunnel_public.bat <公网URL>
echo.
echo 或者手动测试：
echo    curl https://xxxx.loca.lt/api/stats
echo.
pause

