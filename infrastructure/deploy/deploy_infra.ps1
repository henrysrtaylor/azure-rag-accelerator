# deploy.ps1
# Combined deployment: Resources → RBAC/Auth → Models → Generate .env
#
# Usage: .\deploy.ps1

$ErrorActionPreference = "Continue"

$banner = @"

================================================================
           RAG Accelerator - Full Deployment                   
                                                                
  1. Resources (ARM template)                                   
  2. RBAC & Entra ID Auth                                       
  3. AI Models                                                  
  4. Generate .env file                                         
================================================================

"@
Write-Host $banner -ForegroundColor Cyan

# ============================================
# Prerequisites Check
# ============================================
$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "Not logged in. Opening browser for Azure login..." -ForegroundColor Yellow
    az login
    $account = az account show | ConvertFrom-Json
}
Write-Host "Logged in as: $($account.user.name)" -ForegroundColor Green

# List subscriptions
Write-Host "`nAvailable subscriptions:" -ForegroundColor Cyan
az account list --query "[].{Name:name, Id:id}" --output table

# Prompt for inputs
$SubscriptionId = Read-Host "`nEnter Subscription ID"
$Prefix = Read-Host "Enter resource prefix (e.g., myrag)"
$Location = Read-Host "Enter location (e.g., uksouth, westeurope) [uksouth]"
if ([string]::IsNullOrWhiteSpace($Location)) { $Location = "uksouth" }

# Resource naming (ARM template generates these)
$ResourceGroup = "rg-$Prefix"
$StorageAccount = "st$($Prefix -replace '-','')"
$SearchService = "srch-$Prefix"
$FunctionApp = "func-$Prefix"
$AIServices = "ai-$Prefix"
$AppInsights = "appi-$Prefix"

Write-Host "`n=== Deployment Plan ===" -ForegroundColor Cyan
Write-Host "Subscription:    $SubscriptionId"
Write-Host "Resource Group:  $ResourceGroup"
Write-Host "Location:        $Location"
Write-Host "Storage:         $StorageAccount"
Write-Host "AI Search:       $SearchService"
Write-Host "Function App:    $FunctionApp"
Write-Host "AI Services:     $AIServices"

$confirm = Read-Host "`nProceed with deployment? (Y/n)"
if ($confirm -eq "n") { Write-Host "Aborted." -ForegroundColor Red; exit }

az account set --subscription $SubscriptionId
$TenantId = (az account show --query tenantId -o tsv)

# ============================================
# STEP 1: Create Resources
# ============================================
$divider = "=" * 60
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 1: Creating Azure Resources" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

# Create resource group
Write-Host "`n[1/2] Creating Resource Group..." -ForegroundColor Yellow
$result = az group create --name $ResourceGroup --location $Location --output none 2>&1
if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Failed to create resource group" -ForegroundColor Red
    Write-Host $result -ForegroundColor Red
    exit 1
}
Write-Host "  Resource Group: $ResourceGroup" -ForegroundColor Green

# Deploy ARM template
Write-Host "[2/2] Deploying ARM template (this takes ~5 minutes)..." -ForegroundColor Yellow
$templatePath = Join-Path $PSScriptRoot "config\resources.json"
$armResult = az deployment group create --resource-group $ResourceGroup --template-file $templatePath --parameters prefix=$Prefix location=$Location --query "properties.outputs" -o json 2>&1

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: ARM deployment failed" -ForegroundColor Red
    Write-Host $armResult -ForegroundColor Red
    exit 1
}

$armOutput = $armResult | ConvertFrom-Json
$StorageAccount = $armOutput.storageAccountName.value
$FuncStorageAccount = $armOutput.funcStorageAccountName.value
$SearchService = $armOutput.searchServiceName.value
$SearchPrincipalId = $armOutput.searchServicePrincipalId.value
$AIServices = $armOutput.aiServicesName.value
$FunctionApp = $armOutput.functionAppName.value
$FunctionPrincipalId = $armOutput.functionAppPrincipalId.value
$AppInsights = $armOutput.appInsightsName.value

