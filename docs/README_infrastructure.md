# Azure Infrastructure Requirements

This document lists all Azure resources required to run the RAG solution.

---

## Required Azure Resources

### Core Services

| Resource | Azure Service | Purpose |
|----------|---------------|---------|
| **AI Search** | Azure AI Search (Standard tier+) | Vector, keyword, and semantic search with indexer support |
| **AI Foundry** | Azure AI Foundry | LLM, embeddings, and content safety (all-in-one) |
| **Document Storage** | Azure Data Lake Storage Gen2 | Source documents for indexing |

> **Note**: Azure AI Foundry now includes Content Safety capabilities (text moderation, prompt injection detection). No separate Cognitive Services or Content Safety resource is needed.

### Supporting Services

| Resource | Azure Service | Purpose |
|----------|---------------|---------|
| **Security Groups Function** | Azure Functions | DLS custom skill for indexer (WebApiSkill) |
| **Logging & Monitoring** | Standard Python logging | Terminal, container, and Azure host log collection |
| **User Authentication** | Microsoft Entra ID | User login and security group membership |

### Optional Services

| Resource | Azure Service | Purpose |
|----------|---------------|---------|
| **Security Groups Store** | Azure Cosmos DB | Production document-to-groups mapping (replaces JSON file) |
| **Container Hosting** | Azure Container Apps / AKS | API hosting for production |

---

## Resource Configuration

### Azure AI Search

**Tier**: Standard (S1) or higher recommended
- Basic tier does not support semantic search
- Free tier has limited storage and features

**Required Features**:
- Semantic ranker enabled
- Vector search enabled
- Indexer with skillset support

**Index Schema Requirements**:
- Vector field: `Collection(Edm.Single)` with HNSW algorithm
- Security groups field: `Collection(Edm.String)` with `filterable=true`
- Content text field: Searchable with semantic configuration

---

### Azure AI Foundry

Azure AI Foundry is the unified platform providing all AI capabilities:

**Required Model Deployments**:

| Model Type | Example Models | Purpose |
|------------|----------------|---------|
| Large Chat | GPT-4, GPT-4o, o1 | Main RAG responses, verbalization |
| Small Chat | GPT-4o-mini | Evaluation, query refinement |
| Embedding | text-embedding-3-small/large | Vector embeddings |

**Built-in Content Safety** (no separate resource needed):
- Text analysis for hate, violence, sexual, self-harm categories
- Prompt injection / jailbreak detection

**Application inference API**: OpenAI v1 at `/openai/v1/`. The application uses implicit versioning and does not pass a dated `api-version`. Chat Completions supports cross-provider Foundry deployments that implement the OpenAI v1 schema.

`AZURE_FOUNDRY_API_VERSION` remains available for infrastructure components such as Azure AI Search skills that still require a dated API version.

---

### Azure Data Lake Storage Gen2

**Required Filesystems**:

| Filesystem | Purpose |
|-----------|---------|
| `documents` | Source PDF/document files |
| `evaluation` | Test datasets (JSONL format) - optional |

**Configuration**:
- Hierarchical namespace enabled
- Managed Identity access for Search Service

---

### Azure Functions

**Purpose**: Custom WebApiSkill for DLS security group lookup

**Configuration**:
- Runtime: Python 3.11
- Plan: Consumption or Premium
- System-Assigned Managed Identity enabled
- Entra ID authentication configured

**Required Settings**:
- Authentication restricted to Search Service Managed Identity
- 30-second timeout for indexer calls

---

### Standard Python Logging

**Purpose**: Timestamped application logging to stdout

**Required for**:
- Backend request and failure logging
- Index and indexer progress logging
- Evaluation completion logging

Executable application and infrastructure scripts call `configure_logging()` from `raglib/log.py`. The Azure Function relies on the Azure Functions host to collect its standard Python logs and does not import the application logging module.

---

### Microsoft Entra ID

**Required App Registrations**:

| App Registration | Purpose |
|------------------|---------|
| **User Auth App** | MSAL authentication for CLI/web app - extracts security groups from JWT |
| **Function Auth App** | API authentication restricting Function App to Search Service MI only |

**Security Groups**: Create security groups for document access control. Users must be assigned to groups to access corresponding documents.

---

## Configuration

RAG behavior, model deployments, embedding dimensions, and guardrail thresholds are defined by the `AppConfig` dataclass and `app_config` instance in `raglib/config.py`. Azure resource and authentication values are managed through the `.env` file:

