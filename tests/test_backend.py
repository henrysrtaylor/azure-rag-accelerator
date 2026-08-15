import asyncio
from unittest.mock import Mock

import pytest

from app import backend
from raglib.chat_response import create_chat_response
from raglib.prompts.responses import FAILURE_RESPONSE


def make_request(**overrides: object) -> backend.ChatRequest:
    values = {
        "chat_history": [{"role": "user", "content": "question"}],
        "security_groups": ["group-a"],
        "enable_query_refinement": True,
        "enable_guardrail_checks": True,
        "enable_suggested_questions": True,
    }
    values.update(overrides)
    return backend.ChatRequest.model_validate(values)


def test_chat_forwards_security_filter_and_feature_flags(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    build_security_filter = Mock(return_value="odata-filter")
    run_inference = Mock(
        return_value={
            "assistant_message": {"role": "assistant", "content": "answer"},
            "suggested_questions": [],
            "references": [],
            "guardrail_triggered": False,
            "guardrail_type": None,
            "save_chat_history": True,
        }
    )
    rag_pipeline = Mock(run_inference=run_inference)
    rag_pipeline_class = Mock(return_value=rag_pipeline)
    monkeypatch.setattr(backend, "build_security_filter", build_security_filter)
    monkeypatch.setattr(backend, "RAGPipeline", rag_pipeline_class)

    result = asyncio.run(
        backend.chat(
            make_request(
                enable_query_refinement=False,
                enable_guardrail_checks=False,
                enable_suggested_questions=False,
            )
        )
    )

    build_security_filter.assert_called_once_with(["group-a"])
    rag_pipeline_class.assert_called_once_with(
        enable_query_refinement=False,
        enable_guardrail_checks=False,
        enable_suggested_questions=False,
    )
    run_inference.assert_called_once_with(
        chat_history=[{"role": "user", "content": "question"}],
        security_filter="odata-filter",
    )
    assert result["assistant_message"]["content"] == "answer"


def test_chat_returns_standard_failure_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend, "build_security_filter", lambda groups: None)
    rag_pipeline = Mock()
    rag_pipeline.run_inference.side_effect = RuntimeError("Azure unavailable")
    monkeypatch.setattr(backend, "RAGPipeline", Mock(return_value=rag_pipeline))

    result = asyncio.run(backend.chat(make_request()))

    assert result == create_chat_response(FAILURE_RESPONSE)
    assert result["save_chat_history"] is False