Write-Host "`n=== Resources Created ===" -ForegroundColor Green
Write-Host "  Storage:      $StorageAccount"
Write-Host "  Func Storage: $FuncStorageAccount"
Write-Host "  AI Search:    $SearchService (MI: $SearchPrincipalId)"
Write-Host "  AI Services:  $AIServices"
Write-Host "  Function App: $FunctionApp (MI: $FunctionPrincipalId)"
Write-Host "  App Insights: $AppInsights"

# ============================================
# STEP 2: RBAC Permissions
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 2: Assigning RBAC Permissions" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

$StorageScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccount"
$SearchScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Search/searchServices/$SearchService"
$AIScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.CognitiveServices/accounts/$AIServices"
$AppInsightsScope = "/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Insights/components/$AppInsights"

$currentUserId = (az ad signed-in-user show --query id -o tsv)

$rbacAssigned = @()
$rbacFailed = @()

# Search MI Roles
Write-Host "`n[1/11] Search MI -> Storage (Blob Data Reader)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $SearchPrincipalId --role "Storage Blob Data Reader" --scope $StorageScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Search MI -> Storage Blob Data Reader" }
else { $rbacFailed += "Search MI -> Storage Blob Data Reader" }

Write-Host "[2/11] Search MI -> Storage (Blob Data Contributor)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $SearchPrincipalId --role "Storage Blob Data Contributor" --scope $StorageScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Search MI -> Storage Blob Data Contributor" }
else { $rbacFailed += "Search MI -> Storage Blob Data Contributor" }

Write-Host "[3/11] Search MI -> AI Services (Cognitive Services OpenAI User)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $SearchPrincipalId --role "Cognitive Services OpenAI User" --scope $AIScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Search MI -> Cognitive Services OpenAI User" }
else { $rbacFailed += "Search MI -> Cognitive Services OpenAI User" }

# Function MI Roles
Write-Host "[4/11] Function MI -> AI Services (Cognitive Services User)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $FunctionPrincipalId --role "Cognitive Services User" --scope $AIScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Function MI -> Cognitive Services User" }
else { $rbacFailed += "Function MI -> Cognitive Services User" }

Write-Host "[5/11] Function MI -> Search (Search Index Data Reader)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $FunctionPrincipalId --role "Search Index Data Reader" --scope $SearchScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Function MI -> Search Index Data Reader" }
else { $rbacFailed += "Function MI -> Search Index Data Reader" }

Write-Host "[6/11] Function MI -> Storage (Blob Data Reader)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $FunctionPrincipalId --role "Storage Blob Data Reader" --scope $StorageScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Function MI -> Storage Blob Data Reader" }
else { $rbacFailed += "Function MI -> Storage Blob Data Reader" }

# Current User Roles
Write-Host "[7/11] Current User -> Storage (Blob Data Contributor)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $currentUserId --role "Storage Blob Data Contributor" --scope $StorageScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Current User -> Storage Blob Data Contributor" }
else { $rbacFailed += "Current User -> Storage Blob Data Contributor" }

Write-Host "[8/11] Current User -> Search (Search Service Contributor)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $currentUserId --role "Search Service Contributor" --scope $SearchScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Current User -> Search Service Contributor" }
else { $rbacFailed += "Current User -> Search Service Contributor" }

Write-Host "[9/11] Current User -> Search (Search Index Data Reader)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $currentUserId --role "Search Index Data Reader" --scope $SearchScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Current User -> Search Index Data Reader" }
else { $rbacFailed += "Current User -> Search Index Data Reader" }

Write-Host "[10/11] Current User -> AI Services (Cognitive Services OpenAI User)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $currentUserId --role "Cognitive Services OpenAI User" --scope $AIScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Current User -> Cognitive Services OpenAI User" }
else { $rbacFailed += "Current User -> Cognitive Services OpenAI User" }

Write-Host "[11/11] Current User -> App Insights (Monitoring Metrics Publisher)..." -ForegroundColor Yellow
$result = az role assignment create --assignee $currentUserId --role "Monitoring Metrics Publisher" --scope $AppInsightsScope --output none 2>&1
if ($LASTEXITCODE -eq 0) { $rbacAssigned += "Current User -> Monitoring Metrics Publisher" }
else { $rbacFailed += "Current User -> Monitoring Metrics Publisher" }

