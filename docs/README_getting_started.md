# Getting Started

The deployment scripts use Windows PowerShell. You can install and run the Python application on Windows, macOS, or Linux, but infrastructure deployment requires [PowerShell](https://learn.microsoft.com/powershell/scripting/install/installing-powershell) and the Azure CLI.

## 1. Prerequisites

You need:

- An Azure subscription with the Owner or Contributor role required to create resources and assign RBAC roles
- [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli)
- [Python 3.10 or later](https://www.python.org/downloads/)
- [`uv`](https://docs.astral.sh/uv/getting-started/installation/)

Install `uv` on Windows:

```powershell
powershell -ExecutionPolicy ByPass -c "irm https://astral.sh/uv/install.ps1 | iex"
```

Install `uv` on macOS or Linux:

```bash
curl -LsSf https://astral.sh/uv/install.sh | sh
```

## 2. Clone the Repository

```bash
git clone "https://github.com/henrysrtaylor/azure-rag-accelerator.git"
cd azure-rag-accelerator
```

## 3. Install Dependencies

From the project root, install the runtime and development dependencies declared in `pyproject.toml`. This also creates `.venv` automatically:

```bash
uv sync
```

## 4. Activate the Virtual Environment (Optional)

Activation is not required when commands are prefixed with `uv run`.

Windows PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

macOS or Linux:

```bash
source .venv/bin/activate
```

## 5. Sign In to Azure

The application and deployment scripts use your Azure identity:

```powershell
az login
```

> **Note:** All steps below can be skipped, run manually, or edited to suit your preferences. The scripts are provided as a starting point - feel free to modify resource names, locations, RBAC assignments, or deploy individual components separately. See the other documentation files in `docs/` for guidance on customization.

---

## 6. Deploy and Configure Azure Resources

### 6.1. Deploy Infrastructure

Creates all Azure resources (Search, AI Services, ADLS Gen2 Storage, Function App), assigns RBAC permissions, configures authentication, deploys models, and outputs `.env` file.

```powershell
cd infrastructure/deploy
.\deploy_infra.ps1
```

The script will prompt for:
- `Subscription ID` - Your Azure subscription (script lists available subscriptions)
- `Prefix` - Name prefix for all resources (lowercase, no special characters)
- `Location` - Azure region (e.g., "westeurope", "eastus", "uksouth")

> **Tip:** To change the deployed models, edit [infrastructure/deploy/config/models.json](../infrastructure/deploy/config/models.json) before running the script.

### 6.2. Upload Documents

Uploads files from `data/documents/` to the ADLS Gen2 `documents` filesystem. Supports: pdf, doc, docx, txt, md, rtf, csv, json, xml, html. Update `data/documents/` with your desired documents first.

```powershell
.\upload_documents.ps1
```

### 6.3. Deploy Function App Code

> **DLS setup:** If you will use document-level security, create or identify the required Microsoft Entra security groups, then replace the placeholder values in [document_security_groups.json](../infrastructure/functions/document_security_groups.json) with their group **object IDs** before deploying the function. Users must belong to a matching group to retrieve the document. See [README_permissions.md](README_permissions.md) for Entra and token configuration.

Deploys the security groups function to Azure Functions.

```powershell
cd ../functions
.\deploy.ps1
```

### 6.4. Create Search Index

Creates the search index with vector search and semantic ranking configuration.

```powershell
cd ../ai_search
python index.py
```

### 6.5. Create Indexer

Creates the skillset (chunking, embeddings, security groups), datasource, and indexer. Starts processing documents.

```powershell
python indexer.py
```

## 7. Run the Application

```powershell
cd ../../
uv run uvicorn app.backend:app --reload
```

In another terminal, from the project root:

```powershell
uv run streamlit run app/streamlit_app.py
```

Open http://localhost:8501

The backend, Streamlit client, CLI client, index setup, indexer setup, and evaluation script initialize standard Python logging to stdout. This produces consistent timestamped application logs while suppressing verbose Azure SDK request logs. The Azure Function does not run this bootstrap; Azure Functions captures its standard Python logging directly.

## 8. Run Quality Checks

Run the linter and apply safe fixes:

```bash
uv run ruff check . --fix
```

Verify formatting:

```bash
uv run ruff format --check .
```

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
| Application logs | stdout / Azure host logs | Runtime logging and diagnostics |

All resources are configured with Managed Identity and RBAC permissions. See [README_permissions.md](README_permissions.md) for details.

---

## Configuration

The deployment script outputs a `.env` file with Azure resource and authentication configuration. RAG behavior and model deployment names are defined in `raglib/config.py`. Application model calls use the OpenAI SDK with the Foundry `/openai/v1/` endpoint and Entra ID authentication.

Key environment settings:

```env
AZURE_FOUNDRY_ENDPOINT=https://ai-{prefix}.services.ai.azure.com
AZURE_SEARCH_SERVICE_ENDPOINT=https://srch-{prefix}.search.windows.net
STORAGE_DFS_ACCOUNT_URL=https://st{prefix}.dfs.core.windows.net
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
