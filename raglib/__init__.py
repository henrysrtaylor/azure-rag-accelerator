# RAG Library
"""
raglib - Azure RAG System Library for Azure AI Search and OpenAI

Usage:
    from raglib.config import load_env_vars, get_search_client
    from raglib.pipeline import inference_chat_logic
    from raglib.azure_ai import retrieve_documents, send_llm_request
    from raglib.guardrails import guardrails
    from raglib.prompts.markdown_loader import markdown_loader
    from raglib.permissions import build_security_filter
    from raglib.eval import (
        precision_recall_at_k,
        f1_score,
        judge_groundedness,
        judge_relevance,
        judge_coherence,
        judge_fluency,
    )
"""

__version__ = "0.1.0"