Write-Host "`n=== RBAC Summary ===" -ForegroundColor Green
Write-Host "  Assigned: $($rbacAssigned.Count)/11"
if ($rbacFailed.Count -gt 0) {
    Write-Host "  Failed: $($rbacFailed -join ', ')" -ForegroundColor Red
}

# Enable RBAC authentication on Search Service
Write-Host "`nEnabling RBAC auth on Search Service..." -ForegroundColor Yellow
az search service update --name $SearchService --resource-group $ResourceGroup --auth-options aadOrApiKey --aad-auth-failure-mode http401WithBearerChallenge --output none 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "  Search RBAC auth enabled" -ForegroundColor Green
} else {
    Write-Host "  WARNING: Could not enable Search RBAC auth" -ForegroundColor Yellow
}

# ============================================
# STEP 2b: Function App Entra ID Auth
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 2b: Function App Entra ID Authentication" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

# Create App Registration
Write-Host "`n[1/4] Creating App Registration..." -ForegroundColor Yellow
$appRegResult = az ad app create --display-name "$FunctionApp-auth" --sign-in-audience AzureADMyOrg --identifier-uris "api://$FunctionApp" --query "{appId:appId, objectId:id}" -o json 2>&1

$AppClientId = $null
if ($LASTEXITCODE -eq 0 -or $appRegResult -match "appId") {
    try {
        $appReg = $appRegResult | ConvertFrom-Json -ErrorAction SilentlyContinue
        $AppClientId = $appReg.appId
    } catch {
        # App may already exist - try to get it
        $AppClientId = az ad app list --display-name "$FunctionApp-auth" --query "[0].appId" -o tsv 2>$null
    }
}

if (-not $AppClientId) {
    # Try to fetch existing
    $AppClientId = az ad app list --display-name "$FunctionApp-auth" --query "[0].appId" -o tsv 2>$null
}

