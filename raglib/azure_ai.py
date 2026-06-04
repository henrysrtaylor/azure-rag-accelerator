"""Azure AI service integrations for search and LLM operations.

Provides functions for document retrieval via Azure AI Search (hybrid search)
and LLM interactions via Azure OpenAI (chat completions, embeddings).
"""
import os
from typing import Optional

from azure.search.documents.models import VectorizableTextQuery

from raglib.config import get_project_names, get_search_client, get_openai_client


def retrieve_documents(
    text_query: str,
    security_filter: Optional[str] = None
) -> dict[str, dict[str, str]]:
    """
    Retrieve documents using hybrid search (vector + keyword + semantic reranking).

    Args:
        text_query: The search query text.
        security_filter: OData filter for document-level security (from permissions module).

    Returns:
        Dict mapping document titles to their content: {title: {"documents": str}}.
    """
    _, semantic_config_name = get_project_names()
    search_client = get_search_client()
    number_doc_retrieved = int(os.getenv("PARAMETER_NUMBER_DOC_RETRIEVE", "5"))
    k_nearest_neighbors = int(os.getenv("PARAMETER_K_NEAREST_NEIGHBORS", "3"))
    
    vector_query = VectorizableTextQuery(text = text_query,
                                        k_nearest_neighbors=k_nearest_neighbors,             
                                        fields = "content_embedding",   
                                        exhaustive = False)
    
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
        top=number_doc_retrieved
    )
    
    # process results to combine chunks by title and page number
    results = list(results)
    retrieved_documents = {}
    for title in list(set([doc['document_title'] for doc in results])): # combine all chunks for the same title.
        documents = [doc['content_text'] for doc in results if doc['document_title'] == title] # combine all chunks for the same title and page number
        retrieved_documents[title] = {
            "documents": "\n".join(documents), # format as one string for each unuque title (which can be title or title+page number)
        }

    return retrieved_documents

def send_llm_request(deployment_name: str, messages: list[dict[str, str]]) -> str:
    """
    Send a chat completion request to Azure OpenAI.

    Args:
        deployment_name: The model deployment name (e.g., 'gpt-5').
        messages: List of message dicts with 'role' and 'content' keys.

    Returns:
        The model's response text, stripped of leading/trailing whitespace.
    """
    open_ai_client = get_openai_client()
    
    # Get reasoning effort from param or env, default to 'low' for fast responses
    effort = os.getenv("AZURE_FOUNDRY_REASONING_EFFORT", "low")
    
    # reasoning_effort: For reasoning models (gpt-5, o3), controls thinking depth. Ignored for non-reasoning models (gpt-5-mini).
    response = open_ai_client.chat.completions.create(
        model=deployment_name,
        messages=messages,
        reasoning_effort=effort
    )
    return response.choices[0].message.content.strip() # Return the answer from the model

