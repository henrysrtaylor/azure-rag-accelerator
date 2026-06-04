# Azure Infrastructure Requirements

This document lists all Azure resources required to run the RAG solution.

---

## Required Azure Resources

### Core Services

| Resource | Azure Service | Purpose |
|----------|---------------|---------|
| **AI Search** | Azure AI Search (Standard tier+) | Vector, keyword, and semantic search with indexer support |
| **AI Foundry** | Azure AI Foundry | LLM, embeddings, and content safety (all-in-one) |
| **Document Storage** | Azure Blob Storage | Source documents for indexing |

> **Note**: Azure AI Foundry now includes Content Safety capabilities (text moderation, prompt injection detection). No separate Cognitive Services or Content Safety resource is needed.

### Supporting Services

| Resource | Azure Service | Purpose |
|----------|---------------|---------|
| **Security Groups Function** | Azure Functions | DLS custom skill for indexer (WebApiSkill) |
| **Logging & Monitoring** | Azure Application Insights | Telemetry, custom events, and debugging |
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

**API Version**: `2024-08-01-preview` or later (for reasoning models)

---

### Azure Blob Storage

**Required Containers**:

| Container | Purpose |
|-----------|---------|
| `documents` | Source PDF/document files |
| `evaluation` | Test datasets (JSONL format) - optional |

**Configuration**:
- Soft delete enabled (for indexer deletion detection)
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

### Azure Application Insights

**Purpose**: Structured logging and telemetry

**Required for**:
- Custom event logging via `log_message()`
- Performance monitoring
- Error tracking

**Connection**: Full connection string with InstrumentationKey

---

### Microsoft Entra ID

**Required App Registrations**:

| App Registration | Purpose |
|------------------|---------|
| **User Auth App** | MSAL authentication for CLI/web app - extracts security groups from JWT |
| **Function Auth App** | API authentication restricting Function App to Search Service MI only |

**Security Groups**: Create security groups for document access control. Users must be assigned to groups to access corresponding documents.

---

## Environment Variables

All configuration is managed via environment variables (`.env` file):

```bash
# Azure AI Foundry
AZURE_FOUNDRY_ENDPOINT=https://<resource>.services.ai.azure.com/
AZURE_FOUNDRY_API_VERSION=2024-08-01-preview
AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL=gpt-4o
AZURE_FOUNDRY_SMALL_DEPLOYED_MODEL=gpt-4o-mini
AZURE_FOUNDRY_EMBEDDING_DEPLOYED_MODEL=text-embedding-3-small
AZURE_FOUNDRY_EMBEDDING_DIMENSIONS=512
AZURE_FOUNDRY_REASONING_EFFORT=low          # For o-series models

# Azure AI Search
AZURE_SEARCH_SERVICE_ENDPOINT=https://<service>.search.windows.net/
AZURE_SEARCH_API_VERSION=2024-07-01
AZURE_SEARCH_PROJECT_PREFIX=myproject       # Index naming prefix

# Blob Storage
BLOB_ACCOUNT_NAME=<account>
BLOB_ACCOUNT_URL=https://<account>.blob.core.windows.net/
BLOB_CONNECTION_STRING=DefaultEndpointsProtocol=...
BLOB_CONTAINER_NAME_DOCUMENTS=documents
BLOB_CONTAINER_NAME_EVAL=evaluation

# Content Safety (via AI Foundry endpoint)
AZURE_CONTENT_MODERATOR_ENDPOINT=https://<resource>.cognitiveservices.azure.com/

# Logging
LOGGING_CONNECTION_STRING=InstrumentationKey=<key>;IngestionEndpoint=...

# Authentication - User Auth App
AZURE_TENANT_ID=<directory-id>
AZURE_CLIENT_ID=<user-auth-app-client-id>
AZURE_SUBSCRIPTION_ID=<subscription-id>
AZURE_RESOURCE_GROUP=<resource-group>

# Function App (DLS) - Function Auth App
AZURE_FUNCTION_SECURITY_GROUPS_URL=https://<func>.azurewebsites.net/api/get_security_groups
AZURE_FUNCTION_AUTH_RESOURCE_ID=api://<function-auth-app-client-id>

# RAG Parameters
PARAMETER_CHUNK_SIZE=2500
PARAMETER_CHUNK_OVERLAP=500
PARAMETER_NUMBER_DOC_RETRIEVE=3
PARAMETER_SUGGESTED_QUESTIONS=3

# Content Safety Thresholds (0-7)
PARAMETER_HATE_GUARDRAIL_THRESHOLD=4
PARAMETER_SELFHARM_GUARDRAIL_THRESHOLD=4
PARAMETER_SEXUAL_GUARDRAIL_THRESHOLD=4
PARAMETER_VIOLENCE_GUARDRAIL_THRESHOLD=4
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
│  │  │  Blob Storage   │     │  Azure          │                   │ │
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
- [ ] Blob Storage account with `documents` container
- [ ] Application Insights workspace created
- [ ] Azure Functions app deployed with authentication
- [ ] **User Auth App Registration** - for MSAL login with groups claim
- [ ] **Function Auth App Registration** - restricts to Search Service MI
- [ ] Security groups created and users assigned
- [ ] Managed Identities enabled on all resources
- [ ] RBAC permissions configured (see readme_permissions.md)
- [ ] Environment variables populated in `.env`