if ($AppClientId) {
    Write-Host "  App Registration: $AppClientId" -ForegroundColor Green

    # Create Service Principal
    Write-Host "[2/4] Creating Service Principal..." -ForegroundColor Yellow
    az ad sp create --id $AppClientId --output none 2>$null

    # Get Search MI Application ID (different from Object ID)
    Write-Host "[3/4] Getting Search MI Application ID..." -ForegroundColor Yellow
    $SearchAppId = az ad sp show --id $SearchPrincipalId --query appId -o tsv 2>$null
    if ($SearchAppId) {
        Write-Host "  Search MI App ID: $SearchAppId" -ForegroundColor Green
        Write-Host "  Search MI Object ID: $SearchPrincipalId" -ForegroundColor Green
    } else {
        Write-Host "  WARNING: Could not get Search MI Application ID" -ForegroundColor Yellow
    }

    # Configure auth with client/identity restrictions
    Write-Host "[4/4] Configuring Function App authentication..." -ForegroundColor Yellow
    az webapp auth config-version upgrade --name $FunctionApp --resource-group $ResourceGroup --output none 2>$null
    
    # Enable auth with Return401 for unauthenticated
    az webapp auth update --name $FunctionApp --resource-group $ResourceGroup --enabled true --unauthenticated-client-action Return401 --output none 2>$null
    
    # Add Microsoft identity provider (Entra ID)
    if ($SearchAppId) {
        # With client restrictions
        $authResult = az webapp auth microsoft update `
            --name $FunctionApp `
            --resource-group $ResourceGroup `
            --client-id $AppClientId `
            --issuer "https://sts.windows.net/$TenantId/v2.0" `
            --allowed-audiences "api://$FunctionApp" `
            --yes `
            --output none 2>&1
    } else {
        # Without restrictions
        $authResult = az webapp auth microsoft update `
            --name $FunctionApp `
            --resource-group $ResourceGroup `
            --client-id $AppClientId `
            --issuer "https://sts.windows.net/$TenantId/v2.0" `
            --allowed-audiences "api://$FunctionApp" `
            --yes `
            --output none 2>&1
    }

    if ($LASTEXITCODE -eq 0) {
        Write-Host "  Auth configured successfully" -ForegroundColor Green
        Write-Host "  Identity Provider: Microsoft (Entra ID)" -ForegroundColor Green
        Write-Host "  Client ID: $AppClientId" -ForegroundColor Green
        
        # Add allowedApplications via REST (CLI doesn't support this)
        if ($SearchAppId -and $SearchPrincipalId) {
            Write-Host "  Adding Search MI to allowed applications..." -ForegroundColor Yellow
            
            # Write JSON to temp file (az rest handles @file syntax better than inline JSON)
            $authJson = @"
{"properties":{"platform":{"enabled":true,"runtimeVersion":"~1"},"globalValidation":{"requireAuthentication":true,"unauthenticatedClientAction":"Return401"},"identityProviders":{"azureActiveDirectory":{"enabled":true,"registration":{"clientId":"$AppClientId","openIdIssuer":"https://sts.windows.net/$TenantId/v2.0"},"validation":{"allowedAudiences":["api://$FunctionApp"],"defaultAuthorizationPolicy":{"allowedApplications":["$SearchAppId"],"allowedPrincipals":{"identities":["$SearchPrincipalId"]}}}}}}}
"@
            $authFile = Join-Path $env:TEMP "func-auth-$FunctionApp.json"
            $authJson | Out-File -FilePath $authFile -Encoding ascii -NoNewline
            
            $restResult = az rest --method PUT `
                --uri "https://management.azure.com/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Web/sites/$FunctionApp/config/authsettingsV2?api-version=2022-03-01" `
                --body "@$authFile" 2>&1
            
            Remove-Item $authFile -ErrorAction SilentlyContinue
            
            if ($LASTEXITCODE -eq 0) {
                Write-Host "  Allowed client apps: $SearchAppId (Search MI)" -ForegroundColor Green
            } else {
                Write-Host "  WARNING: Could not set allowedApplications" -ForegroundColor Yellow
            }
        }
    } else {
        Write-Host "  WARNING: Auth configuration may have failed" -ForegroundColor Yellow
        Write-Host "  $authResult" -ForegroundColor Yellow
    }
} else {
    Write-Host "  ERROR: Could not create/find App Registration" -ForegroundColor Red
}

# ============================================
# STEP 2c: User Auth App Registration (MSAL Login)
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 2c: User Auth App Registration (MSAL Login)" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

$UserAuthAppName = "$Prefix-user-auth"
Write-Host "`n[1/3] Creating User Auth App Registration..." -ForegroundColor Yellow

# Create with redirect URI for local dev
$userAppResult = az ad app create --display-name $UserAuthAppName --sign-in-audience AzureADMyOrg --public-client-redirect-uris "http://localhost" --query "appId" -o tsv 2>&1

$UserAuthClientId = $null
if ($LASTEXITCODE -eq 0 -and $userAppResult -notmatch "ERROR") {
    $UserAuthClientId = $userAppResult
} else {
    # Try to get existing
    $UserAuthClientId = az ad app list --display-name $UserAuthAppName --query "[0].appId" -o tsv 2>$null
}

if ($UserAuthClientId) {
    Write-Host "  User Auth App: $UserAuthClientId" -ForegroundColor Green
    
    # Add User.Read permission
    Write-Host "[2/3] Adding Microsoft Graph User.Read permission..." -ForegroundColor Yellow
    # User.Read permission ID: e1fe6dd8-ba31-4d61-89e7-88639da4683d
    az ad app permission add --id $UserAuthClientId --api 00000003-0000-0000-c000-000000000000 --api-permissions e1fe6dd8-ba31-4d61-89e7-88639da4683d=Scope --output none 2>$null
    
    # Add groups claim to token
    Write-Host "[3/3] Configuring groups claim in token..." -ForegroundColor Yellow
    az ad app update --id $UserAuthClientId --set groupMembershipClaims=SecurityGroup --output none 2>$null
    
    Write-Host "  Groups claim enabled (SecurityGroup)" -ForegroundColor Green
    Write-Host "`n  NOTE: Grant admin consent in Azure Portal -> App registrations -> $UserAuthAppName -> API permissions" -ForegroundColor Yellow
} else {
    Write-Host "  WARNING: Could not create User Auth App" -ForegroundColor Yellow
    $UserAuthClientId = "<create-manually>"
}

