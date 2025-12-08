@echo off
chcp 65001 >nul
echo ========================================
echo 简单API测试脚本
echo ========================================
echo.

echo 测试本地服务: http://localhost:5000/api/test
echo.

REM 使用 PowerShell 的 Invoke-WebRequest
powershell -Command "try { $response = Invoke-WebRequest -Uri 'http://localhost:5000/api/test' -Method GET -UseBasicParsing; Write-Host '状态码:' $response.StatusCode; Write-Host '响应内容:'; $response.Content } catch { Write-Host '错误:' $_.Exception.Message }"

echo.
echo ========================================
pause