```bash
# Azure AI Foundry
AZURE_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/
AZURE_FOUNDRY_API_VERSION=2025-01-01-preview  # Search skillset calls only

# Azure AI Search
AZURE_SEARCH_SERVICE_ENDPOINT=https://<service>.search.windows.net/
AZURE_SEARCH_API_VERSION=2024-07-01
AZURE_SEARCH_PROJECT_PREFIX=myproject       # Index naming prefix

# ADLS Gen2 Storage
STORAGE_ACCOUNT_NAME=<account>
STORAGE_DFS_ACCOUNT_URL=https://<account>.dfs.core.windows.net/
STORAGE_CONNECTION_STRING=ResourceId=/subscriptions/<subscription-id>/resourceGroups/<resource-group>/providers/Microsoft.Storage/storageAccounts/<account>
DOCUMENTS_FILESYSTEM_NAME=documents
EVALUATION_FILESYSTEM_NAME=evaluation
EVALUATION_DOCUMENT_NAME=example_golden_dataset.json

# Content Safety (via AI Foundry endpoint)
AZURE_CONTENT_MODERATOR_ENDPOINT=https://<resource>.cognitiveservices.azure.com/

# Authentication - User Auth App
AZURE_TENANT_ID=<directory-id>
AZURE_CLIENT_ID=<user-auth-app-client-id>
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=<resource-group>

# Function App (DLS) - Function Auth App
AZURE_FUNCTION_SECURITY_GROUPS_URL=https://<func>.azurewebsites.net/api/get_security_groups
AZURE_FUNCTION_AUTH_RESOURCE_ID=api://<function-auth-app-client-id>
```

---

## Resource Diagram

```
┌─────────────────────────────────────────────────────────────────────┐
│                        AZURE SUBSCRIPTION                            │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     RESOURCE GROUP                              │ │
│  │                                                                 │ │
│  │  ┌─────────────────┐     ┌─────────────────┐                   │ │
│  │  │  Azure AI       │     │  Azure AI       │                   │ │
│  │  │  Foundry        │     │  Search         │                   │ │
│  │  │                 │     │                 │                   │ │
│  │  │  - GPT-4o       │     │  - Index        │                   │ │
│  │  │  - GPT-4o-mini  │     │  - Indexer      │                   │ │
│  │  │  - Embeddings   │     │  - Skillset     │                   │ │
│  │  │  - Content      │     │                 │                   │ │
│  │  │    Safety       │     │                 │                   │ │
│  │  └─────────────────┘     └────────┬────────┘                   │ │
│  │                                   │                             │ │
│  │                                   │ WebApiSkill                 │ │
│  │                                   ▼                             │ │
│  │  ┌─────────────────┐     ┌─────────────────┐                   │ │
│  │  │  ADLS Gen2      │     │  Azure          │                   │ │
│  │  │                 │     │  Functions      │                   │ │
│  │  │  - documents    │────▶│                 │                   │ │
│  │  │  - evaluation   │     │  Security       │                   │ │
│  │  │                 │     │  Groups Lookup  │                   │ │
│  │  └─────────────────┘     └─────────────────┘                   │ │
│  │                                                                 │ │
│  │  ┌─────────────────┐                                           │ │
│  │  │  Application    │                                           │ │
│  │  │  Insights       │                                           │ │
│  │  │                 │                                           │ │
│  │  │  Logging &      │                                           │ │
│  │  │  Telemetry      │                                           │ │
│  │  └─────────────────┘                                           │ │
│  │                                                                 │ │
│  └────────────────────────────────────────────────────────────────┘ │
│                                                                      │
│  ┌────────────────────────────────────────────────────────────────┐ │
│  │                     MICROSOFT ENTRA ID                          │ │
│  │                                                                 │ │
│  │  ┌─────────────────┐     ┌─────────────────┐                   │ │
│  │  │  App Reg:       │     │  App Reg:       │                   │ │
│  │  │  User Auth      │     │  Function Auth  │                   │ │
│  │  │                 │     │                 │                   │ │
│  │  │  MSAL Login     │     │  API://...      │                   │ │
│  │  │  Groups Claim   │     │  Search MI Only │                   │ │
│  │  └─────────────────┘     └─────────────────┘                   │ │
│  │                                                                 │ │
│  │  ┌─────────────────────────────────────────────────────┐       │ │
│  │  │              Security Groups                         │       │ │
│  │  │  - group-a, group-b, etc.                           │       │ │
│  │  └─────────────────────────────────────────────────────┘       │ │
│  └────────────────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────────────────┘
```

---

## Deployment Checklist

- [ ] Azure AI Search (Standard tier) created
- [ ] Azure AI Foundry resource with model deployments
- [ ] ADLS Gen2 account with `documents` filesystem
- [ ] Azure Functions app deployed with authentication
- [ ] **User Auth App Registration** - for MSAL login with groups claim
- [ ] **Function Auth App Registration** - restricts to Search Service MI
- [ ] Security groups created and users assigned
- [ ] Managed Identities enabled on all resources
- [ ] RBAC permissions configured (see readme_permissions.md)
- [ ] Environment variables populated in `.env`
