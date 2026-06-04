"""Azure client configuration and initialization.

Provides cached client factories for Azure services (Search, OpenAI, Content Safety,
Blob Storage) using DefaultAzureCredential for authentication.
"""
import os
from functools import lru_cache

from azure.ai.contentsafety import ContentSafetyClient
from azure.identity import DefaultAzureCredential, get_bearer_token_provider
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.storage.blob import BlobServiceClient, ContainerClient
from dotenv import load_dotenv
from openai import AzureOpenAI


def load_env_vars(path: str | None = None) -> None:
    """
    Load environment variables from a .env file.

    Args:
        path: Optional path to .env file. Uses default discovery if None.
    """
    load_dotenv(path, override=True)


@lru_cache(maxsize=1)
def _get_credential() -> DefaultAzureCredential:
    """Get cached Azure credential for service authentication."""
    return DefaultAzureCredential()


@lru_cache(maxsize=1)
def get_project_names() -> tuple[str, str]:
    """
    Get project-specific names for search index and semantic config.

    Returns:
        Tuple of (index_name, semantic_config_name).
    """
    load_env_vars()
    project_prefix = f'{os.getenv("AZURE_SEARCH_PROJECT_PREFIX")}-{os.getenv("BLOB_CONTAINER_SUB_FOLDER")}'
    index_name = f"{project_prefix}-index"
    semantic_config_name = f"{project_prefix}-default-semantic-config"
    return index_name, semantic_config_name

@lru_cache(maxsize=1)
def get_search_index_client() -> SearchIndexClient:
    """Get cached SearchIndexClient for index management."""
    load_env_vars()
    return SearchIndexClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        credential=_get_credential()
    )


@lru_cache(maxsize=1)
def get_search_indexer_client() -> SearchIndexerClient:
    """Get cached SearchIndexerClient for indexer management."""
    load_env_vars()
    return SearchIndexerClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        credential=_get_credential()
    )


@lru_cache(maxsize=1)
def get_search_client() -> SearchClient:
    """Get cached SearchClient for document search operations."""
    load_env_vars()
    index_name, _ = get_project_names()
    return SearchClient(
        endpoint=os.getenv("AZURE_SEARCH_SERVICE_ENDPOINT"),
        index_name=index_name,
        credential=_get_credential()
    )


@lru_cache(maxsize=1)
def get_openai_client() -> AzureOpenAI:
    """Get cached AzureOpenAI client for LLM operations."""
    load_env_vars()
    token_provider = get_bearer_token_provider(
        _get_credential(),
        "https://cognitiveservices.azure.com/.default"
    )
    return AzureOpenAI(
        azure_endpoint=os.getenv("AZURE_FOUNDRY_ENDPOINT"),
        api_version=os.getenv("AZURE_FOUNDRY_API_VERSION"),
        azure_ad_token_provider=token_provider
    )


@lru_cache(maxsize=1)
def get_content_safety_client() -> ContentSafetyClient:
    """Get cached ContentSafetyClient for content moderation."""
    load_env_vars()
    return ContentSafetyClient(
        endpoint=os.getenv("AZURE_CONTENT_MODERATOR_ENDPOINT"),
        credential=_get_credential()
    )


def get_blob_container_client(container_name: str) -> ContainerClient:
    """
    Get a Blob ContainerClient for the specified container.

    Args:
        container_name: Name of the blob container.

    Returns:
        ContainerClient for the specified container.
    """
    load_env_vars()
    blob_service_client = BlobServiceClient(
        account_url=os.getenv("BLOB_ACCOUNT_URL"),
        credential=_get_credential()
    )
    return blob_service_client.get_container_client(container_name)
