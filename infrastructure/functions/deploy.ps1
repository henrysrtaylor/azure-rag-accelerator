# Deploy Function App
# Usage: ./deploy.ps1

Push-Location $PSScriptRoot

$FunctionAppName = "example-function-app" # Change to your function app name

Write-Host "Deploying to: $FunctionAppName" -ForegroundColor Yellow

func azure functionapp publish $FunctionAppName --publish-local-settings --overwrite-settings

Write-Host "Done!" -ForegroundColor Green
Pop-Location