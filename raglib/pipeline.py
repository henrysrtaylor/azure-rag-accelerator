"""RAG pipeline orchestration.

Coordinates document retrieval, LLM generation, citations, guardrails,
and suggested questions into a unified chat response.
"""
import os
from typing import Optional

from raglib.azure_ai import retrieve_documents, send_llm_request
from raglib.citations import align_references_and_answer, create_text_citation_map, format_documents_with_citations
from raglib.enhance import generate_suggested_questions, query_refinement
from raglib.guardrails import check_model_guardrails
from raglib.prompts.markdown_loader import markdown_loader

prompt_main_agent = markdown_loader(
    "prompt_main_agent",
    allowed_topics=os.getenv("PARAMETER_ALLOWED_TOPICS", "Any topic")
)


def base_chat_logic(
    chat_history: list[dict[str, str]],
    security_filter: Optional[str] = None
) -> dict:
    """
    Core RAG pipeline: retrieve documents, generate response, apply guardrails.

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security. [] means no groups, which will deny all access in DLS filter logic. None means bypass DLS filter (full access).

    Returns:
        Dict with 'assistant_message', 'suggested_questions', 'references',
        and 'document_context'.
    """
    option_query_refinement = os.getenv("OPTION_QUERY_REFINEMENT", "true").lower() in ("true", "1", "yes")
    option_suggested_questions = os.getenv("OPTION_SUGGESTED_QUESTIONS", "true").lower() in ("true", "1", "yes")

    # Internal guardrail flag for model output validation
    model_guardrail_triggered = False

    # Query refinement
    if option_query_refinement:
        user_query = query_refinement(chat_history)
    else:
        user_query = next(
            (m["content"] for m in reversed(chat_history) if m["role"] == "user"),
            ""
        )

    # Document retrieval
    if not user_query:
        retrieved_documents = {}
    else:
        retrieved_documents = retrieve_documents(user_query, security_filter=security_filter)

    # Create citations
    text_citation_map = create_text_citation_map(retrieved_documents)
    documents_joined = format_documents_with_citations(retrieved_documents, text_citation_map)

    # LLM generation
    main_agent_messages = [{"role": "system", "content": prompt_main_agent + "\n\nContext:" + documents_joined}]
    model_answer = send_llm_request(
        os.getenv("AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL"),
        main_agent_messages + chat_history
    )

    # Model guardrail check
    guardrail_response = check_model_guardrails(model_answer)
    model_guardrail_triggered = guardrail_response["guardrail_triggered"]
    if model_guardrail_triggered:
        model_answer = guardrail_response["guardrail_answer"]
        generated_id_questions = []
        text_citation_map = []
        documents_joined = ""
    else:
        if option_suggested_questions:
            generated_id_questions = generate_suggested_questions(chat_history, documents_joined)
        else:
            generated_id_questions = []

        align_response = align_references_and_answer(model_answer, text_citation_map)
        model_answer = align_response["answer"]
        text_citation_map = align_response["text_citation_map"]
    
    return {
        "assistant_message": {"role": "assistant", "content": model_answer},
        "suggested_questions": generated_id_questions,
        "references": text_citation_map,
        "document_context": documents_joined
    }


def evaluation_chat_logic(
    chat_history: list[dict[str, str]],
    security_filter: Optional[str] = None
) -> dict:
    """
    RAG pipeline for evaluation mode (includes document_context, excludes suggested_questions).

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security.

    Returns:
        Dict with 'assistant_message', 'references', and 'document_context'.
    """
    chat_response = base_chat_logic(chat_history, security_filter=security_filter)
    chat_response.pop("suggested_questions")
    return chat_response


def inference_chat_logic(
    chat_history: list[dict[str, str]],
    security_filter: Optional[str] = None
) -> dict:
    """
    RAG pipeline for inference mode (includes suggested_questions, excludes document_context).

    Args:
        chat_history: List of message dicts with 'role' and 'content' keys.
        security_filter: OData filter for document-level security.

    Returns:
        Dict with 'assistant_message', 'suggested_questions', and 'references'.
    """
    chat_response = base_chat_logic(chat_history, security_filter=security_filter)
    chat_response.pop("document_context")
    return chat_response