# ============================================
# STEP 3: Deploy AI Models
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 3: Deploying AI Models" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

$modelsPath = Join-Path $PSScriptRoot "config\models.json"
$models = Get-Content $modelsPath | ConvertFrom-Json

$modelsDeployed = @()
$modelsFailed = @()
$i = 1
$total = $models.Count

foreach ($model in $models) {
    Write-Host "`n[$i/$total] Deploying $($model.name)..." -ForegroundColor Yellow
    
    $result = az cognitiveservices account deployment create --name $AIServices --resource-group $ResourceGroup --deployment-name $model.name --model-name $model.name --model-version $model.version --model-format $model.format --sku-name "GlobalStandard" --sku-capacity $model.capacity --output none 2>&1
    
    if ($LASTEXITCODE -eq 0) {
        $modelsDeployed += $model.name
        Write-Host "  Deployed: $($model.name)" -ForegroundColor Green
    } else {
        $modelsFailed += $model.name
        Write-Host "  Failed: $($model.name)" -ForegroundColor Red
    }
    $i++
}

Write-Host "`n=== Models Summary ===" -ForegroundColor Green
Write-Host "  Deployed: $($modelsDeployed.Count)/$total"
if ($modelsFailed.Count -gt 0) {
    Write-Host "  Failed: $($modelsFailed -join ', ')" -ForegroundColor Red
}

# ============================================
# STEP 4: Generate .env File
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 4: Generating .env File" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

# Get Application Insights connection string
Write-Host "  Looking up Application Insights..." -ForegroundColor Yellow
$AppInsightsConnStr = az resource show --resource-group $ResourceGroup --resource-type "Microsoft.Insights/components" --name $AppInsights --query "properties.ConnectionString" -o tsv 2>$null
if (-not $AppInsightsConnStr) {
    $AppInsightsConnStr = "<run-after-deployment>"
    Write-Host "  WARNING: Could not get App Insights connection string" -ForegroundColor Yellow
} else {
    Write-Host "  App Insights connection string retrieved" -ForegroundColor Green
}

$envContent = @"
# Generated by deploy.ps1 on $(Get-Date -Format "yyyy-MM-dd HH:mm:ss")
# Prefix: $Prefix | Location: $Location

# parameters to set dependent on use case
PARAMETER_CHUNK_SIZE='1000'
PARAMETER_CHUNK_OVERLAP='100'
PARAMETER_NUMBER_DOC_RETRIEVE='5'
PARAMETER_K_NEAREST_NEIGHBORS='3'
PARAMETER_SUGGESTED_QUESTIONS='3'
PARAMETER_ALLOWED_TOPICS='any topic'
PARAMETER_HATE_GUARDRAIL_THRESHOLD='4'
PARAMETER_SELFHARM_GUARDRAIL_THRESHOLD='4'
PARAMETER_SEXUAL_GUARDRAIL_THRESHOLD='4'
PARAMETER_VIOLENCE_GUARDRAIL_THRESHOLD='4'

# option flags to enable/disable features
OPTION_QUERY_REFINEMENT='true'
OPTION_GUARDRAIL_CHECKS='true'
OPTION_SUGGESTED_QUESTIONS='true'
OPTION_SECURITY_GROUPS='true'

# model and embedding configuration
AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL='gpt-5.4'
AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL='gpt-5.4-mini'
AZURE_FOUNDRY_JUDGE_MODEL='gpt-5.4-mini'
AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL='text-embedding-3-large'
AZURE_FOUNDRY_EMBEDDING_DIMENSIONS='3072'
AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL_VERSION='2026-03-05'
AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL_VERSION='2026-03-17'
AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL_VERSION='1'
AZURE_FOUNDRY_REASONING_EFFORT='low'

# Azure specific configuration
AZURE_SUBSCRIPTION_ID='$SubscriptionId'
AZURE_RESOURCE_GROUP='$ResourceGroup'

