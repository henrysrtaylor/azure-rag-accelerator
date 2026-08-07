# Overall Application Flow

This document describes the end-to-end flow of the RAG solution from user input to response.

---

## High-Level Architecture

```
┌─────────────────┐     ┌─────────────────┐     ┌─────────────────┐
│   User Input    │────▶│   Application   │────▶│   RAG Engine    │
│ (Web, CLI, API) │     │     Layer       │     │   (raglib)      │
└─────────────────┘     └─────────────────┘     └─────────────────┘
                                                        │
                        ┌───────────────────────────────┼───────────────────────────┐
                        │                               │                           │
                        ▼                               ▼                           │
                ┌───────────────┐              ┌───────────────┐                    │
                │  Azure AI     │              │  Azure AI     │                    │
                │  Search       │              │  Foundry      │                    │
                │               │              │  (LLM, Safety)│                    │
                └───────────────┘              └───────────────┘                    │
```

---

## Application Entry Points

### 1. Streamlit Web UI (`streamlit_app.py`) - Recommended
- Modern web-based chat interface
- User authenticates via browser (MSAL)
- Configurable toggles for auth, guardrails, references, suggested questions
- Displays response with expandable citations and suggestions

### 2. REST API (`backend_server.py`)
- FastAPI server exposing `/chat` endpoint
- Receives JSON request with chat history and options
- Security groups passed directly in request body
- Returns structured JSON response

### 3. CLI Application (`cli_app.py`) - Legacy
- Interactive terminal-based chat
- User authenticates via browser (MSAL)
- Security groups extracted from JWT token automatically
- Displays response with citations and suggested questions

### 4. Evaluation Script (`evaluation_script.py`)
- Batch evaluation against test datasets
- Runs queries without DLS (full access mode)
- Measures retrieval and generation quality
- Outputs metrics to CSV

---

## Request Flow

### Step 1: Authentication (Web UI and CLI)
User logs in via Microsoft Entra ID browser flow. The application extracts security group GUIDs from the JWT token's `groups` claim. These groups determine which documents the user can access.

### Step 2: User Guardrail Checks
Before processing, the user's message is checked for:
- Harmful content (hate, violence, sexual, self-harm)
- Prompt injection / jailbreak attempts
- Off-topic queries (optional LLM check)

If any check fails, a static response is returned and processing stops.

### Step 3: Security Filter Construction
User's security groups are converted to an OData filter:
```
security_groups/any(g: search.in(g, 'group1-guid,group2-guid'))
```
This filter restricts document retrieval to authorized content only.

### Step 4: Query Refinement (Optional)
The user's latest message is sent to an LLM along with conversation history. The LLM generates a refined, standalone query that better captures intent for retrieval.

### Step 5: Document Retrieval
Hybrid search is performed against Azure AI Search:
- **Vector search**: Semantic similarity using embeddings
- **Keyword search**: Full-text matching
- **Semantic ranking**: AI-powered relevance reranking
- **DLS filter**: Security groups applied to all results

Top K documents are returned (configurable, default 3).

### Step 6: Context Preparation
Retrieved documents are formatted with citation placeholders:
```
PlaceholderTitleCitation_1: [document content]
PlaceholderTitleCitation_2: [document content]
```
This allows the LLM to reference sources in its response.

### Step 7: LLM Response Generation
The system prompt, formatted documents, and conversation history are sent to Azure AI Foundry. The LLM generates a response using the provided context, including citation placeholders where appropriate.

### Step 8: Model Guardrail Checks
The LLM's response is checked for harmful content using the same content safety checks as user input. If flagged, a safe static response replaces the generated content.

### Step 9: Suggested Questions (Optional)
The conversation history and retrieved documents are sent to an LLM to generate follow-up questions. Questions are parsed and returned with unique IDs.

### Step 10: Citation Processing
Citation placeholders in the response are replaced with numbered references:
- `PlaceholderTitleCitation_1` → `[1]`
- A reference map is created: `[{id: 1, text: "Document Title"}]`

### Step 11: Response Assembly
The final response includes:
- **assistant_message**: The answer text with numbered citations
- **references**: List of cited documents with IDs
- **suggested_questions**: Follow-up questions (if enabled)

