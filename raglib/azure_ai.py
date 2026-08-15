"""Azure AI service integrations for search and LLM operations.

Provides functions for document retrieval via Azure AI Search (hybrid search)
and LLM interactions via the Microsoft Foundry OpenAI v1 API.
"""

from azure.search.documents.models import VectorizableTextQuery

from raglib.clients import get_chat_client, get_project_names, get_search_client
from raglib.config import app_config


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
    )

    # Execute combined search - vector, keyword, and semantic
    # Apply security filter if provided
    results = search_client.search(
        search_text=text_query,
        search_fields=["content_text"],  # keyword search field
        vector_queries=[vector_query],  # vector search
        query_type="semantic",  # enable semantic ranking
        semantic_configuration_name=semantic_config_name,  # use your semantic config
        select=["content_text", "document_title", "document_date"],
        filter=security_filter,  # Apply document-level security filter
        top=app_config.number_documents_retrieve,
    )

    # process results to combine chunks by title and page number
    results = list(results)
    retrieved_documents = {}
    for title in list(
        set([doc["document_title"] for doc in results])
    ):  # combine all chunks for the same title.
        documents = [
            doc["content_text"] for doc in results if doc["document_title"] == title
        ]  # combine all chunks for the same title and page number
        retrieved_documents[title] = {
            # Combine chunks that share a document title.
            "documents": "\n".join(documents),
        }

    return retrieved_documents


def send_llm_request(deployment_name: str, messages: list[dict[str, str]]) -> str:
    """
    Send a chat completion request via the Microsoft Foundry OpenAI v1 API.

    Args:
        deployment_name: The model deployment name (e.g., 'gpt-5').
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        The model's response text, stripped of leading/trailing whitespace.
    """
    chat_client = get_chat_client()
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
        reasoning_effort=app_config.reasoning_effort,
    )
    content = response.choices[0].message.content
    return content.strip() if content else ""
