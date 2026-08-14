# Permissions & Document-Level Security

This document details all permissions required between Azure resources and the complete Document-Level Security (DLS) implementation.

---

## Overview

The solution uses three authentication mechanisms:
1. **Managed Identity** - Service-to-service authentication
2. **Microsoft Entra ID** - User authentication (MSAL) via User Auth App
3. **DefaultAzureCredential** - SDK authentication (auto-detects environment)

---

## App Registrations Required

Two separate app registrations are needed:

| App Registration | Purpose | Used By |
|------------------|---------|---------|
| **User Auth App** | MSAL browser login, extracts security groups from JWT | CLI app, web app |
| **Function Auth App** | Restricts Function App to Search Service MI only | Indexer WebApiSkill |

---

## Managed Identity Configuration

### Resources Requiring Managed Identity

| Resource | Identity Type | Purpose |
|----------|---------------|---------|
| Azure AI Search | System-Assigned | Call Function App WebApiSkill |
| Azure Functions | System-Assigned | Access Blob/Cosmos for security groups |
| Container/App Service | System-Assigned | Runtime SDK authentication |

### Enabling System-Assigned Managed Identity

For each resource in Azure Portal:
1. Go to resource → Identity
2. System assigned → Status: **On**
3. Save and note the **Object (Principal) ID**

---

## RBAC Permissions Between Resources

### Azure AI Search → Other Resources

| Target Resource | Role | Purpose |
|-----------------|------|---------|
| ADLS Gen2 | **Storage Blob Data Reader** | Read source documents for indexing |
| Azure AI Foundry | **Cognitive Services OpenAI User** | Generate embeddings in skillset |
| Azure Functions | **Allowed via Entra ID auth** | Call WebApiSkill for security groups |

### Azure Functions → Other Resources

| Target Resource | Role | Purpose |
|-----------------|------|---------|
| ADLS Gen2 | **Storage Blob Data Reader** | Read security groups JSON (if using storage) |
| Cosmos DB | **Cosmos DB Built-in Data Reader** | Read security groups (production) |

### Application/Container → Other Resources

| Target Resource | Role | Purpose |
|-----------------|------|---------|
| Azure AI Search | **Search Index Data Reader** | Query index |
| Azure AI Foundry | **Cognitive Services OpenAI User** | LLM completions, embeddings, content safety |
| ADLS Gen2 | **Storage Blob Data Reader** | Read evaluation datasets |

### Indexer Scripts → Other Resources

| Target Resource | Role | Purpose |
|-----------------|------|---------|
| Azure AI Search | **Search Service Contributor** | Create/modify index, indexer, skillset |

---

## User Auth App Registration (for MSAL Login)

This app registration enables users to login via browser and receive a JWT with their security groups.

### Step 1: Create App Registration

1. Azure Portal → Entra ID → App registrations → New registration
2. Name: `rag-user-auth` (or similar)
3. Supported account types: Single tenant
4. Redirect URI: Select "Public client/native (mobile & desktop)" → `http://localhost` (for local development; add your app URL for deployed scenarios)
5. Register

### Step 2: Configure API Permissions

1. Go to API permissions → Add permission
2. Microsoft Graph → Delegated permissions
3. Add: `User.Read`
4. Grant admin consent

### Step 3: Enable Groups Claim

1. Go to Token configuration → Add groups claim
2. Select: **Security groups**
3. For ID tokens: Check **Group ID**
4. Save

### Step 4: Note Required Values

- **Application (client) ID**: Use in `AZURE_CLIENT_ID`
- **Directory (tenant) ID**: Use in `AZURE_TENANT_ID`

### Environment Variables

```bash
AZURE_CLIENT_ID=<user-auth-app-client-id>
AZURE_TENANT_ID=<directory-id>
```

---

## Function Auth App Registration (for WebApiSkill)

This app registration restricts the Function App to only accept calls from the Search Service Managed Identity.

### Step 1: Create App Registration

1. Azure Portal → Entra ID → App registrations → New registration
2. Name: `rag-function-auth` (or similar)
3. Supported account types: Single tenant
4. Register

### Step 2: Expose an API

1. Go to "Expose an API"
2. Set Application ID URI: `api://<application-client-id>`

### Step 3: Configure Function App Authentication

1. Azure Portal → Function App → Authentication
2. Add identity provider → Microsoft
3. Configure:
   - **App registration type**: Pick an existing registration
   - **App registration**: Select the Function Auth app
   - **Tenant requirement**: Use default restrictions based on issuer
   - **Client application requirement**: Allow requests only from specific client applications
   - **Allowed client applications**: Add the **Application ID** of the Search Service MI
   - **Identity requirement**: Allow requests only from specific identities
   - **Allowed identities**: Add the **Object ID** of the Search Service MI

