from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from azure.ai.inference.models import AssistantMessage, SystemMessage, UserMessage

from raglib import azure_ai


def test_retrieve_documents_passes_filter_and_combines_title_chunks(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    search_client = Mock()
    search_client.search.return_value = [
        {"document_title": "Guide", "content_text": "Chunk one"},
        {"document_title": "Other", "content_text": "Other content"},
        {"document_title": "Guide", "content_text": "Chunk two"},
    ]
    monkeypatch.setattr(
        azure_ai,
        "get_project_names",
        lambda: ("test-index", "test-semantic"),
    )
    monkeypatch.setattr(azure_ai, "get_search_client", lambda: search_client)

    documents = azure_ai.retrieve_documents(
        "search query",
        security_filter="security-filter",
    )

    assert documents == {
        "Guide": {"documents": "Chunk one\nChunk two"},
        "Other": {"documents": "Other content"},
    }
    search_arguments = search_client.search.call_args.kwargs
    assert search_arguments["search_text"] == "search query"
    assert search_arguments["filter"] == "security-filter"
    assert search_arguments["semantic_configuration_name"] == "test-semantic"
    assert search_arguments["top"] == 5
    assert search_arguments["vector_queries"][0].k_nearest_neighbors == 3


def test_send_llm_request_converts_roles_and_strips_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    chat_client = Mock()
    chat_client.complete.return_value = SimpleNamespace(
        choices=[SimpleNamespace(message=SimpleNamespace(content="  answer  "))]
    )
    monkeypatch.setattr(azure_ai, "get_chat_client", lambda deployment: chat_client)

    result = azure_ai.send_llm_request(
        "test-deployment",
        [
            {"role": "system", "content": "system prompt"},
            {"role": "assistant", "content": "prior answer"},
            {"role": "user", "content": "question"},
            {"role": "unknown", "content": "fallback user"},
        ],
    )

    assert result == "answer"
    messages = chat_client.complete.call_args.kwargs["messages"]
    assert isinstance(messages[0], SystemMessage)
    assert isinstance(messages[1], AssistantMessage)
    assert isinstance(messages[2], UserMessage)
    assert isinstance(messages[3], UserMessage)
    assert chat_client.complete.call_args.kwargs["model_extras"] == {
        "reasoning_effort": "low"
    }
