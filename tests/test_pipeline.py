from unittest.mock import Mock

import pytest

from raglib import pipeline
from raglib.citations import PLACEHOLDER_CITATION
from raglib.prompts.responses import EMPTY_QUERY_RESPONSE, GUARDRAIL_RESPONSE


def test_inference_returns_empty_response_before_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rag_pipeline = pipeline.RAGPipeline()
    run = Mock()
    monkeypatch.setattr(rag_pipeline, "_run", run)

    result = rag_pipeline.run_inference(
        [{"role": "user", "content": "   "}],
    )

    assert result["assistant_message"]["content"] == EMPTY_QUERY_RESPONSE
    assert result["save_chat_history"] is False
    run.assert_not_called()


def test_run_inference_builds_answer_references_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "query_refinement",
        lambda history, deployment: "refined query",
    )
    retrieve_documents = Mock(return_value={"Guide": {"documents": "Relevant context"}})
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

    rag_pipeline = pipeline.RAGPipeline()
    result = rag_pipeline.run_inference(
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
    assert "document_context" not in result
    assert result["save_chat_history"] is True


def test_model_guardrail_removes_context_references_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "query_refinement",
        lambda history, deployment: "query",
    )
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, security_filter=None: {
            "Guide": {"documents": "Sensitive model context"}
        },
    )
    monkeypatch.setattr(
        pipeline,
        "send_llm_request",
        lambda deployment, messages: "blocked",
    )
    monkeypatch.setattr(
        pipeline,
        "guardrails",
        lambda query, model=False: (
            {
                "guardrail_triggered": True,
                "guardrail_type": "inappropriate_text",
            }
            if model
            else {"guardrail_triggered": False, "guardrail_type": None}
        ),
    )
    suggestions = Mock()
    monkeypatch.setattr(pipeline, "generate_suggested_questions", suggestions)

    rag_pipeline = pipeline.RAGPipeline()
    result = rag_pipeline.run_inference(
        [{"role": "user", "content": "question"}],
    )

    assert result["assistant_message"]["content"] == GUARDRAIL_RESPONSE
    assert result["references"] == []
    assert result["suggested_questions"] == []
    assert "document_context" not in result
    assert result["save_chat_history"] is False
    suggestions.assert_not_called()


def test_run_evaluation_returns_evaluation_fields(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rag_pipeline = pipeline.RAGPipeline()
    run = Mock(
        return_value={
            "assistant_message": {"role": "assistant", "content": "answer"},
            "suggested_questions": [],
            "references": [{"id": 1, "text": "Guide"}],
            "document_context": "Relevant context",
            "guardrail_triggered": False,
            "guardrail_type": None,
            "save_chat_history": True,
        }
    )
    monkeypatch.setattr(rag_pipeline, "_run", run)

    result = rag_pipeline.run_evaluation(
        [{"role": "user", "content": "question"}],
        security_filter="security-filter",
    )

    run.assert_called_once_with(
        [{"role": "user", "content": "question"}],
        "security-filter",
        generate_questions=False,
    )
    assert result == {
        "assistant_message": {"role": "assistant", "content": "answer"},
        "references": [{"id": 1, "text": "Guide"}],
        "document_context": "Relevant context",
        "save_chat_history": True,
    }
