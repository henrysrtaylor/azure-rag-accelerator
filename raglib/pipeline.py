"""RAG pipeline orchestration.

Coordinates document retrieval, LLM generation, citations, guardrails,
and suggested questions into a unified chat response.
"""

from raglib.azure_ai import retrieve_documents, send_llm_request
from raglib.chat_response import create_chat_response
from raglib.citations import (
    align_references_and_answer,
    create_text_citation_map,
    format_documents_with_citations,
)
from raglib.config import config
from raglib.enhance import generate_suggested_questions, query_refinement
from raglib.guardrails import guardrails
from raglib.prompts.prompts import MAIN_AGENT_PROMPT
from raglib.prompts.responses import (
    EMPTY_QUERY_RESPONSE,
    GUARDRAIL_RESPONSE,
)


class RAGPipeline:
    def __init__(
        self,
        enable_query_refinement: bool = True,
        enable_suggested_questions: bool = True,
        enable_guardrail_checks: bool = True,
    ) -> None:
        """Initialize the RAG pipeline with feature configuration.

        Args:
            enable_query_refinement: Whether to refine the latest user query
                before document retrieval.
            enable_suggested_questions: Whether inference responses should
                include generated follow-up questions.
            enable_guardrail_checks: Whether to validate the latest user
                message before running the RAG flow.
        """
        self.prompt_main_agent = MAIN_AGENT_PROMPT
        self.enable_query_refinement = enable_query_refinement
        self.enable_suggested_questions = enable_suggested_questions
        self.enable_guardrail_checks = enable_guardrail_checks

    def _get_control_response(
        self,
        latest_user_query: str,
    ) -> dict | None:
        """Return an early response for empty input or a triggered guardrail.

        Args:
            latest_user_query: Most recent user message.

        Returns:
            A standard chat response when processing should stop, otherwise
            None.
        """
        latest_user_query = latest_user_query.strip()

        if not latest_user_query:
            return create_chat_response(EMPTY_QUERY_RESPONSE)

        if self.enable_guardrail_checks:
            user_guardrail_response = guardrails(latest_user_query, model=False)
            if user_guardrail_response["guardrail_triggered"]:
                guardrail_type = user_guardrail_response["guardrail_type"]
                return create_chat_response(
                    GUARDRAIL_RESPONSE,
                    guardrail_type=guardrail_type,
                )

        return None

    def _run(
        self,
        chat_history: list[dict[str, str]],
        security_filter: str | None,
        *,
        generate_questions: bool,
    ) -> dict:
        """Run shared retrieval, generation, citations, and output guardrails.

        Args:
            chat_history: Conversation messages with role and content keys.
            security_filter: OData filter for document-level security. None
                bypasses document-level filtering.
            generate_questions: Whether to generate suggested follow-up
                questions for this run.

        Returns:
            Standard chat response containing the answer, suggestions,
            references, document context, guardrail state, and history-save
            decision.
        """
        if self.enable_query_refinement:
            user_query = query_refinement(chat_history, config.large_deployed_model)
        else:
            user_query = next(
                (
                    message["content"]
                    for message in reversed(chat_history)
                    if message["role"] == "user"
                ),
                "",
            )

        retrieved_documents = (
            retrieve_documents(user_query, security_filter=security_filter)
            if user_query
            else {}
        )
        text_citation_map = create_text_citation_map(retrieved_documents)
        documents_joined = format_documents_with_citations(
            retrieved_documents,
            text_citation_map,
        )

        main_agent_messages = [
            {
                "role": "system",
                "content": self.prompt_main_agent + "\n\nContext:" + documents_joined,
            }
        ]
        model_answer = send_llm_request(
            config.large_deployed_model,
            main_agent_messages + chat_history,
        )

        guardrail_response = guardrails(model_answer, model=True)
        model_guardrail_triggered = guardrail_response["guardrail_triggered"]
        if model_guardrail_triggered:
            model_answer = GUARDRAIL_RESPONSE
            generated_id_questions = []
            text_citation_map = []
            documents_joined = ""
        else:
            generated_id_questions = (
                generate_suggested_questions(chat_history, documents_joined)
                if generate_questions
                else []
            )
            align_response = align_references_and_answer(
                model_answer,
                text_citation_map,
            )
            model_answer = align_response["answer"]
            text_citation_map = align_response["text_citation_map"]

        return create_chat_response(
            model_answer,
            suggested_questions=generated_id_questions,
            references=text_citation_map,
            document_context=documents_joined,
            guardrail_triggered=model_guardrail_triggered,
            guardrail_type=guardrail_response["guardrail_type"],
            save_chat_history=not model_guardrail_triggered,
        )

    def run_inference(
        self,
        chat_history: list[dict[str, str]],
        security_filter: str | None = None,
    ) -> dict:
        """Run the RAG pipeline for an inference request.

        Applies input control checks before the shared RAG flow and excludes
        document context from the returned response.

        Args:
            chat_history: Conversation messages with role and content keys.
            security_filter: OData filter for document-level security. None
                bypasses document-level filtering.

        Returns:
            Chat response containing the assistant message, suggested
            questions, references, guardrail state, and history-save decision.
        """
        latest_user_query = next(
            (
                message["content"]
                for message in reversed(chat_history)
                if message["role"] == "user"
            ),
            "",
        )
        control_response = self._get_control_response(latest_user_query)
        if control_response:
            return control_response

        chat_response = self._run(
            chat_history,
            security_filter,
            generate_questions=self.enable_suggested_questions,
        )
        chat_response.pop("document_context")
        return chat_response

    def run_evaluation(
        self,
        chat_history: list[dict[str, str]],
        security_filter: str | None = None,
    ) -> dict:
        """Run the RAG pipeline and return evaluation-specific fields.

        Suggested questions are not generated, and inference-only guardrail
        metadata is excluded from the returned response.

        Args:
            chat_history: Conversation messages with role and content keys.
            security_filter: OData filter for document-level security. None
                bypasses document-level filtering.

        Returns:
            Evaluation response containing the assistant message, references,
            document context, and history-save decision.
        """
        chat_response = self._run(
            chat_history,
            security_filter,
            generate_questions=False,
        )
        chat_response.pop("suggested_questions")
        chat_response.pop("guardrail_triggered")
        chat_response.pop("guardrail_type")
        return chat_response
