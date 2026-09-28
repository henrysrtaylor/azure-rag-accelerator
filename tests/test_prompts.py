from raglib.prompts.prompts import (
    MAIN_AGENT_PROMPT,
    QUERY_REFINEMENT_PROMPT,
    SHARED_CONTEXT_PROMPT,
    SUGGESTED_QUESTIONS_PROMPT,
)


def test_shared_context_is_baked_into_prompts() -> None:
    # A distinctive line from prompt_shared_context.md.
    marker = "Prefer official Azure service names"
    assert marker in SHARED_CONTEXT_PROMPT
    assert marker in MAIN_AGENT_PROMPT
    assert marker in QUERY_REFINEMENT_PROMPT
    # HTML editor comments are stripped before reaching the model.
    assert "<!--" not in SHARED_CONTEXT_PROMPT
    assert "<!--" not in MAIN_AGENT_PROMPT
    assert "<!--" not in QUERY_REFINEMENT_PROMPT


def test_suggested_questions_placeholder_is_substituted() -> None:
    # The {number_suggested_questions} placeholder must be resolved at load.
    assert "{number_suggested_questions}" not in SUGGESTED_QUESTIONS_PROMPT
