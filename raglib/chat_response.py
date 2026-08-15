"""Construction helpers for the standard chat response shape."""


def create_chat_response(
    content: str,
    *,
    suggested_questions: list | None = None,
    references: list | None = None,
    document_context: str | None = None,
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
        "document_context": document_context,
        "guardrail_triggered": guardrail_triggered,
        "guardrail_type": guardrail_type,
        "save_chat_history": save_chat_history,
    }