> ⚠️ **CRITICAL**: The Search Service MI has TWO different IDs. You must use BOTH correctly:
> - **Application ID** (Client ID) → goes in "Allowed client applications"
> - **Object ID** (Principal ID) → goes in "Allowed identities"
> 
> Azure Portal only shows the Object ID on the Search Service Identity page. You must run the az command below to get the Application ID. Using the wrong ID in either field will cause authentication failures.

### Step 4: Get Search Service MI Application ID

The Search Service has a System-Assigned Managed Identity with:
- **Object ID** (Principal ID): Used in Identity requirements
- **Application ID** (Client ID): Used in Client application requirements

To find the Application ID from Object ID:
```powershell
az ad sp show --id <object-id> --query appId -o tsv
```

### Step 5: Note Required Values

- **Application ID URI**: Use in `AZURE_FUNCTION_AUTH_RESOURCE_ID` (format: `api://<client-id>`)

### Environment Variables

```bash
AZURE_FUNCTION_SECURITY_GROUPS_URL=https://<func-app>.azurewebsites.net/api/get_security_groups
AZURE_FUNCTION_AUTH_RESOURCE_ID=api://<function-auth-app-client-id>
```

### WebApiSkill Configuration

In `2_setup_indexer.py`, the skill is configured with authentication:
```python
skill_security_groups = WebApiSkill(
    name="security-groups-skill",
    uri=os.getenv("AZURE_FUNCTION_SECURITY_GROUPS_URL"),
    auth_resource_id=os.getenv("AZURE_FUNCTION_AUTH_RESOURCE_ID"),  # Enables MI auth
    timeout="PT10S",
    batch_size=1,
    inputs=[
        InputFieldMappingEntry(
            name="document_name", source="/document/metadata_storage_name"
        )
    ],
    outputs=[
        OutputFieldMappingEntry(name="security_groups", target_name="security_groups")
    ],
)
```

---

## Document-Level Security (DLS) Implementation

### Architecture Overview

```
┌─────────────────────────────────────────────────────────────────────┐
│                         INDEXING TIME                                │
│                                                                      │
│  Document.pdf                                                        │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────┐    ┌─────────────────┐    ┌─────────────────────┐  │
│  │   Indexer   │───▶│  WebApiSkill    │───▶│   Azure Function    │  │
│  │             │    │                 │    │                     │  │
│  │ Extract:    │    │ Call with:      │    │ Look up document    │  │
│  │ - text      │    │ document_name   │    │ Return: group GUIDs │  │
│  │ - chunks    │    │                 │    │                     │  │
│  │ - embeddings│    └─────────────────┘    └──────────┬──────────┘  │
│  └─────────────┘                                      │              │
│                                                       ▼              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │                     SEARCH INDEX                                 ││
│  │                                                                  ││
│  │  content_id | content_text | embedding | security_groups        ││
│  │  ─────────────────────────────────────────────────────────      ││
│  │  chunk_001  | "Text..."   | [0.1,...]  | ["group-a", "group-b"]    ││
│  │  chunk_002  | "Azure..."   | [0.2,...]  | ["group-c"]             ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────────────┐
│                         QUERY TIME                                   │
│                                                                      │
│  User logs in via MSAL (User Auth App)                               │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  JWT Token contains:                                             ││
│  │  {                                                               ││
│  │    "groups": ["group-a", "group-d", "group-e"]                        ││
│  │  }                                                               ││
│  └─────────────────────────────────────────────────────────────────┘│
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────┐    ┌─────────────────────────────────────────────┐ │
│  │ permissions │───▶│ OData Filter:                                │ │
│  │    .py      │    │ security_groups/any(g: search.in(g,          │ │
│  │             │    │   'group-a,group-d,group-e'))                      │ │
│  └─────────────┘    └─────────────────────────────────────────────┘ │
│       │                                                              │
│       ▼                                                              │
│  ┌─────────────────────────────────────────────────────────────────┐│
│  │  Search query with filter applied                                ││
│  │  → Only returns chunks where security_groups contains            ││
│  │    at least one of user's groups                                ││
│  └─────────────────────────────────────────────────────────────────┘│
└─────────────────────────────────────────────────────────────────────┘
```

### Security Groups Mapping File

The Function App reads document-to-groups mapping from a JSON file (simple setup). For production, consider using Cosmos DB for scalability.

**Location**: `infrastructure/functions/document_security_groups.json`

```json
{
  "document-a.pdf": [
    "6656ed65-0c70-4356-afad-06e53ad076f2",
    "2d74c252-890b-4760-828a-5091412fa290"
  ],
  "document-b.pdf": [
    "93a36980-8070-48e3-bc85-3f209aeadf40"
  ],
  "document-c.pdf": [
    "a1b2c3d4-e5f6-7890-abcd-ef1234567890"
  ]
}
```

**Important**: Group values must be the **Object IDs (GUIDs)** of Entra ID security groups, not display names.

### Index Field Configuration

The security groups field must be correctly configured:

