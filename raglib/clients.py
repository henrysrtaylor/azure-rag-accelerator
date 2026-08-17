"""Environment loading and cached Azure client factories."""

import os
from functools import lru_cache

from azure.ai.contentsafety import ContentSafetyClient
from azure.identity import (
    AzureCliCredential,
    ChainedTokenCredential,
    ManagedIdentityCredential,
    get_bearer_token_provider,
)
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from dotenv import load_dotenv
from openai import OpenAI


def load_env_vars(path: str | None = None) -> None:
    """Load Azure resource and authentication values from a dotenv file."""
    load_dotenv(path, override=True)
    required = [
        "AZURE_FOUNDRY_ENDPOINT",
        "AZURE_SEARCH_SERVICE_ENDPOINT",
        "AZURE_CONTENT_MODERATOR_ENDPOINT",
        "AZURE_SEARCH_PROJECT_PREFIX",
    ]
    missing = [v for v in required if not os.getenv(v)]
    if missing:
        raise OSError(f"Missing required environment variables: {', '.join(missing)}")


@lru_cache(maxsize=1)
def _get_credential() -> ChainedTokenCredential:
    """Get a cached Azure credential and validate it eagerly."""
    credential = ChainedTokenCredential(
        AzureCliCredential(),
        ManagedIdentityCredential(),
    )
    credential.get_token("https://cognitiveservices.azure.com/.default")
    return credential


@lru_cache(maxsize=1)
def get_project_names() -> tuple[str, str]:
    """Return the configured search index and semantic configuration names."""
    load_env_vars()
    project_prefix = os.getenv("AZURE_SEARCH_PROJECT_PREFIX")
    return f"{project_prefix}-index", f"{project_prefix}-default-semantic-config"


@lru_cache(maxsize=1)
def get_search_index_client() -> SearchIndexClient:
    """Get a cached Azure AI Search index client."""
    load_env_vars()
    return SearchIndexClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        credential=_get_credential(),
    )


@lru_cache(maxsize=1)
def get_search_indexer_client() -> SearchIndexerClient:
    """Get a cached Azure AI Search indexer client."""
    load_env_vars()
    return SearchIndexerClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        credential=_get_credential(),
    )


@lru_cache(maxsize=1)
def get_search_client() -> SearchClient:
    """Get a cached Azure AI Search document client."""
    load_env_vars()
    index_name, _ = get_project_names()
    return SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        index_name=index_name,
        credential=_get_credential(),
    )


@lru_cache(maxsize=1)
def get_chat_client() -> OpenAI:
    """Get a cached OpenAI v1 client for Microsoft Foundry models."""
    load_env_vars()
    endpoint = os.environ["AZURE_FOUNDRY_ENDPOINT"].rstrip("/")
    token_provider = get_bearer_token_provider(
        _get_credential(),
        "https://ai.azure.com/.default",
    )
    return OpenAI(
        base_url=f"{endpoint}/openai/v1/",
        api_key=token_provider,
    )


@lru_cache(maxsize=1)
def get_content_safety_client() -> ContentSafetyClient:
    """Get a cached Azure AI Content Safety client."""
    load_env_vars()
    return ContentSafetyClient(
        endpoint=os.getenv("AZURE_CONTENT_MODERATOR_ENDPOINT"),
        credential=_get_credential(),
    )
