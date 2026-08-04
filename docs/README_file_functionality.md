# File Functionality Reference

This document provides a brief overview of each Python file in the codebase.

---

## Core RAG Library (`raglib/`)

### `config.py`
Environment configuration and Azure client initialization. Loads environment variables from `.env` and creates cached SDK clients for Azure AI Search, Azure AI Foundry (LLM, embeddings, content safety), and storage access. All clients authenticate using `DefaultAzureCredential` (Managed Identity in Azure, Azure CLI locally).

### `log.py`
Structured logging to Azure Application Insights. Provides a `log_message()` function that sends custom events with severity levels and additional properties (tags, timestamps) for telemetry and debugging.

### `azure_ai.py`
Core retrieval and LLM interaction functions. `retrieve_documents()` performs hybrid search (vector + keyword + semantic) against Azure AI Search with optional DLS filtering. `send_llm_request()` calls Azure AI Foundry for chat completions.

### `pipeline.py`
Main chat orchestration logic. `base_chat_logic()` coordinates the full RAG pipeline: query refinement → document retrieval → citation formatting → LLM response → model guardrails → suggested questions. `inference_chat_logic()` applies user guardrails before retrieval and returns whether the client should retain the turn. `evaluation_chat_logic()` is a simplified version for testing.

### `permissions.py`
Document-Level Security (DLS) implementation. `build_security_filter()` converts user security group GUIDs into an OData filter expression that restricts search results to documents the user is authorized to view.

### `guardrails.py`
Content moderation and safety checks. Uses Azure AI Foundry Content Safety to detect harmful content (hate, violence, sexual, self-harm), prompt injection attempts, and jailbreak attacks. Provides both user-input validation (`check_user_guardrails()`) and model-output validation (`check_model_guardrails()`).

### `enhance.py`
Query enhancement utilities. Contains `query_refinement()` which rewrites user queries using conversation context to improve retrieval, and `generate_suggested_questions()` which uses an LLM to suggest relevant follow-up questions based on conversation history and retrieved documents.

### `citations.py`
Reference management for RAG responses. Creates citation placeholders for documents, formats context for the LLM, and post-processes responses to replace placeholders with numbered references linked to source documents.

---

## Prompts (`raglib/prompts/`)

### `markdown_loader.py`
Markdown template management. Loads `.md` files from the prompts folder with support for variable substitution using `{variable}` syntax.

---

## Applications (`app/`)

### `backend_server.py`
FastAPI REST API server. Exposes `/chat` for RAG interactions, user and model guardrails, empty-message and exit-command responses, and the history-save decision; `/health_check` provides monitoring. Handles request/response serialization and security group passthrough.

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
