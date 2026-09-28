from unittest.mock import Mock

import pytest

from raglib import pipeline
from raglib.citations import PLACEHOLDER_CITATION, Citation
from raglib.guardrails import GuardrailResult
from raglib.prompts.responses import EMPTY_QUERY_RESPONSE, GUARDRAIL_RESPONSE


def test_run_returns_empty_response_before_rag(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    rag_pipeline = pipeline.RAGPipeline()
    refine_query = Mock()
    monkeypatch.setattr(rag_pipeline.language_enhancer, "refine_query", refine_query)

    result = rag_pipeline.run(
        [{"role": "user", "content": "   "}],
    )

    assert result.answer == EMPTY_QUERY_RESPONSE
    assert result.save_chat_history is False
    refine_query.assert_not_called()


def test_run_uses_main_agent_prompt_and_source_material(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, security_filter=None: {"Guide": {"documents": "Relevant"}},
    )

    captured: dict[str, object] = {}

    def capture_send(deployment, messages, model_parameters=None):
        captured["messages"] = messages
        return f"Answer [{PLACEHOLDER_CITATION}1]"

    monkeypatch.setattr(pipeline, "send_llm_request", capture_send)

    rag_pipeline = pipeline.RAGPipeline(enable_suggested_questions=False)
    # The shared context is baked into the main agent prompt at load time;
    # use a sentinel to stand in for the loaded prompt.
    rag_pipeline.prompt_main_agent = "MAIN AGENT PROMPT\n\nAdditional Context:\n- Prod."
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "refine_query",
        lambda messages: "query",
    )
    no_guardrail = GuardrailResult(triggered=False)
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_input",
        lambda query: no_guardrail,
    )
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_output",
        lambda query: no_guardrail,
    )

    rag_pipeline.run([{"role": "user", "content": "question"}])

    system_prompt = captured["messages"][0]["content"]
    assert "MAIN AGENT PROMPT" in system_prompt
    assert "Additional Context:" in system_prompt
    assert "- Prod." in system_prompt
    assert "Source Material:" in system_prompt


def test_run_builds_complete_response(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    retrieve_documents = Mock(return_value={"Guide": {"documents": "Relevant context"}})
    monkeypatch.setattr(pipeline, "retrieve_documents", retrieve_documents)
    monkeypatch.setattr(
        pipeline,
        "send_llm_request",
        lambda *args, **kwargs: f"Answer [{PLACEHOLDER_CITATION}1]",
    )

    rag_pipeline = pipeline.RAGPipeline()
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "refine_query",
        lambda messages: "refined query",
    )
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "generate_suggested_questions",
        lambda messages, documents: [{"id": "question-1", "text": "More?"}],
    )
    no_guardrail = GuardrailResult(triggered=False)
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_input",
        lambda query: no_guardrail,
    )
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_output",
        lambda query: no_guardrail,
    )
    result = rag_pipeline.run(
        [{"role": "user", "content": "original query"}],
        security_filter="security-filter",
    )

    retrieve_documents.assert_called_once_with(
        "refined query",
        security_filter="security-filter",
    )
    assert result.answer == "Answer [1]"
    assert result.references == [Citation(id=1, text="Guide")]
    assert result.suggested_questions[0]["text"] == "More?"
    assert "Relevant context" in result.document_context
    assert result.save_chat_history is True


def test_model_guardrail_removes_context_references_and_suggestions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
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
        lambda *args, **kwargs: "blocked",
    )

    rag_pipeline = pipeline.RAGPipeline()
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "refine_query",
        lambda messages: "query",
    )
    suggestions = Mock()
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "generate_suggested_questions",
        suggestions,
    )
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_input",
        lambda query: GuardrailResult(triggered=False),
    )
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_output",
        lambda query: GuardrailResult(
            triggered=True, guardrail_type="inappropriate_text"
        ),
    )
    result = rag_pipeline.run(
        [{"role": "user", "content": "question"}],
    )

    assert result.answer == GUARDRAIL_RESPONSE
    assert result.references == []
    assert result.suggested_questions == []
    assert result.document_context == ""
    assert result.save_chat_history is False
    suggestions.assert_not_called()


def test_run_skips_suggestions_when_disabled(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        pipeline,
        "retrieve_documents",
        lambda query, security_filter=None: {"Guide": {"documents": "Context"}},
    )
    monkeypatch.setattr(
        pipeline,
        "send_llm_request",
        lambda *args, **kwargs: f"Answer [{PLACEHOLDER_CITATION}1]",
    )

    rag_pipeline = pipeline.RAGPipeline(enable_suggested_questions=False)
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "refine_query",
        lambda messages: "query",
    )
    suggestions = Mock()
    monkeypatch.setattr(
        rag_pipeline.language_enhancer,
        "generate_suggested_questions",
        suggestions,
    )
    no_guardrail = GuardrailResult(triggered=False)
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_input",
        lambda query: no_guardrail,
    )
    monkeypatch.setattr(
        rag_pipeline.guardrail_evaluator,
        "check_output",
        lambda query: no_guardrail,
    )
    result = rag_pipeline.run(
        [{"role": "user", "content": "question"}],
        security_filter="security-filter",
    )

    assert result.answer == "Answer [1]"
    assert result.references == [Citation(id=1, text="Guide")]
    assert "Context" in result.document_context
    assert result.suggested_questions == []
    suggestions.assert_not_called()
