# deploy-3-rbac.ps1
# Assigns RBAC permissions between resources
#
# Usage: .\deploy-3-rbac.ps1

$ErrorActionPreference = "Stop"

Write-Host "`n=== RAG Accelerator - Step 3: RBAC Permissions ===" -ForegroundColor Cyan

$Prefix = Read-Host "Enter resource prefix (e.g., myrag)"
$ResourceGroup = "rg-$Prefix"
$SubscriptionId = (az account show --query id -o tsv)

# Resource naming (must match ARM template)
$StorageAccount = "st$($Prefix -replace '-','')"
$SearchService = "srch-$Prefix"
$FunctionApp = "func-$Prefix"

Write-Host "`nResource Group: $ResourceGroup"

# Get principal IDs
Write-Host "Getting managed identity principal IDs..." -ForegroundColor Yellow

$SearchPrincipalId = az search service show `
    --name $SearchService `
    --resource-group $ResourceGroup `
    --query "identity.principalId" -o tsv

$FunctionPrincipalId = az functionapp identity show `
    --name $FunctionApp `
    --resource-group $ResourceGroup `
    --query "principalId" -o tsv

Write-Host "  Search MI:   $SearchPrincipalId"
Write-Host "  Function MI: $FunctionPrincipalId`n"

# Storage scope
$StorageScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccount"

# 1. Search -> Storage (read blobs for indexer)
Write-Host "[1/4] Search MI -> Storage (Blob Data Reader)..." -ForegroundColor Yellow
az role assignment create `
    --assignee $SearchPrincipalId `
    --role "Storage Blob Data Reader" `
    --scope $StorageScope `
    --output none

# 2. Search -> Storage (read blob index tags if using them)
Write-Host "[2/4] Search MI -> Storage (Storage Blob Index Reader)..." -ForegroundColor Yellow
az role assignment create `
    --assignee $SearchPrincipalId `
    --role "Storage Blob Data Contributor" `
    --scope $StorageScope `
    --output none

# 3. Function App -> AI Foundry (inference)
Write-Host "[3/4] Function MI -> AI Foundry (Cognitive Services User)..." -ForegroundColor Yellow
$AIScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup"
az role assignment create `
    --assignee $FunctionPrincipalId `
    --role "Cognitive Services User" `
    --scope $AIScope `
    --output none

# 4. Function App -> Search (query)
Write-Host "[4/4] Function MI -> Search (Search Index Data Reader)..." -ForegroundColor Yellow
$SearchScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Search/searchServices/$SearchService"
az role assignment create `
    --assignee $FunctionPrincipalId `
    --role "Search Index Data Reader" `
    --scope $SearchScope `
    --output none

Write-Host "`n=== RBAC Assignments Complete ===" -ForegroundColor Green
Write-Host "Search MI -> Storage Blob Data Reader"
Write-Host "Search MI -> Storage Blob Data Contributor"
Write-Host "Function MI -> Cognitive Services User"
Write-Host "Function MI -> Search Index Data Reader"

Write-Host "`n=== Next ===" -ForegroundColor Cyan
Write-Host "1. Configure Function App Entra ID authentication"
Write-Host "2. Deploy Function App code: func azure functionapp publish $FunctionApp"
