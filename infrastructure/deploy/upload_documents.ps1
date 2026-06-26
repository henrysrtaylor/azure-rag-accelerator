<#
.DESCRIPTION
    Upload documents to blob storage.
    Uploads files from data/documents to Azure Blob Storage.
    Reads storage account from .env file.

.PARAMETER Overwrite
    Overwrite existing blobs. Defaults to false.

.EXAMPLE
    .\upload_documents.ps1
    .\upload_documents.ps1 -Overwrite
#>

param(
    [switch]$Overwrite = $false
)

$ErrorActionPreference = "Stop"

Write-Host ""
Write-Host "========================================"
Write-Host "       Upload Documents to Azure"
Write-Host "========================================"
Write-Host ""

# ============================================================
# STEP 1: Load configuration from .env
# ============================================================
Write-Host "[1/4] Loading configuration from .env..." -ForegroundColor Cyan

$ProjectRoot = (Get-Item $PSScriptRoot).Parent.Parent.FullName
$EnvFile = Join-Path $ProjectRoot ".env"

if (-not (Test-Path $EnvFile)) {
    Write-Host "ERROR: .env file not found at $EnvFile" -ForegroundColor Red
    Write-Host "Run deploy_infra.ps1 first to generate the .env file." -ForegroundColor Yellow
    exit 1
}

$envContent = Get-Content $EnvFile
$StorageAccount = ($envContent | Where-Object { $_ -match "^BLOB_ACCOUNT_NAME=" }) -replace "BLOB_ACCOUNT_NAME=", "" -replace "'", ""
$ContainerName = ($envContent | Where-Object { $_ -match "^BLOB_CONTAINER_NAME_DOCUMENTS=" }) -replace "BLOB_CONTAINER_NAME_DOCUMENTS=", "" -replace "'", ""

if ([string]::IsNullOrWhiteSpace($StorageAccount)) {
    Write-Host "ERROR: BLOB_ACCOUNT_NAME not found in .env" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($ContainerName)) {
    $ContainerName = "documents"
    Write-Host "  Using default container name: $ContainerName" -ForegroundColor Yellow
}

Write-Host "  Storage Account: $StorageAccount" -ForegroundColor Green
Write-Host "  Container: $ContainerName" -ForegroundColor Green

# ============================================================
# STEP 2: Determine source folder
# ============================================================
Write-Host ""
Write-Host "[2/4] Checking source folder..." -ForegroundColor Cyan

$SourceFolder = Join-Path $ProjectRoot "data\documents"

if (-not (Test-Path $SourceFolder)) {
    Write-Host "ERROR: Source folder not found: $SourceFolder" -ForegroundColor Red
    exit 1
}

# Supported file extensions
$Extensions = @("*.pdf", "*.doc", "*.docx", "*.txt", "*.md", "*.rtf", "*.csv", "*.json", "*.xml", "*.html")

$Files = Get-ChildItem -Path $SourceFolder -File -Recurse -Include $Extensions
$FileCount = $Files.Count

if ($FileCount -eq 0) {
    Write-Host "WARNING: No supported files found in $SourceFolder" -ForegroundColor Yellow
    Write-Host "  Supported: pdf, doc, docx, txt, md, rtf, csv, json, xml, html" -ForegroundColor Gray
    exit 0
}

Write-Host "  Source: $SourceFolder" -ForegroundColor Green
Write-Host "  Files to upload: $FileCount" -ForegroundColor Green

# ============================================================
# STEP 3: Verify Azure login
# ============================================================
Write-Host ""
Write-Host "[3/4] Verifying Azure login..." -ForegroundColor Cyan

$account = az account show 2>$null | ConvertFrom-Json
if (-not $account) {
    Write-Host "ERROR: Not logged in to Azure. Run 'az login' first." -ForegroundColor Red
    exit 1
}
Write-Host "  Logged in as: $($account.user.name)" -ForegroundColor Green

# ============================================================
# STEP 4: Upload documents
# ============================================================
Write-Host ""
Write-Host "[4/4] Uploading documents..." -ForegroundColor Cyan

# Build az command arguments
$azArgs = @(
    "storage", "blob", "upload-batch",
    "--account-name", $StorageAccount,
    "--destination", $ContainerName,
    "--source", $SourceFolder,
    "--auth-mode", "login"
)

if ($Overwrite) {
    $azArgs += "--overwrite"
}

Write-Host "  Uploading $FileCount file(s)..." -ForegroundColor Gray

& az @azArgs

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Upload failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "         Upload Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Uploaded $FileCount file(s) to:" -ForegroundColor Green
Write-Host "  https://$StorageAccount.blob.core.windows.net/$ContainerName" -ForegroundColor Cyan
Write-Host ""
Write-Host "Next steps:" -ForegroundColor Yellow
Write-Host "  1. Run the indexer to process new documents"
Write-Host "  2. Or wait for scheduled indexer run"
Write-Host ""
