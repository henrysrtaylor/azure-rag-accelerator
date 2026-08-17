# File Functionality Reference

This document provides a brief overview of each Python file in the codebase.

---

## Core RAG Library (`raglib/`)

### `config.py`
Defines `AppConfig` for application behavior and model settings and `EvalConfig` for evaluation pass/fail thresholds. The frozen `app_config` and `eval_config` instances are imported by their respective consumers.

### `clients.py`
Environment loading and cached Azure client initialization. Creates Azure AI Search, Content Safety, storage, and OpenAI clients. The OpenAI client uses the Microsoft Foundry `/openai/v1/` endpoint with an automatically refreshed Entra ID bearer token.

### `log.py`
Shared standard-library logging configuration. `configure_logging()` sends timestamped application logs to stdout and suppresses noisy Azure SDK request and authentication logs.

The Azure Function intentionally uses the platform-provided logger instead of importing this module.

### `azure_ai.py`
Core retrieval and LLM interaction functions. `retrieve_documents()` performs hybrid search (vector + keyword + semantic) against Azure AI Search with optional DLS filtering. `send_llm_request()` calls Microsoft Foundry model deployments through the stable OpenAI SDK and v1 Chat Completions API.

### `pipeline.py`
Main chat orchestration logic. `RAGPipeline` stores stable feature configuration and coordinates input controls → query refinement → document retrieval → citation formatting → LLM response → model guardrails → suggested questions. Its single `run()` method returns the complete standard response, allowing API and evaluation callers to consume the fields they need. Chat history and document security filters are supplied per method call.

### `chat_response.py`
Constructs the standard chat response dictionary used by pipeline and application outcomes.

### `permissions.py`
Document-Level Security (DLS) implementation. `build_security_filter()` converts user security group GUIDs into an OData filter expression that restricts search results to documents the user is authorized to view.

### `guardrails.py`
Content moderation and safety checks. `GuardrailEvaluator` owns Azure Content Safety integration and LLM-based topic classification. Exposes `check_input()` for user messages (content moderation + jailbreak + off-topic) and `check_output()` for model responses (content moderation only). Returns a typed `GuardrailResult` dataclass. Fails closed on API errors.

### `enhance.py`
Query enhancement utilities. `LanguageEnhancer` owns the model deployment and provides `refine_query()` to rewrite user queries using conversation context, and `generate_suggested_questions()` to suggest follow-up questions based on conversation history and retrieved documents.

### `citations.py`
Reference management for RAG responses. Creates citation placeholders for documents, formats context for the LLM, and post-processes responses to replace placeholders with numbered references linked to source documents.

---

## Prompts (`raglib/prompts/`)

### `markdown_loader.py`
Markdown template management. Loads `.md` files from the prompts folder with support for variable substitution using `{variable}` syntax.

### `prompts.py`
Preloads named system prompts used by the pipeline, guardrails, evaluation, enhancement, and indexing modules.

### `responses.py`
Preloads static response text for empty input, guardrail outcomes, and unexpected failures. Response dictionary construction remains in `raglib/chat_response.py`.

---

## Applications (`app/`)

### `backend.py`
FastAPI REST API server. Exposes `/chat` for RAG interactions, user and model guardrails, empty-message responses, and the history-save decision; `/health_check` provides monitoring. Handles request/response serialization and security group passthrough.

### `streamlit_app.py`
Web-based chat interface built with Streamlit. Provides a modern UI with MSAL authentication, configurable options (guardrails, DLS, references, suggested questions), and real-time chat with the RAG backend. Calls the unified FastAPI `/chat` endpoint via HTTP.

### `cli_app.py`
Interactive command-line chat client (legacy). Authenticates users via MSAL (browser-based Microsoft login), extracts security groups from the JWT token, and provides a terminal-based conversation interface through the unified `/chat` endpoint. Useful for testing and headless environments.

---

## Evaluation (`evaluation/`)

### `evaluation_script.py`
RAG quality evaluation using Azure AI Evaluation SDK. Runs evaluators for groundedness, similarity, relevance, fluency, and coherence against a test dataset (JSONL format) in `data/evaluation/`. Includes `precision_recall_at_k()` for retrieval metrics.

---

## AI Search Setup (`infrastructure/ai_search/`)

### `index.py`
Creates the Azure AI Search index schema. Defines fields for content, embeddings, metadata, and security groups with appropriate search configurations (vector, keyword, semantic).

### `indexer.py`
Creates the indexer pipeline with skillset. Configures document extraction, text chunking, embedding generation, image verbalization, and security group lookup via Azure Function (WebApiSkill).

---

## Infrastructure (`infrastructure/functions/`)

### `function_app.py`
Azure Function for security group lookup. Called by the indexer WebApiSkill to map document names to security group GUIDs. Reads from a JSON file (or Cosmos DB in production).
