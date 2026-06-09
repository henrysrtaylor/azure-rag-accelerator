# deploy-infrastructure.ps1
# Azure CLI script to create all required Azure resources for the RAG accelerator
#
# Usage: .\deploy-infrastructure.ps1 -Prefix "myrag" -Location "uksouth" -SubscriptionId "your-sub-id"

param(
    [Parameter(Mandatory=$true)][string]$Prefix,
    [Parameter(Mandatory=$true)][string]$Location,
    [Parameter(Mandatory=$true)][string]$SubscriptionId
)

# TODO: Add Azure CLI commands
