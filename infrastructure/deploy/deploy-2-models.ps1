# deploy-2-models.ps1
# Deploys AI models to the Azure AI Services account
#
# Usage: .\deploy-2-models.ps1

$ErrorActionPreference = "Stop"

Write-Host "`n=== RAG Accelerator - Step 2: Model Deployments ===" -ForegroundColor Cyan

$Prefix = Read-Host "Enter resource prefix (e.g., myrag)"
$ResourceGroup = "rg-$Prefix"
$AIAccount = "ai-$Prefix"

Write-Host "`nAI Services Account: $AIAccount"
Write-Host "Resource Group: $ResourceGroup`n"

# Deploy gpt-5.4 (reasoning model)
Write-Host "[1/3] Deploying gpt-5.4 (large/reasoning)..." -ForegroundColor Yellow
az cognitiveservices account deployment create `
    --name $AIAccount `
    --resource-group $ResourceGroup `
    --deployment-name "gpt-5.4" `
    --model-name "gpt-5.4" `
    --model-version "2026-03-05" `
    --model-format OpenAI `
    --sku-capacity 10 `
    --sku-name Standard `
    --output none

# Deploy gpt-5.4-mini (small + judge)
Write-Host "[2/3] Deploying gpt-5.4-mini (small/judge)..." -ForegroundColor Yellow
az cognitiveservices account deployment create `
    --name $AIAccount `
    --resource-group $ResourceGroup `
    --deployment-name "gpt-5.4-mini" `
    --model-name "gpt-5.4-mini" `
    --model-version "2026-03-17" `
    --model-format OpenAI `
    --sku-capacity 10 `
    --sku-name Standard `
    --output none

# Deploy embeddings model
Write-Host "[3/3] Deploying text-embedding-3-large..." -ForegroundColor Yellow
az cognitiveservices account deployment create `
    --name $AIAccount `
    --resource-group $ResourceGroup `
    --deployment-name "text-embedding-3-large" `
    --model-name "text-embedding-3-large" `
    --model-version "1" `
    --model-format OpenAI `
    --sku-capacity 10 `
    --sku-name Standard `
    --output none

Write-Host "`n=== Models Deployed ===" -ForegroundColor Green
Write-Host "gpt-5.4:                 large/reasoning model"
Write-Host "gpt-5.4-mini:            small + judge model"
Write-Host "text-embedding-3-large:  embeddings"

Write-Host "`n=== Next ===" -ForegroundColor Cyan
Write-Host "Run: .\deploy-3-rbac.ps1"
