# Camera Settings Helper
# Opens Windows Camera Settings for manual configuration

Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Camera Settings Configuration" -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Write-Host "Opening Camera Settings..." -ForegroundColor Yellow
Write-Host ""

# Open Camera Settings
Start-Process "ms-settings:camera"

Write-Host "INSTRUCTIONS:" -ForegroundColor Green
Write-Host ""
Write-Host "1. Click on your camera name (e.g., 'Ziad's S22 Ultra')" -ForegroundColor White
Write-Host ""
Write-Host "2. Click on 'Advanced camera options'" -ForegroundColor White
Write-Host "   (sometimes called 'Administrator settings')" -ForegroundColor Gray
Write-Host ""
Write-Host "3. Toggle ON 'Allow multiple apps to use camera at the same time'" -ForegroundColor White
Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host ""
Pause