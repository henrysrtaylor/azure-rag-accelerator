from unittest.mock import Mock

import pytest

from raglib import pipeline
from raglib.citations import PLACEHOLDER_CITATION


@pytest.mark.parametrize(
    ("query", "response_key", "end_conversation"),
    [
        ("   ", "empty_query", False),
        ("QUIT", "exit", True),
    ],
)
def test_inference_returns_control_response_before_rag(
    monkeypatch: pytest.MonkeyPatch,
    query: str,
    response_key: str,
    end_conversation: bool,
) -> None:
    base_chat_logic = Mock()
    monkeypatch.setattr(pipeline, "base_chat_logic", base_chat_logic)

    result = pipeline.inference_chat_logic(
        [{"role": "user", "content": query}],
    )

    assert result["assistant_message"]["content"] == pipeline.CHAT_RESPONSES[
        response_key
    ]
    assert result["end_conversation"] is end_conversation
    assert result["save_chat_history"] is False
    base_chat_logic.assert_not_called()


def test_base_chat_logic_builds_answer_references_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "query_refinement",
        lambda history, deployment: "refined query",
    )
    retrieve_documents = Mock(
        return_value={"Guide": {"documents": "Relevant context"}}
    )
    monkeypatch.setattr(pipeline, "retrieve_documents", retrieve_documents)
    monkeypatch.setattr(
        pipeline,
        "send_llm_request",
        lambda deployment, messages: f"Answer [{PLACEHOLDER_CITATION}1]",
    )
    monkeypatch.setattr(
        pipeline,
        "guardrails",
        lambda query, model=False: {
            "guardrail_triggered": False,
            "guardrail_type": None,
        },
    )
    monkeypatch.setattr(
        pipeline,
        "generate_suggested_questions",
        lambda history, context: [{"id": "question-1", "text": "More?"}],
    )

    result = pipeline.base_chat_logic(
        [{"role": "user", "content": "original query"}],
        security_filter="security-filter",
    )

    retrieve_documents.assert_called_once_with(
        "refined query",
        security_filter="security-filter",
    )
    assert result["assistant_message"]["content"] == "Answer [1]"
    assert result["references"] == [{"id": 1, "text": "Guide"}]
    assert result["suggested_questions"][0]["text"] == "More?"
    assert "Relevant context" in result["document_context"]
    assert result["save_chat_history"] is True


def test_model_guardrail_removes_context_references_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(pipeline, "query_refinement", lambda history, deployment: "query")
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, security_filter=None: {
            "Guide": {"documents": "Sensitive model context"}
        },
    )
    monkeypatch.setattr(pipeline, "send_llm_request", lambda deployment, messages: "blocked")
    monkeypatch.setattr(
        pipeline,
        "guardrails",
        lambda query, model=False: {
            "guardrail_triggered": True,
            "guardrail_type": "inappropriate_text",
        },
    )
    suggestions = Mock()
    monkeypatch.setattr(pipeline, "generate_suggested_questions", suggestions)

    result = pipeline.base_chat_logic(
        [{"role": "user", "content": "question"}],
    )

    assert result["assistant_message"]["content"] == pipeline.CHAT_RESPONSES[
        "inappropriate_text"
    ]
    assert result["references"] == []
    assert result["suggested_questions"] == []
    assert result["document_context"] == ""
    assert result["save_chat_history"] is False
    suggestions.assert_not_called()

