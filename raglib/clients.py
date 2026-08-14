"""Environment loading and cached Azure client factories."""

import os
from functools import lru_cache

from azure.ai.contentsafety import ContentSafetyClient
from azure.ai.inference import ChatCompletionsClient
from azure.identity import AzureCliCredential, ChainedTokenCredential, ManagedIdentityCredential
from azure.search.documents import SearchClient
from azure.search.documents.indexes import SearchIndexClient, SearchIndexerClient
from azure.storage.filedatalake import DataLakeServiceClient, FileSystemClient
from dotenv import load_dotenv


def load_env_vars(path: str | None = None) -> None:
    """Load Azure resource and authentication values from a dotenv file."""
    load_dotenv(path, override=True)


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


@lru_cache(maxsize=4)
def get_chat_client(deployment_name: str) -> ChatCompletionsClient:
    """Get a cached Foundry chat-completions client for a deployment."""
    load_env_vars()
    base = os.getenv("AZURE_FOUNDRY_ENDPOINT")
    api_version = os.getenv("AZURE_FOUNDRY_API_VERSION", "2024-06-01")
    openai_prefixes = (
        "gpt-",
        "o1",
        "o3",
        "text-embedding",
        "dall-e",
        "whisper",
        "tts",
    )
    if deployment_name.lower().startswith(openai_prefixes):
        endpoint = f"{base}/openai/deployments/{deployment_name}"
    else:
        endpoint = f"{base}/models/{deployment_name}"

    return ChatCompletionsClient(
        endpoint=endpoint,
        credential=_get_credential(),
        credential_scopes=["https://cognitiveservices.azure.com/.default"],
        api_version=api_version,
    )


@lru_cache(maxsize=1)
def get_content_safety_client() -> ContentSafetyClient:
    """Get a cached Azure AI Content Safety client."""
    load_env_vars()
    return ContentSafetyClient(
        endpoint=os.getenv("AZURE_CONTENT_MODERATOR_ENDPOINT"),
        credential=_get_credential(),
    )


def get_storage_file_system_client(file_system_name: str) -> FileSystemClient:
    """Get an ADLS Gen2 filesystem client."""
    load_env_vars()
    service_client = DataLakeServiceClient(
        account_url=os.getenv("STORAGE_DFS_ACCOUNT_URL"),
        credential=_get_credential(),
    )
    return service_client.get_file_system_client(file_system_name)