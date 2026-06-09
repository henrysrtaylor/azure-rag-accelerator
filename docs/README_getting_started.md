# Getting Started

This guide covers infrastructure setup and application deployment.

## Deployment Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 1: Run CLI Script                                                      │
│                                                                              │
│  .\deploy-infrastructure.ps1 -Prefix "myrag" -Location "uksouth" -Sub "..."│
│                                                                              │
│  Parameters:                                                                 │
│    • Prefix       - Name prefix for all resources (e.g., "myrag")           │
│    • Location     - Azure region (e.g., "uksouth", "eastus")                │
│    • SubscriptionId - Your Azure subscription ID                            │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 2: Script Creates Azure Resources                                     │
│                                                                              │
│  ├── myrag-rg            (Resource Group)                                   │
│  ├── myragfoundry        (AI Foundry + GPT, Embeddings, Content Safety)     │
│  ├── myragsearch         (AI Search)                                        │
│  ├── myragstorage        (Blob Storage + containers)                        │
│  ├── myrag-func          (Function App for DLS)                             │
│  ├── myrag-insights      (Application Insights)                             │
│  └── Managed Identities + RBAC permissions between resources                │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 3: Script Outputs .env Configuration                                  │
│                                                                              │
│  Writes to .env (or prints to console):                                     │
│                                                                              │
│    AZURE_FOUNDRY_ENDPOINT=https://myragfoundry.openai.azure.com/            │
│    AZURE_SEARCH_SERVICE_ENDPOINT=https://myragsearch.search.windows.net     │
│    BLOB_ACCOUNT_URL=https://myragstorage.blob.core.windows.net              │
│    LOGGING_CONNECTION_STRING=InstrumentationKey=...                         │
│    ...                                                                       │
└─────────────────────────────────────────────────────────────────────────────┘
                                   │
                                   ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│  STEP 4: Manual Steps (see docs)                                            │
│                                                                              │
│  ├── Create App Registrations in Entra ID (User Auth, Function Auth)       │
│  ├── Configure Function App authentication                                  │
│  ├── Create Security Groups + update document_security_groups.json         │
│  ├── Deploy Function App code: func azure functionapp publish              │
│  └── Run index/indexer: python infrastructure/ai_search/index.py           │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## 1. Infrastructure Setup

Infrastructure setup will deploy the following Azure resources in a fresh resource group with Managed Identity enabled between them:
- Azure AI Search
- Azure AI Foundry (LLM, Embeddings, Content Safety)
- Azure Blob Storage
- Azure Function App (for DLS)
- Application Insights

See [README_permissions.md](README_permissions.md) for required permissions and access configuration.

**Options:**
- **CLI Scripts:** Run the Azure CLI scripts in `infrastructure/deploy/` - *coming soon*
- **Manual:** If comfortable, provision resources and setup Managed Identities yourself following the permissions guide.

---

## 2. Application Setup

### 2.1 Clone the Repository

```bash
git clone "https://github.com/henrysrtaylor/azure-rag-accelerator.git"
cd azure-rag-accelerator
```

### 2.2 Set Up Virtual Environment

Windows:
```powershell
python -m venv .venv
.\.venv\Scripts\activate
```

macOS/Linux:
```bash
python3 -m venv .venv
source .venv/bin/activate
```

### 2.3 Install Dependencies

```bash
pip install -r requirements.txt
```

### 2.4 Configure Environment

Copy `.env.example` to `.env` and fill in your Azure resource details:

```env
AZURE_SEARCH_SERVICE_ENDPOINT=https://<search-service>.search.windows.net
AZURE_FOUNDRY_ENDPOINT=https://<foundry>.services.ai.azure.com
```

See the main [README.md](../README.md#configuration-options) for all available configuration options.

---

## 3. Run the Application

### Option A: Streamlit + Backend (recommended)

Run services separately for development with hot-reload.

**Prerequisite:** You must be logged into Azure CLI for `DefaultAzureCredential` to work:

```bash
az login
```

> **Note:** Your Azure account needs appropriate permissions to access Search, AI Foundry, and other resources. See [README_permissions.md](README_permissions.md) for required access.

Then start the services:

```bash
# Terminal 1 - Start backend API
uvicorn app.backend_server:app --reload

# Terminal 2 - Start Streamlit frontend
streamlit run app/streamlit_app.py
```

Open http://localhost:8501 in your browser.

### Option B: CLI Client

Terminal-based interface (useful for testing/automation):

```bash
# Start backend API first
uvicorn app.backend_server:app --reload

# In another terminal
python -m app.cli_app
```

---

## 4. Docker (Production Deployment - Optional)

We have provided a [dockerfile](../app/dockerfile) to use as reference if you wish to build a container.

**Build:**

```bash
docker build -f app/dockerfile -t rag-accelerator .
docker run -p 8501:8501 -p 8000:8000 rag-accelerator
```

**Authentication options:**

| Deployment | Auth Method |
|------------|-------------|
| Local Docker | Service Principal credentials in `.env` (see below) |
| Azure Container Apps / AKS | Enable Managed Identity - Azure handles auth automatically |

**For local Docker testing**, create a Service Principal with the same permissions as described in [README_permissions.md](README_permissions.md), and add to `.env`:

```env
AZURE_CLIENT_ID=<service-principal-app-id>
AZURE_CLIENT_SECRET=<service-principal-secret>
AZURE_TENANT_ID=<your-tenant-id>
```

Then rebuild the image to include the updated `.env`.

**For Azure deployments**, enable Managed Identity on your Container App or AKS cluster and grant it access to your Azure resources - no credentials needed in the image.

> **Note:** The Service Principal or Managed Identity needs appropriate permissions to access Azure resources. See [README_permissions.md](README_permissions.md) for required access.