AZURE_FOUNDRY_RESOURCE='$AIServices'
AZURE_FOUNDRY_ENDPOINT='https://$AIServices.services.ai.azure.com'
AZURE_FOUNDRY_API_VERSION='2025-01-01-preview'
AZURE_CONTENT_MODERATOR_ENDPOINT='https://$AIServices.cognitiveservices.azure.com/'
AZURE_CONTENT_MODERATOR_API_VERSION='2024-09-01'
COGNITIVE_SERVICES_ENDPOINT='https://$AIServices.cognitiveservices.azure.com/'

AZURE_SEARCH_SERVICE_ENDPOINT='https://$SearchService.search.windows.net'
AZURE_SEARCH_API_VERSION='2023-11-01'
AZURE_SEARCH_PROJECT_PREFIX='$Prefix'

BLOB_ACCOUNT_NAME='$StorageAccount'
BLOB_ACCOUNT_URL='https://$StorageAccount.blob.core.windows.net'
BLOB_CONNECTION_STRING='ResourceId=/subscriptions/$SubscriptionId/resourceGroups/$ResourceGroup/providers/Microsoft.Storage/storageAccounts/$StorageAccount'
BLOB_CONTAINER_NAME_DOCUMENTS='documents'

# Application Insights logging
LOGGING_CONNECTION_STRING='$AppInsightsConnStr'

# Azure Function for DLS (indexer WebApiSkill)
FUNCTION_APP_NAME='$FunctionApp'
AZURE_FUNCTION_SECURITY_GROUPS_URL='https://$FunctionApp.azurewebsites.net/api/get_security_groups'
AZURE_FUNCTION_AUTH_RESOURCE_ID='api://$FunctionApp'

# Entra ID Authentication (for MSAL user login)
AZURE_CLIENT_ID='$UserAuthClientId'
AZURE_TENANT_ID='$TenantId'
"@

$envOutputPath = Join-Path (Split-Path (Split-Path $PSScriptRoot -Parent) -Parent) ".env"
$envContent | Out-File -FilePath $envOutputPath -Encoding utf8

Write-Host "`n  Generated: .env (in project root)" -ForegroundColor Green

# ============================================
# Deployment Complete
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "DEPLOYMENT COMPLETE" -ForegroundColor Green
Write-Host $divider -ForegroundColor Cyan

Write-Host @"

=== Summary ===
Resource Group:     $ResourceGroup
Storage Account:    $StorageAccount
AI Search:          $SearchService
AI Services:        $AIServices
Function App:       $FunctionApp
Function Auth App:  $AppClientId
User Auth App:      $UserAuthClientId
App Insights:       $AppInsights
Models Deployed:    $($modelsDeployed.Count)/$total

=== Generated Files ===
.env - Ready to use

"@ -ForegroundColor Cyan

# ============================================
# STEP 5: Validation Tests
# ============================================
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "STEP 5: Validation Tests" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

$testsPassed = @()
$testsFailed = @()

# Test 1: Verify resources exist
Write-Host "`n[1/5] Verifying resources exist..." -ForegroundColor Yellow

$resources = @(
    @{ Type = "Storage"; Name = $StorageAccount; Cmd = "az storage account show --name $StorageAccount --resource-group $ResourceGroup --query name -o tsv" },
    @{ Type = "AI Search"; Name = $SearchService; Cmd = "az search service show --name $SearchService --resource-group $ResourceGroup --query name -o tsv" },
    @{ Type = "AI Services"; Name = $AIServices; Cmd = "az cognitiveservices account show --name $AIServices --resource-group $ResourceGroup --query name -o tsv" },
    @{ Type = "Function App"; Name = $FunctionApp; Cmd = "az functionapp show --name $FunctionApp --resource-group $ResourceGroup --query name -o tsv" }
)

foreach ($r in $resources) {
    $result = Invoke-Expression $r.Cmd 2>$null
    if ($result -eq $r.Name) {
        Write-Host "  + $($r.Type): $($r.Name)" -ForegroundColor Green
        $testsPassed += "$($r.Type) exists"
    } else {
        Write-Host "  x $($r.Type): $($r.Name) NOT FOUND" -ForegroundColor Red
        $testsFailed += "$($r.Type) missing"
    }
}

