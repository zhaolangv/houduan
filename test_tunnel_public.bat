@echo off
chcp 65001 >nul
echo ========================================
echo 测试内网穿透公网访问
echo ========================================
echo.

if "%1"=="" (
    echo 用法: test_tunnel_public.bat <公网URL>
    echo.
    echo 示例:
    echo   test_tunnel_public.bat https://xxxx.loca.lt
    echo.
    pause
    exit /b 1
)

set PUBLIC_URL=%1
echo 公网URL: %PUBLIC_URL%
echo.

REM 测试接口（推荐，快速且简单）
echo [测试1] 测试接口（推荐）...
echo 请求: %PUBLIC_URL%/api/test
echo.

REM 检测是否是 ngrok（需要特殊处理）
echo %PUBLIC_URL% | findstr /i "ngrok" >nul
if %errorlevel% == 0 (
    echo 检测到 ngrok，使用特殊请求头跳过警告页面...
    echo.
    REM 使用 PowerShell 发送带请求头的请求（跳过 ngrok 警告页面）
    powershell -Command "try { $headers = @{'ngrok-skip-browser-warning'='true'}; $response = Invoke-WebRequest -Uri '%PUBLIC_URL%/api/test' -Method GET -Headers $headers -UseBasicParsing; Write-Host '状态码:' $response.StatusCode; Write-Host ''; Write-Host '响应内容:'; $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10 } catch { Write-Host '错误:' $_.Exception.Message; Write-Host '响应:' $_.Exception.Response; exit 1 }"
) else (
    REM 非 ngrok，使用普通请求
    powershell -Command "try { $response = Invoke-WebRequest -Uri '%PUBLIC_URL%/api/test' -Method GET -UseBasicParsing; Write-Host '状态码:' $response.StatusCode; Write-Host ''; Write-Host '响应内容:'; $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10 } catch { Write-Host '错误:' $_.Exception.Message; exit 1 }"
)

if %errorlevel% == 0 (
    echo.
    echo ✅ 测试接口成功
    echo.
) else (
    echo.
    echo ❌ 测试接口失败
    echo.
    echo 可能的原因：
    echo 1. 内网穿透未正确启动
    echo 2. 公网URL不正确
    echo 3. 网络连接问题
    echo 4. ngrok 需要手动点击"Visit Site"按钮（首次访问）
    echo.
    echo 提示：如果是 ngrok，请在浏览器中先访问一次，点击"Visit Site"按钮
    echo.
    pause
    exit /b 1
)

echo.
echo [测试2] 健康检查接口...
echo 请求: %PUBLIC_URL%/api/health
echo.

REM 检测是否是 ngrok
echo %PUBLIC_URL% | findstr /i "ngrok" >nul
if %errorlevel% == 0 (
    powershell -Command "try { $headers = @{'ngrok-skip-browser-warning'='true'}; $response = Invoke-WebRequest -Uri '%PUBLIC_URL%/api/health' -Method GET -Headers $headers -UseBasicParsing; Write-Host $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10 } catch { Write-Host '错误:' $_.Exception.Message }"
) else (
    powershell -Command "try { $response = Invoke-WebRequest -Uri '%PUBLIC_URL%/api/health' -Method GET -UseBasicParsing; Write-Host $response.Content | ConvertFrom-Json | ConvertTo-Json -Depth 10 } catch { Write-Host '错误:' $_.Exception.Message }"
)

if %errorlevel% == 0 (
    echo.
    echo ✅ 健康检查接口成功
    echo.
) else (
    echo.
    echo ⚠️ 健康检查接口失败（不影响基本功能）
    echo.
)


echo ========================================
echo ✅ 内网穿透测试完成！
echo ========================================
echo.
echo 如果看到上述测试成功，说明内网穿透工作正常。
echo 你可以使用这个公网URL从外网访问你的服务。
echo.
pause

