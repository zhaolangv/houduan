# PowerShell 测试脚本
# 使用方法: .\test_api_simple.ps1

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "简单API测试脚本" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

$url = "http://localhost:5000/api/test"

Write-Host "测试本地服务: $url" -ForegroundColor Yellow
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri $url -Method GET -UseBasicParsing
    
    Write-Host "✅ 请求成功！" -ForegroundColor Green
    Write-Host "状态码: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    Write-Host "响应内容:" -ForegroundColor Cyan
    Write-Host $response.Content
    Write-Host ""
    
    # 尝试解析 JSON
    try {
        $json = $response.Content | ConvertFrom-Json
        Write-Host "解析后的JSON:" -ForegroundColor Cyan
        $json | ConvertTo-Json -Depth 10
    } catch {
        Write-Host "⚠️ 无法解析为JSON" -ForegroundColor Yellow
    }
    
} catch {
    Write-Host "❌ 请求失败！" -ForegroundColor Red
    Write-Host "错误信息: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    Write-Host "可能的原因:" -ForegroundColor Yellow
    Write-Host "1. Flask 服务未启动（运行: python app.py）" -ForegroundColor Yellow
    Write-Host "2. 端口 5000 被占用" -ForegroundColor Yellow
    Write-Host "3. 防火墙阻止连接" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "按任意键退出..." -ForegroundColor Gray
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

