"""Preloaded response templates and standard response construction helpers."""

from raglib.prompts.markdown_loader import markdown_loader

EMPTY_QUERY_RESPONSE = markdown_loader("responses/response_empty_query")
FAILURE_RESPONSE = markdown_loader("responses/response_failure")
GUARDRAIL_RESPONSE = markdown_loader("responses/response_guardrail")


def create_chat_response(
    content: str,
    *,
    suggested_questions: list | None = None,
    references: list | None = None,
    guardrail_triggered: bool | None = None,
    guardrail_type: str | None = None,
    save_chat_history: bool = False,
) -> dict:
    """Create a chat response with the standard API response shape."""
    if guardrail_triggered is None:
        guardrail_triggered = guardrail_type is not None

    return {
        "assistant_message": {
            "role": "assistant",
            "content": content,
        },
        "suggested_questions": suggested_questions or [],
        "references": references or [],
        "guardrail_triggered": guardrail_triggered,
        "guardrail_type": guardrail_type,
        "save_chat_history": save_chat_history,
    }


def failure_chat_response() -> dict:
    """Create the standard response for an unexpected chat failure."""
    return create_chat_response(FAILURE_RESPONSE)
