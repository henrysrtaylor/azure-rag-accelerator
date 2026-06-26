# Test Deployment Scripts
# Validates configs and runs ARM what-if without creating resources

param(
    [Parameter(Mandatory=$true)]
    [string]$ResourceGroup,
    
    [string]$Location = "westeurope",
    [string]$Prefix = "y"
)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$ConfigDir = Join-Path $ScriptDir "config"
$passed = @()
$failed = @()

Write-Host "=== Deployment Script Tests ===" -ForegroundColor Cyan
Write-Host "Resource Group: $ResourceGroup"
Write-Host "Location: $Location"
Write-Host "Prefix: $Prefix`n"

# ============================================
# Test 1: Validate JSON configs
# ============================================
Write-Host "[1/4] Validating JSON config files..." -ForegroundColor Yellow

$jsonFiles = @("resources.json", "models.json")
foreach ($file in $jsonFiles) {
    $path = Join-Path $ConfigDir $file
    if (Test-Path $path) {
        try {
            $null = Get-Content $path -Raw | ConvertFrom-Json
            $passed += "JSON valid: $file"
            Write-Host "  + $file" -ForegroundColor Green
        }
        catch {
            $failed += "JSON invalid: $file - $_"
            Write-Host "  x $file - Invalid JSON" -ForegroundColor Red
        }
    } else {
        $failed += "Missing: $file"
        Write-Host "  x $file - Not found" -ForegroundColor Red
    }
}

# ============================================
# Test 2: Validate ARM template
# ============================================
Write-Host "`n[2/4] Validating ARM template..." -ForegroundColor Yellow

$templatePath = Join-Path $ConfigDir "resources.json"

$validation = az deployment group validate --resource-group $ResourceGroup --template-file $templatePath --parameters prefix=$Prefix location=$Location --query "properties.provisioningState" -o tsv 2>&1

if ($LASTEXITCODE -eq 0) {
    $passed += "ARM template validation"
    Write-Host "  + ARM template is valid" -ForegroundColor Green
} else {
    $failed += "ARM template validation failed"
    Write-Host "  x ARM template validation failed" -ForegroundColor Red
    Write-Host "    $validation" -ForegroundColor Red
}

# ============================================
# Test 3: ARM What-If (preview changes)
# ============================================
Write-Host "`n[3/4] Running ARM what-if (preview)..." -ForegroundColor Yellow

$whatif = az deployment group what-if --resource-group $ResourceGroup --template-file $templatePath --parameters prefix=$Prefix location=$Location --no-pretty-print 2>&1

if ($LASTEXITCODE -eq 0) {
    $passed += "ARM what-if succeeded"
    Write-Host "  + What-if completed" -ForegroundColor Green
    
    $whatifStr = $whatif -join "`n"
    $createCount = ([regex]::Matches($whatifStr, '"changeType":\s*"Create"')).Count
    $modifyCount = ([regex]::Matches($whatifStr, '"changeType":\s*"Modify"')).Count
    $deleteCount = ([regex]::Matches($whatifStr, '"changeType":\s*"Delete"')).Count
    
    Write-Host "    Would create: $createCount resources" -ForegroundColor Cyan
    Write-Host "    Would modify: $modifyCount resources" -ForegroundColor Yellow
    Write-Host "    Would delete: $deleteCount resources" -ForegroundColor Red
} else {
    $failed += "ARM what-if failed"
    Write-Host "  x What-if failed" -ForegroundColor Red
    Write-Host "    $whatif" -ForegroundColor Red
}

# ============================================
# Test 4: Validate model config
# ============================================
Write-Host "`n[4/4] Validating model configuration..." -ForegroundColor Yellow

$modelsPath = Join-Path $ConfigDir "models.json"
$models = Get-Content $modelsPath -Raw | ConvertFrom-Json

foreach ($model in $models) {
    if ($model.name -and $model.version -and $model.capacity) {
        Write-Host "  + $($model.name) v$($model.version) (capacity: $($model.capacity))" -ForegroundColor Green
        $passed += "Model config: $($model.name)"
    } else {
        Write-Host "  x Invalid model config: $($model.name)" -ForegroundColor Red
        $failed += "Model config: $($model.name)"
    }
}

# ============================================
# Summary
# ============================================
Write-Host "`n=== Test Summary ===" -ForegroundColor Cyan
Write-Host "Passed: $($passed.Count)" -ForegroundColor Green
Write-Host "Failed: $($failed.Count)" -ForegroundColor Red

if ($failed.Count -gt 0) {
    Write-Host "`nFailed tests:" -ForegroundColor Red
    foreach ($f in $failed) { Write-Host "  - $f" -ForegroundColor Red }
    exit 1
} else {
    Write-Host "`nAll tests passed! Safe to deploy." -ForegroundColor Green
    exit 0
}
