param([string]$Url = "https://a5413eed8eb6.ngrok-free.app")

$Url = $Url.TrimEnd('/')
$headers = @{'ngrok-skip-browser-warning'='true'}

Write-Host "Testing: $Url/api/test" -ForegroundColor Yellow

try {
    $r = Invoke-WebRequest -Uri "$Url/api/test" -Headers $headers -UseBasicParsing
    Write-Host "SUCCESS! Status: $($r.StatusCode)" -ForegroundColor Green
    $r.Content | ConvertFrom-Json | ConvertTo-Json
} catch {
    Write-Host "FAILED: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "Try opening $Url in browser and click 'Visit Site' first" -ForegroundColor Yellow
}

