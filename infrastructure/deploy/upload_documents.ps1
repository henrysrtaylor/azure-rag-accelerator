<#
.DESCRIPTION
    Upload documents to ADLS Gen2 storage.
    Uploads files from data/documents to an Azure Data Lake Storage Gen2 filesystem.
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
$StorageAccount = ($envContent | Where-Object { $_ -match "^STORAGE_ACCOUNT_NAME=" }) -replace "STORAGE_ACCOUNT_NAME=", "" -replace "'", ""

$ContainerName = ($envContent | Where-Object { $_ -match "^DOCUMENTS_FILESYSTEM_NAME=" }) -replace "DOCUMENTS_FILESYSTEM_NAME=", "" -replace "'", ""

if ([string]::IsNullOrWhiteSpace($StorageAccount)) {
    Write-Host "ERROR: STORAGE_ACCOUNT_NAME not found in .env" -ForegroundColor Red
    exit 1
}

if ([string]::IsNullOrWhiteSpace($ContainerName)) {
    $ContainerName = "documents"
    Write-Host "  Using default filesystem name: $ContainerName" -ForegroundColor Yellow
}

Write-Host "  Storage Account: $StorageAccount" -ForegroundColor Green
Write-Host "  Filesystem: $ContainerName" -ForegroundColor Green

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

Write-Host "  Uploading $FileCount file(s)..." -ForegroundColor Gray

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"

az storage fs create --account-name $StorageAccount --name $ContainerName --auth-mode login --output none
if ($LASTEXITCODE -ne 0) {
    $ErrorActionPreference = $previousErrorActionPreference
    Write-Host "ERROR: Could not create or access filesystem '$ContainerName'" -ForegroundColor Red
    exit 1
}

$uploaded = 0
foreach ($File in $Files) {
    $relativePath = $File.FullName.Substring($SourceFolder.Length).TrimStart("\", "/") -replace "\\", "/"
    $parentPath = Split-Path $relativePath -Parent

    if (-not [string]::IsNullOrWhiteSpace($parentPath)) {
        $directoryPath = $parentPath -replace "\\", "/"
        az storage fs directory create --account-name $StorageAccount --file-system $ContainerName --name $directoryPath --auth-mode login --output none
        if ($LASTEXITCODE -ne 0) {
            $ErrorActionPreference = $previousErrorActionPreference
            Write-Host "ERROR: Could not create directory $directoryPath" -ForegroundColor Red
            exit 1
        }
    }

    $azArgs = @(
        "storage", "fs", "file", "upload",
        "--account-name", $StorageAccount,
        "--file-system", $ContainerName,
        "--path", $relativePath,
        "--source", $File.FullName,
        "--auth-mode", "login",
        "--output", "none"
    )

    if ($Overwrite) {
        $azArgs += @("--overwrite", "true")
    }

    & az @azArgs

    if ($LASTEXITCODE -ne 0) {
        $ErrorActionPreference = $previousErrorActionPreference
        Write-Host "ERROR: Upload failed for $relativePath" -ForegroundColor Red
        exit 1
    }

    $uploaded++
}

$ErrorActionPreference = $previousErrorActionPreference

if ($LASTEXITCODE -ne 0) {
    Write-Host "ERROR: Upload failed" -ForegroundColor Red
    exit 1
}

Write-Host ""
Write-Host "========================================"
Write-Host "         Upload Complete!"
Write-Host "========================================"
Write-Host ""
Write-Host "Uploaded $uploaded file(s) to:" -ForegroundColor Green
Write-Host "  https://$StorageAccount.dfs.core.windows.net/$ContainerName" -ForegroundColor Cyan
Write-Host ""

