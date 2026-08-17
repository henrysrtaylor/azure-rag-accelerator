# Azure RAG Accelerator

A modular Retrieval-Augmented Generation (RAG) solution built on Azure AI services. Implements document-level security, content moderation guardrails, query refinement, and citation management. Designed as an accelerator to speed up production RAG deployments.

> NOTE: This is an accelerator/reference implementation, not a production-ready product. Its designed for local use, connecting with Azure services. Customize for your specific use case and or production loads.

![RAG Assistant Chat Interface](docs/images/chat_screenshot.png)

## 📋 Core Components
- Entry: Streamlit chat application front-end, CLI, API from backend
- LLM: Azure Foundry for chat completion and query refinement
- Model Agnostic: Uses the stable OpenAI SDK with Microsoft Foundry's v1 API to call supported cross-provider model deployments without code changes.
- Search: Azure AI Search with hybrid (vector + keyword) and semantic ranking
- Embeddings: Azure AI Foundry embeddings for vector search
- Guardrails: Content Safety API for hate/violence/sexual/self-harm detection + jailbreak prevention + on topic detection
- Security: Document-Level Security (DLS) via Entra ID group-based filtering
- Citations: Automatic reference tracking
- Query Enhancement: Conversation-aware query refinement and suggested follow-up questions
- Logging: Standard Python logging to stdout for terminal, container, and Azure host collection
- Evaluation: Custom LLM as as judge, script to locally evaluate solution and record metrics based on `data/evaluation/golden_dataset`
- Infrastructure: Azure CLI deployment scripts
- Data: Load documents into the local directory and send them to Data Lake
- Tests: Mocked unit tests covering core RAG behavior without requiring Azure resources

## 📈 Future Roadmap
- Async I/O — Convert Azure API calls and pipeline execution to async, enabling concurrent request handling.

## 📂 Project Structure

```
azure-rag-accelerator/
├── raglib/                    # Core library
│   ├── azure_ai.py            # Search & LLM functions
│   ├── pipeline.py            # RAG orchestration
│   ├── guardrails.py          # Content safety checks
│   ├── permissions.py         # Document-level security
│   ├── citations.py           # Reference management
│   ├── enhance.py             # Query refinement & suggestions
│   ├── config.py              # Typed app and evaluation settings
│   ├── clients.py             # Azure client factories
│   ├── log.py                 # Logging configuration (stdout)
│   ├── eval.py                # LLM-as-judge evaluation functions
│   └── prompts/               # Agent & evaluation prompt templates
├── app/                       # Application scripts
│   ├── backend.py             # FastAPI REST API
│   ├── streamlit_app.py       # Streamlit web UI
│   └── cli_app.py             # CLI chat client (legacy)
├── evaluation/                # RAG evaluation
│   ├── evaluation_script.py   # Quality metrics runner
│   └── results/               # Timestamped evaluation outputs
├── data/                      # Source documents for indexing and evaluation
├── infrastructure/            # Deployment resources
│   ├── ai_search/             # Index & indexer setup
│   ├── functions/             # Azure Function for DLS
│   └── deploy/                # Azure CLI deployment scripts
├── docs/                      # Documentation
├── .env                       # Environment configuration
├── requirements.txt           # Dependencies
└── pyproject.toml             # Package configuration
```

## ⚙️ Client Feature Flags

These feature flags are owned by each client and sent with every `/chat` request; they are not backend environment settings.

| Option | CLI | Streamlit | Description |
|--------|-----|-----------|-------------|
| Query refinement | `OPTION_QUERY_REFINEMENT` constant | Setup toggle | Rewrite queries using conversation context |
| Guardrail checks | `OPTION_GUARDRAIL_CHECKS` constant | Setup toggle | Content safety, jailbreak, and on-topic checks |
| Suggested questions | `OPTION_SUGGESTED_QUESTIONS` constant | Setup toggle | Generate follow-up question suggestions |
| Document-level security | `OPTION_SECURITY_GROUPS` constant | Authentication toggle | Apply Entra ID group filtering |

The API returns one consistent response shape for normal answers, empty input, guardrail outcomes, and unexpected failures. The backend prints unexpected exception tracebacks to its server console, then returns the standard failure response. Clients display the response and use `save_chat_history` to decide whether to retain the turn.

Tunable values in `raglib/config.py`:

| Parameter | Default | Description |
|-----------|---------|-------------|
| `number_documents_retrieve` | `5` | Number of documents to retrieve |
| `k_nearest_neighbors` | `3` | k for vector search |
| `suggested_questions` | `3` | Number of follow-up suggestions |
| `chunk_size` | `1000` | Document chunk size (indexing) |
| `chunk_overlap` | `100` | Chunk overlap (indexing) |

Content safety thresholds (0-7, higher = more permissive):

| Parameter | Default |
|-----------|---------|
| `hate_guardrail_threshold` | `4` |
| `self_harm_guardrail_threshold` | `4` |
| `sexual_guardrail_threshold` | `4` |
| `violence_guardrail_threshold` | `4` |

## 🚀 Getting Started

See [docs/README_getting_started.md](docs/README_getting_started.md) for full infrastructure and application setup instructions. Or, if comfortable and infrastructure is in place, use the quick start below:

**Quick Start:**

Before starting, [Python 3.10+](https://www.python.org/downloads/), the [Azure CLI](https://learn.microsoft.com/cli/azure/install-azure-cli), and [`uv`](https://docs.astral.sh/uv/getting-started/installation/).

```bash
git clone "https://github.com/henrysrtaylor/azure-rag-accelerator.git"
cd azure-rag-accelerator
uv sync
```

Configure Azure and run the application without activating the environment:

```bash
# Login to Azure (required for DefaultAzureCredential)
az login

# Configure .env with Azure resource details

# Terminal 1 - Start backend
uv run uvicorn app.backend:app --reload

# Terminal 2 - Start frontend
uv run streamlit run app/streamlit_app.py
```

Alternatively, activate `.venv` with `.\.venv\Scripts\Activate.ps1` on Windows PowerShell or `source .venv/bin/activate` on macOS/Linux. Once activated, omit the `uv run` prefix from the application commands.

Open http://localhost:8501 in your browser.


## 🔐 Document-Level Security

DLS restricts search results based on user's Entra ID security groups:

1. Documents are tagged with security group GUIDs during indexing
2. User authenticates via MSAL and receives JWT with `groups` claim
3. `build_security_filter()` creates OData filter from user's groups
4. Azure AI Search only returns documents matching user's groups

> **Note:** DLS is selected in the client: set the CLI `OPTION_SECURITY_GROUPS` constant to `False`, or turn off Streamlit's **Authentication (DLS)** toggle, for full file access.

See [docs/README_permissions.md](docs/README_permissions.md) for setup details.

## 🧪 Testing

The unit tests mock Azure service clients, so they do not require deployed resources or an Azure login.

Run the full test suite:

```bash
uv run pytest
```

Run a specific test module:

```bash
uv run pytest tests/test_pipeline.py
```

Run tests with a terminal coverage report:

```bash
uv run pytest --cov=raglib --cov=app --cov-report=term-missing
```

## 📚 Documentation

- [Getting Started](docs/README_getting_started.md)
- [Overall Flow](docs/README_overall_flow.md)
- [File Functionality](docs/README_file_functionality.md)
- [Infrastructure](docs/README_infrastructure.md)
- [Permissions & DLS](docs/README_permissions.md)