### Step 12: Unexpected Failures
The FastAPI `/chat` endpoint is the error boundary. It prints the exception traceback to the server console and returns the standard failure response so clients receive the same response shape as other chat outcomes.

---

## Indexing Flow

Documents must be indexed before they can be searched. The solution uses the Azure AI Search **pull method** (indexer-based):

```
ADLS Gen2 → Indexer → Skills Pipeline → Search Index
```

1. Indexer monitors ADLS Gen2 for new and updated documents
2. Skills extract text, chunk content, generate embeddings
3. WebApiSkill calls Azure Function for security groups
4. Chunks with embeddings and security groups stored in index

---

## Data Flow Diagram

```
User Query
    │
    ▼
┌─────────────────────────────────────────────────────────┐
│                    APPLICATION LAYER                     │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │   backend   │ OR │ application │    │ evaluation  │  │
│  │  _server.py │    │ _script.py  │    │ _script.py  │  │
│  └──────┬──────┘    └──────┬──────┘    └─────────────┘  │
│         │                  │                             │
│         └────────┬─────────┘                             │
│                  │                                       │
│                  ▼                                       │
│  ┌───────────────────────────────────────────────────┐  │
│  │              SECURITY FILTER                       │  │
│  │    permissions.py → build_security_filter()       │  │
│  └───────────────────────────────────────────────────┘  │
└─────────────────────────────────────────────────────────┘
                   │
                   ▼
┌─────────────────────────────────────────────────────────┐
│                      RAG ENGINE                          │
│                                                          │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ guardrails  │───▶│   query_    │───▶│    rag_     │  │
│  │   .py       │    │ refinement  │    │ functions   │  │
│  │ (user check)│    │    .py      │    │    .py      │  │
│  └─────────────┘    └─────────────┘    │ (retrieve)  │  │
│                                         └──────┬──────┘  │
│                                                │         │
│                                                ▼         │
│  ┌─────────────────────────────────────────────────────┐│
│  │                  AZURE AI SEARCH                    ││
│  │  Vector + Keyword + Semantic + DLS Filter           ││
│  └─────────────────────────────────────────────────────┘│
│                          │                               │
│                          ▼                               │
│  ┌─────────────┐    ┌─────────────┐    ┌─────────────┐  │
│  │ citations   │───▶│    rag_     │───▶│ guardrails  │  │
│  │    .py      │    │ functions   │    │    .py      │  │
│  │ (format)    │    │    .py      │    │(model check)│  │
│  │             │    │ (LLM call)  │    │             │  │
│  └─────────────┘    └─────────────┘    └─────────────┘  │
│                                                │         │
│                                                ▼         │
│  ┌─────────────┐    ┌─────────────┐                     │
│  │ suggested_  │    │ citations   │  (parallel post-    │
│  │ questions   │    │    .py      │   processing)       │
│  │    .py      │    │ (finalize)  │                     │
│  └─────────────┘    └─────────────┘                     │
└─────────────────────────────────────────────────────────┘
                   │
                   ▼
            Final Response
```

---

## Key Decision Points

| Stage | Condition | Outcome |
|-------|-----------|---------|
| User Guardrails | Content flagged | Return static error response |
| Security Filter | No groups provided | Full access (evaluation mode) |
| Security Filter | Empty groups list | Deny all access |
| Query Refinement | Disabled | Use raw user query |
| Model Guardrails | Content flagged | Return safe static response |
| Suggested Questions | Disabled | Omit from response |

---

## Supporting Systems

### Prompts (`raglib/prompts/`)
Markdown templates loaded via `markdown_loader.py`. Separates prompt content from code for easy editing.

### Logging (`log.py`)
Standard Python logging configuration. Executable processes initialize `configure_logging()` for timestamped logs sent to stdout; backend, permissions, index, indexer, and evaluation modules emit the actual log messages. The Azure Function uses standard Python logging without importing the application logging module, allowing the Azure Functions host to capture its logs directly.

### Environment Setup (`config.py`)
Centralized Azure client initialization using `DefaultAzureCredential`. Generates consistent naming for indexes and indexers based on project configuration.
