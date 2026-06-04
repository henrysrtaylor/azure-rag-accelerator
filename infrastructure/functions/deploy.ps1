# Deploy Function App
# Usage: ./deploy.ps1       - Code only
#        ./deploy.ps1 -Full - Full deploy (code + settings)

param(
    [switch]$Full
)

Push-Location $PSScriptRoot

$FunctionAppName = "example-function-app" # Change to your function app name
$ResourceGroup = "example-resource-group" # Change to your resource group

Write-Host "Deploying to: $FunctionAppName (RG: $ResourceGroup)" -ForegroundColor Yellow

# Get function app's storage account and whitelist outbound IPs
Write-Host "`nConfiguring storage firewall..." -ForegroundColor Cyan
$storageConnStr = az functionapp config appsettings list --name $FunctionAppName --resource-group $ResourceGroup --query "[?name=='AzureWebJobsStorage'].value" -o tsv
if ($storageConnStr -match "AccountName=([^;]+)") {
    $storageAccountName = $matches[1]
    Write-Host "Storage account: $storageAccountName" -ForegroundColor Gray
    
    # Get outbound IPs and add to firewall
    $outboundIps = az functionapp show --name $FunctionAppName --resource-group $ResourceGroup --query "outboundIpAddresses" -o tsv
    $outboundIps -split ',' | ForEach-Object {
        az storage account network-rule add --account-name $storageAccountName --resource-group $ResourceGroup --ip-address $_ 2>$null
    }
    Write-Host "Added outbound IPs to storage firewall" -ForegroundColor Gray
}

# Core deployment
Write-Host "`nPublishing function app..." -ForegroundColor Cyan
func azure functionapp publish $FunctionAppName

# Publish settings on full deploy
if ($Full) {
    Write-Host "`nPublishing local settings to Azure..." -ForegroundColor Cyan
    func azure functionapp publish $FunctionAppName --publish-local-settings --overwrite-settings
    
    Write-Host "`nRestarting..." -ForegroundColor Cyan
    az functionapp restart --name $FunctionAppName --resource-group $ResourceGroup
}

Write-Host "`nDone!" -ForegroundColor Green
Pop-Location
