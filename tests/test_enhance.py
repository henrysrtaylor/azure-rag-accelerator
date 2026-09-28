import pytest

from raglib import enhance


def test_refine_query_uses_prompt_and_appends_conversation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, object] = {}

    def fake_send_llm_request(deployment, messages, model_parameters=None):
        captured["deployment"] = deployment
        captured["messages"] = messages
        return "refined standalone question"

    monkeypatch.setattr(enhance, "send_llm_request", fake_send_llm_request)
    # The shared context is baked into the prompt at load time; use a sentinel
    # to stand in for the loaded refinement prompt.
    monkeypatch.setattr(
        enhance,
        "QUERY_REFINEMENT_PROMPT",
        "REFINEMENT INSTRUCTIONS\n\nAdditional Context:\n- Prod means production.",
    )

    enhancer = enhance.LanguageEnhancer()
    result = enhancer.refine_query(
        [
            {"role": "system", "content": "ignored system prompt"},
            {"role": "user", "content": "How do rollbacks work in prod?"},
        ]
    )

    assert result == "refined standalone question"
    prompt = captured["messages"][0]["content"]
    assert "REFINEMENT INSTRUCTIONS" in prompt
    assert "Additional Context:" in prompt
    assert "- Prod means production." in prompt
    assert "Conversation History:" in prompt
    assert "How do rollbacks work in prod?" in prompt
    # System messages are excluded from the conversation history block.
    assert "ignored system prompt" not in prompt
