# Deploy Function App
# Usage: ./deploy.ps1

Push-Location $PSScriptRoot

# Read function app name from .env
$envPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) ".env"
if (Test-Path $envPath) {
    $envContent = Get-Content $envPath
    $FunctionAppName = ($envContent | Where-Object { $_ -match "^FUNCTION_APP_NAME=" }) -replace "FUNCTION_APP_NAME='?([^']+)'?", '$1'
}

if (-not $FunctionAppName) {
    Write-Host "ERROR: FUNCTION_APP_NAME not found in .env" -ForegroundColor Red
    Write-Host "Run deploy_infra.ps1 first or set FUNCTION_APP_NAME in .env" -ForegroundColor Yellow
    Pop-Location
    exit 1
}

Write-Host "Deploying to: $FunctionAppName" -ForegroundColor Yellow

func azure functionapp publish $FunctionAppName --publish-local-settings --overwrite-settings

Write-Host "Done!" -ForegroundColor Green
Pop-Location