```python
SearchField(
    name="security_groups",
    type=SearchFieldDataType.Collection(SearchFieldDataType.String),
    filterable=True,  # Required for DLS
    searchable=False,
)
```

### Security Filter Logic

**`build_security_filter()` in `permissions.py`**:

| Input | Output | Use Case |
|-------|--------|----------|
| `["group-a", "group-b"]` | `security_groups/any(g: search.in(g, 'group-a,group-b'))` | Normal user with groups |
| `None` | `None` | Full access (evaluation mode) |
| `[]` | `security_groups/any(g: g eq '__DENY_ALL__')` | Deny all (no groups) |

### Filter Matching Logic

The OData filter uses `any()` which means OR logic:

| Document Groups | User Groups | Match? |
|-----------------|-------------|--------|
| `["group-a"]` | `["group-a"]` | ✅ YES |
| `["group-a", "group-b"]` | `["group-a"]` | ✅ YES |
| `["group-a", "group-b"]` | `["group-c"]` | ❌ NO |
| `["group-a", "group-b"]` | `["group-b", "group-c"]` | ✅ YES |

User needs **at least one** matching group to access the document.

---

## Entra ID Security Group Setup

### Step 1: Create Security Groups

1. Azure Portal → Entra ID → Groups → New group
2. Group type: **Security**
3. Group name: e.g., `group-a`, `group-b`, `all-users`
4. Create group

5. Note the **Object ID** (GUID) - this is used in:
   - `document_security_groups.json`
   - User JWT token `groups` claim

### Step 2: Assign Users to Groups

1. Go to group → Members → Add members
2. Select users
3. Add



---

## User Authentication Flow

### MSAL Configuration

The CLI application uses MSAL for browser-based login:

```python
app = msal.PublicClientApplication(
    client_id=os.getenv("AZURE_CLIENT_ID"),  # User Auth App
    authority=f"https://login.microsoftonline.com/{os.getenv('AZURE_TENANT_ID')}",
)

result = app.acquire_token_interactive(scopes=["User.Read"])
groups = result.get("id_token_claims", {}).get("groups", [])
```

The extracted `groups` list contains GUIDs that are passed to `build_security_filter()`.

---

## Permissions Checklist

### Managed Identity Assignments
- [ ] Search Service MI → Storage Blob Data Reader on ADLS Gen2
- [ ] Search Service MI → Cognitive Services OpenAI User on Azure AI Foundry
- [ ] Function App MI → Storage Blob Data Reader (or Cosmos DB Reader)
- [ ] App/Container MI → Search Index Data Reader
- [ ] App/Container MI → Cognitive Services OpenAI User on Azure AI Foundry

### User Auth App Registration
- [ ] App Registration created with redirect URI `http://localhost`
- [ ] API permission `User.Read` added and consented
- [ ] Token configuration: Groups claim enabled (Security groups, Group ID)
- [ ] `AZURE_CLIENT_ID` and `AZURE_TENANT_ID` set in `.env`

### Function Auth App Registration
- [ ] App Registration created
- [ ] Expose an API configured with Application ID URI (`api://<client-id>`)
- [ ] Function App Authentication enabled with Entra ID
- [ ] Client application restricted to Search Service MI **Application ID**
- [ ] Identity restricted to Search Service MI **Object ID**
- [ ] `AZURE_FUNCTION_AUTH_RESOURCE_ID` set in `.env`

### Entra ID Configuration
- [ ] Security groups created for document access
- [ ] Users assigned to appropriate groups
- [ ] Document-to-group mapping in `document_security_groups.json`

### Index Configuration
- [ ] `security_groups` field is `filterable=True`
- [ ] `security_groups` field type is `Collection(Edm.String)`
- [ ] Indexer includes WebApiSkill for security groups

---

## Troubleshooting

### "Indexer failed to call WebApiSkill"
- **Most common cause**: Using the wrong ID in the wrong field
  - Verify you used **Application ID** (not Object ID) in "Allowed client applications"
  - Verify you used **Object ID** (not Application ID) in "Allowed identities"
  - Run `az ad sp show --id <object-id> --query appId -o tsv` to get the Application ID
- Verify `auth_resource_id` matches the Function Auth App's Application ID URI exactly (format: `api://<client-id>`)
- Check Function App logs (Log Stream) for authentication errors
- Ensure Function App has Authentication enabled (not just authorization)

### "User has no groups in token"
- Verify groups claim is configured in User Auth App Registration
- Verify user is member of at least one security group
- Check if group count exceeds 200 (use Graph API instead)

### "User can access all documents"
- Verify `security_filter` is being passed to `retrieve_documents()`
- Verify `security_groups` field is filterable in index
- Verify documents have security groups populated

### "User cannot access any documents"
- Verify user's groups match at least one document's groups
- Check group GUIDs match exactly (case-sensitive)
- Test with `build_security_filter(None)` for full access to verify setup