# Test 2: Verify managed identities
Write-Host "`n[2/5] Verifying managed identities..." -ForegroundColor Yellow

$searchMI = az search service show --name $SearchService --resource-group $ResourceGroup --query "identity.principalId" -o tsv 2>$null
$funcMI = az functionapp identity show --name $FunctionApp --resource-group $ResourceGroup --query "principalId" -o tsv 2>$null

if ($searchMI) {
    Write-Host "  + Search MI: $searchMI" -ForegroundColor Green
    $testsPassed += "Search MI enabled"
} else {
    Write-Host "  x Search MI not enabled" -ForegroundColor Red
    $testsFailed += "Search MI missing"
}

if ($funcMI) {
    Write-Host "  + Function MI: $funcMI" -ForegroundColor Green
    $testsPassed += "Function MI enabled"
} else {
    Write-Host "  x Function MI not enabled" -ForegroundColor Red
    $testsFailed += "Function MI missing"
}

# Test 3: Verify model deployments
Write-Host "`n[3/5] Verifying model deployments..." -ForegroundColor Yellow

$deployedModels = az cognitiveservices account deployment list --name $AIServices --resource-group $ResourceGroup --query "[].name" -o tsv 2>$null
$expectedModels = @("gpt-5.4", "gpt-5.4-mini", "text-embedding-3-large")

foreach ($model in $expectedModels) {
    if ($deployedModels -contains $model) {
        Write-Host "  + Model: $model" -ForegroundColor Green
        $testsPassed += "Model $model deployed"
    } else {
        Write-Host "  x Model: $model NOT DEPLOYED" -ForegroundColor Red
        $testsFailed += "Model $model missing"
    }
}

# Test 4: Verify Function App auth
Write-Host "`n[4/5] Verifying Function App authentication..." -ForegroundColor Yellow

$authEnabled = az webapp auth show --name $FunctionApp --resource-group $ResourceGroup --query "properties.platform.enabled" -o tsv 2>$null
if ($authEnabled -eq "true") {
    Write-Host "  + Function App auth enabled" -ForegroundColor Green
    $testsPassed += "Function auth enabled"
} else {
    Write-Host "  x Function App auth NOT enabled" -ForegroundColor Red
    $testsFailed += "Function auth missing"
}

# Test 5: Verify App Registrations
Write-Host "`n[5/5] Verifying App Registrations..." -ForegroundColor Yellow

$funcAuthApp = az ad app list --display-name "$FunctionApp-auth" --query "[0].appId" -o tsv 2>$null
$userAuthApp = az ad app list --display-name "$UserAuthAppName" --query "[0].appId" -o tsv 2>$null

if ($funcAuthApp) {
    Write-Host "  + Function Auth App: $funcAuthApp" -ForegroundColor Green
    $testsPassed += "Function Auth App exists"
} else {
    Write-Host "  x Function Auth App NOT FOUND" -ForegroundColor Red
    $testsFailed += "Function Auth App missing"
}

if ($userAuthApp) {
    Write-Host "  + User Auth App: $userAuthApp" -ForegroundColor Green
    $testsPassed += "User Auth App exists"
} else {
    Write-Host "  x User Auth App NOT FOUND" -ForegroundColor Red
    $testsFailed += "User Auth App missing"
}

# Test Summary
Write-Host "`n$divider" -ForegroundColor Cyan
Write-Host "VALIDATION SUMMARY" -ForegroundColor Cyan
Write-Host $divider -ForegroundColor Cyan

Write-Host "`nPassed: $($testsPassed.Count)" -ForegroundColor Green
Write-Host "Failed: $($testsFailed.Count)" -ForegroundColor Red

if ($testsFailed.Count -gt 0) {
    Write-Host "`nFailed tests:" -ForegroundColor Red
    foreach ($f in $testsFailed) { Write-Host "  - $f" -ForegroundColor Red }
    Write-Host "`nSome tests failed. Review above and fix manually if needed." -ForegroundColor Yellow
} else {
    Write-Host "`nAll validation tests passed!" -ForegroundColor Green
}
