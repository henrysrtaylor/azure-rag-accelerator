from collections.abc import Iterator

import pytest

from raglib import clients


TEST_ENV = {
	"AZURE_CONTENT_MODERATOR_API_VERSION": "2024-09-01",
	"AZURE_CONTENT_MODERATOR_ENDPOINT": "https://content.test",
	"AZURE_FOUNDRY_API_VERSION": "2024-06-01",
	"AZURE_FOUNDRY_ENDPOINT": "https://foundry.test",
	"AZURE_SEARCH_PROJECT_PREFIX": "test-project",
	"AZURE_SEARCH_SERVICE_ENDPOINT": "https://search.test",
}

CACHED_CLIENT_FUNCTIONS = (
	clients._get_credential,
	clients.get_project_names,
	clients.get_search_index_client,
	clients.get_search_indexer_client,
	clients.get_search_client,
	clients.get_chat_client,
	clients.get_content_safety_client,
)


@pytest.fixture(autouse=True)
def isolated_test_environment(monkeypatch: pytest.MonkeyPatch) -> Iterator[None]:
	for name, value in TEST_ENV.items():
		monkeypatch.setenv(name, value)
	for cached_function in CACHED_CLIENT_FUNCTIONS:
		cached_function.cache_clear()

	yield

	for cached_function in CACHED_CLIENT_FUNCTIONS:
		cached_function.cache_clear()
