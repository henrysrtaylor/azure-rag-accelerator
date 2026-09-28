"""Azure AI service integrations for search and LLM operations.

Provides functions for document retrieval via Azure AI Search (hybrid search)
and LLM interactions via the Microsoft Foundry OpenAI v1 API.
"""

import logging

from azure.search.documents.models import VectorizableTextQuery

from raglib.clients import get_chat_client, get_project_names, get_search_client
from raglib.config import app_config

logger = logging.getLogger(__name__)


def retrieve_documents(
    text_query: str, security_filter: str | None = None
) -> dict[str, dict[str, str]]:
    """
    Retrieve documents using hybrid search (vector + keyword + semantic reranking).

    Args:
        text_query: The search query text.
        security_filter: OData filter for document-level security from the
            permissions module.

    Returns:
        Dict mapping document titles to their content: {title: {"documents": str}}.
    """
    _, semantic_config_name = get_project_names()
    search_client = get_search_client()

    vector_query = VectorizableTextQuery(
        text=text_query,
        k_nearest_neighbors=app_config.k_nearest_neighbors,
        fields="content_embedding",
        exhaustive=False,
        weight=app_config.vector_weight,
    )

    # Execute combined search - vector, keyword, and semantic
    try:
        results = search_client.search(
            search_text=text_query,
            search_fields=["content_text"],
            search_mode=app_config.search_mode,
            vector_queries=[vector_query],
            query_type="semantic",
            semantic_configuration_name=semantic_config_name,
            select=["content_text", "document_title", "document_date"],
            filter=security_filter,
            top=app_config.number_chunks_retrieve,
        )
        results = list(results)
    except Exception:
        logger.exception("Azure AI Search retrieval failed")
        return {}

    # Preserve rank order and cap the number of distinct documents returned.
    ordered_titles: list[str] = []
    for doc in results:
        title = doc["document_title"]
        if title not in ordered_titles:
            ordered_titles.append(title)
    ordered_titles = ordered_titles[: app_config.number_documents_retrieve]

    retrieved_documents = {}
    for title in ordered_titles:
        documents = [
            doc["content_text"] for doc in results if doc["document_title"] == title
        ]  # combine all chunks that share a document title
        retrieved_documents[title] = {
            "documents": "\n".join(documents),
        }

    return retrieved_documents


def send_llm_request(
    deployment_name: str,
    messages: list[dict[str, str]],
    model_parameters: dict | None = None,
) -> str:
    """
    Send a chat completion request via the Microsoft Foundry OpenAI v1 API.

    Args:
        deployment_name: The model deployment name (e.g., 'gpt-5').
        messages: List of message dicts with 'role' and 'content' keys.
        model_parameters: Generation parameters (reasoning effort and token
            limit) built from a ``TaskModelConfig``. Defaults to the main-agent
            task configuration when omitted.

    Returns:
        The model's response text, stripped of leading/trailing whitespace.
    """
    chat_client = get_chat_client()
    if model_parameters is None:
        model_parameters = app_config.main_agent.as_model_parameters()
    normalized_messages = [
        {
            "role": message.get("role", "user")
            if message.get("role") in {"system", "assistant", "user"}
            else "user",
            "content": message.get("content", ""),
        }
        for message in messages
    ]
    response = chat_client.chat.completions.create(
        model=deployment_name,
        messages=normalized_messages,
        **model_parameters,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""
