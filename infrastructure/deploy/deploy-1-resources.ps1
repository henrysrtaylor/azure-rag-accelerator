# deploy-1-resources.ps1
# Creates Azure resources for the RAG accelerator via ARM template
#
# Usage: .\deploy-1-resources.ps1
#        (will prompt for values interactively)

$ErrorActionPreference = "Stop"

Write-Host "`n=== RAG Accelerator - Step 1: Resources ===" -ForegroundColor Cyan

# Check if logged in
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Not logged in. Opening browser for Azure login..." -ForegroundColor Yellow
    az login
    $account = az account show | ConvertFrom-Json
}
Write-Host "Logged in as: $($account.user.name)" -ForegroundColor Green

# List subscriptions and prompt
Write-Host "`nAvailable subscriptions:" -ForegroundColor Cyan
az account list --query "[].{Name:name, Id:id}" --output table

$SubscriptionId = Read-Host "`nEnter Subscription ID"
$Prefix = Read-Host "Enter resource prefix (e.g., myrag)"
$Location = Read-Host "Enter location (e.g., uksouth, ukwest, eastus) [ukwest]"
if ([string]::IsNullOrWhiteSpace($Location)) { $Location = "ukwest" }

# Resource naming (for display only - ARM template generates names)
$ResourceGroup = "rg-$Prefix"

Write-Host "`nWill create in $ResourceGroup (all resources via ARM):" -ForegroundColor Cyan
Write-Host "  Storage Accounts (documents + function app)"
Write-Host "  AI Search (Standard tier)"
Write-Host "  AI Services"
Write-Host "  Function App (Elastic Premium, Python 3.11)"
Write-Host "  Application Insights"

$confirm = Read-Host "`nProceed? (Y/n)"
if ($confirm -eq "n") { Write-Host "Aborted." -ForegroundColor Red; exit }

# Set subscription
Write-Host "`n[1/2] Setting subscription and creating Resource Group..." -ForegroundColor Yellow
az account set --subscription $SubscriptionId
az group create --name $ResourceGroup --location $Location --output none

# Deploy all resources via ARM template
Write-Host "[2/2] Deploying all resources via ARM template..." -ForegroundColor Yellow
$templatePath = Join-Path $PSScriptRoot "arm.json"
$armOutput = az deployment group create `
    --resource-group $ResourceGroup `
    --template-file $templatePath `
    --parameters prefix=$Prefix location=$Location `
    --query "properties.outputs" -o json | ConvertFrom-Json

# Extract outputs
$StorageAccount = $armOutput.storageAccountName.value
$FuncStorageAccount = $armOutput.funcStorageAccountName.value
$SearchService = $armOutput.searchServiceName.value
$SearchMI = $armOutput.searchServicePrincipalId.value
$AppInsights = $armOutput.appInsightsName.value
$AIProject = $armOutput.aiServicesName.value
$FunctionApp = $armOutput.functionAppName.value
$FunctionMI = $armOutput.functionAppPrincipalId.value

# Output summary
Write-Host "`n=== Resources Created ===" -ForegroundColor Green
Write-Host "Resource Group:    $ResourceGroup"
Write-Host "Storage Account:   $StorageAccount"
Write-Host "Func Storage:      $FuncStorageAccount"
Write-Host "AI Search:         $SearchService (MI: $SearchMI)"
Write-Host "AI Services:       $AIProject"
Write-Host "Function App:      $FunctionApp (MI: $FunctionMI)"
Write-Host "App Insights:      $AppInsights"

Write-Host "`n=== Next ===" -ForegroundColor Cyan
Write-Host "Run: .\deploy-2-models.ps1"
