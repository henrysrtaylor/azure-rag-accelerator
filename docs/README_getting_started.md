# Getting Started

The following instructions are for Windows (PowerShell). For macOS/Linux, use bash equivalents or [install PowerShell](https://docs.microsoft.com/en-us/powershell/scripting/install/installing-powershell).

## Prerequisites

1. **Azure Permissions**: Owner or Contributor role on the target subscription (required to create resources and assign RBAC roles)
2. Install [Azure CLI](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
3. Install [Python 3.10+](https://www.python.org/downloads/)
4. Create a virtual environment:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

5. Login to Azure:

```powershell
az login
```

> **Note:** All steps below can be skipped, run manually, or edited to suit your preferences. The scripts are provided as a starting point - feel free to modify resource names, locations, RBAC assignments, or deploy individual components separately. See the other documentation files in `docs/` for guidance on customization.

---

## Deployment Steps

### Step 1: Deploy Infrastructure

Creates all Azure resources (Search, AI Services, Storage, Function App), assigns RBAC permissions, configures authentication, deploys models, and outputs `.env` file.

```powershell
cd infrastructure/deploy
.\deploy_infra.ps1
```

The script will prompt for:
- `Subscription ID` - Your Azure subscription (script lists available subscriptions)
- `Prefix` - Name prefix for all resources (lowercase, no special characters)
- `Location` - Azure region (e.g., "westeurope", "eastus", "uksouth")

> **Tip:** To change the deployed models, edit [infrastructure/deploy/config/models.json](../infrastructure/deploy/config/models.json) before running the script.

### Step 2: Upload Documents

Uploads files from `data/documents/` to blob storage. Supports: pdf, doc, docx, txt, md, rtf, csv, json, xml, html. Update `data/documents/` with your desired documents first.

```powershell
.\upload_documents.ps1
```

### Step 3: Deploy Function App Code

Deploys the security groups function to Azure Functions.

```powershell
cd ../functions
.\deploy.ps1
```

### Step 4: Create Search Index

Creates the search index with vector search and semantic ranking configuration.

```powershell
cd ../ai_search
python index.py
```

### Step 5: Create Indexer

Creates the skillset (chunking, embeddings, security groups), datasource, and indexer. Starts processing documents.

```powershell
python indexer.py
```

### Step 6: Run the Application

```powershell
cd ../../
pip install -r requirements.txt
uvicorn app.backend_server:app --reload
# In another terminal:
streamlit run app/streamlit_app.py
```

Open http://localhost:8501

---

## Quick Reference

| Step | Script | Location |
|------|--------|----------|
| 1 | `deploy_infra.ps1` | `infrastructure/deploy/` |
| 2 | `upload_documents.ps1` | `infrastructure/deploy/` |
| 3 | `deploy.ps1` | `infrastructure/functions/` |
| 4 | `index.py` | `infrastructure/ai_search/` |
| 5 | `indexer.py` | `infrastructure/ai_search/` |

---

## Resources Created

`deploy_infra.ps1` creates the following Azure resources:

| Resource | Naming | Purpose |
|----------|--------|---------|
| Resource Group | `rg-{prefix}` | Container for all resources |
| AI Services | `ai-{prefix}` | GPT, Embeddings, Content Safety |
| AI Search | `srch-{prefix}` | Vector search with semantic ranking |
| Storage Account | `st{prefix}` | Document storage |
| Function App | `func-{prefix}` | Document-level security groups lookup |
| App Insights | `appi-{prefix}` | Logging and monitoring |

All resources are configured with Managed Identity and RBAC permissions. See [README_permissions.md](README_permissions.md) for details.

---

## Configuration

The deployment script outputs a `.env` file with all required configuration. Key settings:

```env
AZURE_FOUNDRY_ENDPOINT=https://ai-{prefix}.services.ai.azure.com
AZURE_SEARCH_SERVICE_ENDPOINT=https://srch-{prefix}.search.windows.net
BLOB_ACCOUNT_URL=https://st{prefix}.blob.core.windows.net
```

See [.env.example](../.env.example) for all available options.

---

## Docker (Optional)
> NOTE: Needs additional configuration on the permissions side when hosting on Azure.

Build and run as a container:

```bash
docker build -f app/dockerfile -t rag-accelerator .
docker run -p 8501:8501 -p 8000:8000 rag-accelerator
```

For Azure deployments (Container Apps, AKS), enable Managed Identity - no credentials needed.
