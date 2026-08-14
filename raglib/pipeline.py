"""RAG pipeline orchestration.

Coordinates document retrieval, LLM generation, citations, guardrails,
and suggested questions into a unified chat response.
"""

from raglib.azure_ai import retrieve_documents, send_llm_request
from raglib.citations import (
    align_references_and_answer,
    create_text_citation_map,
    format_documents_with_citations,
)
from raglib.config import config
from raglib.enhance import generate_suggested_questions, query_refinement
from raglib.guardrails import guardrails
from raglib.prompts.markdown_loader import markdown_loader

prompt_main_agent = markdown_loader("prompt_main_agent")
CHAT_RESPONSES = {
    "empty_query": markdown_loader("responses/response_empty_query"),
    "exit": markdown_loader("responses/response_exit"),
    "failure": markdown_loader("responses/response_failure"),
    "inappropriate_text": markdown_loader("responses/response_inappropriate"),
    "jailbreak_attempt": markdown_loader("responses/response_jailbreak"),
    "off_topic_query": markdown_loader("responses/response_offtopic"),
}
_EXIT_PHRASES = {"exit", "quit", "stop", "bye", "goodbye"}


def _create_chat_response(
    content: str,
    *,
    guardrail_type: str | None = None,
    end_conversation: bool = False,
) -> dict:
    """Create a non-RAG chat response with the standard API response shape."""
    return {
        "assistant_message": {
            "role": "assistant",
            "content": content,
        },
        "suggested_questions": [],
        "references": [],
        "guardrail_triggered": guardrail_type is not None,
        "guardrail_type": guardrail_type,
        "save_chat_history": False,
        "end_conversation": end_conversation,
    }


def failure_chat_response() -> dict:
    """Create the standard response for an unexpected chat failure."""
    return _create_chat_response(CHAT_RESPONSES["failure"])


def _get_control_response(
    latest_user_query: str,
    enable_guardrail_checks: bool = True,
) -> dict | None:
    """Return early responses for empty/exit input or triggered user guardrails."""
    latest_user_query = latest_user_query.strip()

    if not latest_user_query:
        return _create_chat_response(CHAT_RESPONSES["empty_query"])

    if latest_user_query.lower() in _EXIT_PHRASES:
        return _create_chat_response(CHAT_RESPONSES["exit"], end_conversation=True)

    if enable_guardrail_checks:
        user_guardrail_response = guardrails(latest_user_query, model=False)
        if user_guardrail_response["guardrail_triggered"]:
            guardrail_type = user_guardrail_response["guardrail_type"]
            return _create_chat_response(
                CHAT_RESPONSES[guardrail_type],
                guardrail_type=guardrail_type,
            )

    return None


def base_chat_logic(
    chat_history: list[dict[str, str]],
    security_filter: str | None = None,
    enable_query_refinement: bool = True,
    enable_suggested_questions: bool = True,
) -> dict:
    """
    Core RAG pipeline: retrieve documents, generate response, apply guardrails.

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security. An empty group
            list denies access; None bypasses DLS filtering.
        enable_query_refinement: Whether to refine the latest user query before
            retrieval.
        enable_suggested_questions: Whether to generate follow-up questions.

    Returns:
        Dict with 'assistant_message', 'suggested_questions', 'references',
        and 'document_context'.
    """
    # Internal guardrail flag for model output validation
    model_guardrail_triggered = False

    # Query refinement
    if enable_query_refinement:
        user_query = query_refinement(chat_history, config.large_deployed_model)
    else:
        user_query = next(
            (m["content"] for m in reversed(chat_history) if m["role"] == "user"), ""
        )

    # Document retrieval
    if not user_query:
        retrieved_documents = {}
    else:
        retrieved_documents = retrieve_documents(
            user_query,
            security_filter=security_filter,
        )

    # Create citations
    text_citation_map = create_text_citation_map(retrieved_documents)
    documents_joined = format_documents_with_citations(
        retrieved_documents,
        text_citation_map,
    )

    # LLM generation
    main_agent_messages = [
        {
            "role": "system",
            "content": prompt_main_agent + "\n\nContext:" + documents_joined,
        }
    ]
    model_answer = send_llm_request(
        config.large_deployed_model, main_agent_messages + chat_history
    )

    # Model guardrail check
    guardrail_response = guardrails(model_answer, model=True)
    model_guardrail_triggered = guardrail_response["guardrail_triggered"]
    if model_guardrail_triggered:
        model_answer = CHAT_RESPONSES[guardrail_response["guardrail_type"]]
        generated_id_questions = []
        text_citation_map = []
        documents_joined = ""
    else:
        if enable_suggested_questions:
            generated_id_questions = generate_suggested_questions(
                chat_history,
                documents_joined,
            )
        else:
            generated_id_questions = []

        align_response = align_references_and_answer(model_answer, text_citation_map)
        model_answer = align_response["answer"]
        text_citation_map = align_response["text_citation_map"]

    return {
        "assistant_message": {"role": "assistant", "content": model_answer},
        "suggested_questions": generated_id_questions,
        "references": text_citation_map,
        "document_context": documents_joined,
        "guardrail_triggered": model_guardrail_triggered,
        "guardrail_type": guardrail_response["guardrail_type"],
        "save_chat_history": not model_guardrail_triggered,
    }


def evaluation_chat_logic(
    chat_history: list[dict[str, str]], security_filter: str | None = None
) -> dict:
    """
    RAG pipeline for evaluation mode.

    Includes document context and excludes suggested questions.

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security.

    Returns:
        Dict with 'assistant_message', 'references', and 'document_context'.
    """
    chat_response = base_chat_logic(
        chat_history,
        security_filter=security_filter,
        enable_query_refinement=True,
        enable_suggested_questions=False,
    )
    chat_response.pop("suggested_questions")
    chat_response.pop("guardrail_triggered")
    chat_response.pop("guardrail_type")
    return chat_response


def inference_chat_logic(
    chat_history: list[dict[str, str]],
    security_filter: str | None = None,
    enable_guardrail_checks: bool = True,
    enable_query_refinement: bool = True,
    enable_suggested_questions: bool = True,
) -> dict:
    """
    RAG pipeline for inference mode.

    Includes suggested questions and excludes document context.

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security.
        enable_guardrail_checks: Whether to validate the latest user message.
        enable_query_refinement: Whether to refine the latest user query before
            retrieval.
        enable_suggested_questions: Whether to generate follow-up questions.

    Returns:
        Dict with the assistant response, guardrail state, and history-save decision.
    """
    latest_user_query = next(
        (
            message["content"]
            for message in reversed(chat_history)
            if message["role"] == "user"
        ),
        "",
    )

    control_response = _get_control_response(
        latest_user_query=latest_user_query,
        enable_guardrail_checks=enable_guardrail_checks,
    )
    if control_response:
        return control_response

    chat_response = base_chat_logic(
        chat_history,
        security_filter=security_filter,
        enable_query_refinement=enable_query_refinement,
        enable_suggested_questions=enable_suggested_questions,
    )
    chat_response["end_conversation"] = False
    return chat_response
