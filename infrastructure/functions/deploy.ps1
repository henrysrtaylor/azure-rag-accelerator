# Deploy Function App
# Usage: ./deploy.ps1

Write-Host "`n=== Function App Deployment ===" -ForegroundColor Cyan

Push-Location $PSScriptRoot

# Read config from .env
$envPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) ".env"
if (Test-Path $envPath) {
    $envContent = Get-Content $envPath
    $FunctionAppName = ($envContent | Where-Object { $_ -match "^FUNCTION_APP_NAME=" }) -replace "FUNCTION_APP_NAME='?([^']+)'?", '$1'
    $ResourceGroup = ($envContent | Where-Object { $_ -match "^AZURE_RESOURCE_GROUP=" }) -replace "AZURE_RESOURCE_GROUP='?([^']+)'?", '$1'
}

if (-not $FunctionAppName) {
    Write-Host "ERROR: FUNCTION_APP_NAME not found in .env" -ForegroundColor Red
    Write-Host "Run deploy_infra.ps1 first" -ForegroundColor Yellow
    Pop-Location
    exit 1
}

Write-Host "Deploying to: $FunctionAppName" -ForegroundColor Yellow

# Deploy
func azure functionapp publish $FunctionAppName --python

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Deployment failed" -ForegroundColor Red
    Pop-Location
    exit 1
}

# Quick validation
Write-Host "`n=== Validation ===" -ForegroundColor Cyan

$functionUrl = "https://$FunctionAppName.azurewebsites.net/api/get_security_groups"
try {
    $null = Invoke-WebRequest -Uri $functionUrl -Method GET -UseBasicParsing -ErrorAction Stop
    Write-Host "Endpoint accessible" -ForegroundColor Green
} catch {
    $code = $_.Exception.Response.StatusCode.value__
    if ($code -in @(401, 400)) {
        Write-Host "Endpoint accessible (auth enabled)" -ForegroundColor Green
    } else {
        Write-Host "Endpoint returned: $code" -ForegroundColor Yellow
    }
}

Write-Host "`nDone! Function deployed to: $functionUrl" -ForegroundColor Green
Pop-Location