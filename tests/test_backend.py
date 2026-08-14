import asyncio
from unittest.mock import Mock

import pytest

from app import backend


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
    inference_chat_logic = Mock(
        return_value={
            "assistant_message": {"role": "assistant", "content": "answer"},
            "suggested_questions": [],
            "references": [],
            "guardrail_triggered": False,
            "guardrail_type": None,
            "save_chat_history": True,
            "end_conversation": False,
        }
    )
    monkeypatch.setattr(backend, "build_security_filter", build_security_filter)
    monkeypatch.setattr(backend, "inference_chat_logic", inference_chat_logic)

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
    inference_chat_logic.assert_called_once_with(
        chat_history=[{"role": "user", "content": "question"}],
        security_filter="odata-filter",
        enable_query_refinement=False,
        enable_guardrail_checks=False,
        enable_suggested_questions=False,
    )
    assert result["assistant_message"]["content"] == "answer"


def test_chat_returns_standard_failure_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(backend, "build_security_filter", lambda groups: None)

    def raise_failure(**kwargs: object) -> dict:
        raise RuntimeError("Azure unavailable")

    monkeypatch.setattr(backend, "inference_chat_logic", raise_failure)

    result = asyncio.run(backend.chat(make_request()))

    assert result == backend.failure_chat_response()
    assert result["save_chat_history"] is False
