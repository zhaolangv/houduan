# ngrok Test Script
# Usage: .\test_ngrok.ps1 <ngrok-url>
# Example: .\test_ngrok.ps1 https://a5413eed8eb6.ngrok-free.app

param(
    [Parameter(Mandatory=$true)]
    [string]$NgrokUrl
)

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "ngrok Public Access Test" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""

# Remove trailing slash
$NgrokUrl = $NgrokUrl.TrimEnd('/')

Write-Host "ngrok URL: $NgrokUrl" -ForegroundColor Yellow
Write-Host ""

# ngrok free version requires header to skip warning page
$headers = @{
    'ngrok-skip-browser-warning' = 'true'
}

Write-Host "[Test 1] Test API: $NgrokUrl/api/test" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "$NgrokUrl/api/test" -Method GET -Headers $headers -UseBasicParsing
    
    Write-Host "SUCCESS! Request successful" -ForegroundColor Green
    Write-Host "Status Code: $($response.StatusCode)" -ForegroundColor Green
    Write-Host ""
    Write-Host "Response Content:" -ForegroundColor Cyan
    
    # Parse and format JSON
    $json = $response.Content | ConvertFrom-Json
    $json | ConvertTo-Json -Depth 10
    
    Write-Host ""
    
} catch {
    Write-Host "FAILED! Request failed" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host ""
    
    if ($_.Exception.Response) {
        $statusCode = $_.Exception.Response.StatusCode.value__
        Write-Host "HTTP Status Code: $statusCode" -ForegroundColor Yellow
    }
    
    Write-Host ""
    Write-Host "Possible reasons:" -ForegroundColor Yellow
    Write-Host "1. ngrok tunnel not started or disconnected" -ForegroundColor Yellow
    Write-Host "2. Local Flask service not running" -ForegroundColor Yellow
    Write-Host "3. First visit requires clicking 'Visit Site' button in browser" -ForegroundColor Yellow
    Write-Host ""
    Write-Host "Solutions:" -ForegroundColor Cyan
    Write-Host "1. Open in browser: $NgrokUrl" -ForegroundColor Cyan
    Write-Host "2. Click 'Visit Site' button (first time only)" -ForegroundColor Cyan
    Write-Host "3. Run this script again" -ForegroundColor Cyan
    Write-Host ""
    exit 1
}

Write-Host "[Test 2] Health Check API: $NgrokUrl/api/health" -ForegroundColor Cyan
Write-Host ""

try {
    $response = Invoke-WebRequest -Uri "$NgrokUrl/api/health" -Method GET -Headers $headers -UseBasicParsing
    
    Write-Host "SUCCESS! Health check passed" -ForegroundColor Green
    Write-Host ""
    
    $json = $response.Content | ConvertFrom-Json
    $json | ConvertTo-Json -Depth 10
    
} catch {
    Write-Host "WARNING: Health check failed (does not affect basic functionality)" -ForegroundColor Yellow
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "Test Complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Tip: If tests passed, intranet penetration is working." -ForegroundColor Gray
Write-Host "You can use this URL to access your service from the internet." -ForegroundColor Gray
Write-Host ""
Write-Host "API Endpoints:" -ForegroundColor Cyan
Write-Host "  - Test: $NgrokUrl/api/test" -ForegroundColor Gray
Write-Host "  - Analyze: $NgrokUrl/api/questions/analyze" -ForegroundColor Gray
Write-Host "  - Detail: $NgrokUrl/api/questions/<id>/detail" -ForegroundColor Gray
Write-Host "  - Stats: $NgrokUrl/api/stats" -ForegroundColor Gray
Write-Host "  - Upload: $NgrokUrl/api/upload" -ForegroundColor Gray
Write-Host ""
