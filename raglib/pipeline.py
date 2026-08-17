"""RAG pipeline orchestration.

Coordinates document retrieval, LLM generation, citations, guardrails,
and suggested questions into a unified chat response.
"""

from dataclasses import dataclass, field

from raglib.azure_ai import retrieve_documents, send_llm_request
from raglib.citations import (
    Citation,
    align_references_and_answer,
    create_text_citation_map,
    format_documents_with_citations,
)
from raglib.config import app_config
from raglib.enhance import LanguageEnhancer
from raglib.guardrails import GuardrailEvaluator, GuardrailResult
from raglib.prompts.prompts import MAIN_AGENT_PROMPT
from raglib.prompts.responses import (
    EMPTY_QUERY_RESPONSE,
    GUARDRAIL_RESPONSE,
)


@dataclass
class PipelineResult:
    """Complete result of a RAG pipeline run."""

    answer: str
    suggested_questions: list[dict[str, str]] = field(default_factory=list)
    references: list[Citation] = field(default_factory=list)
    document_context: str = ""
    guardrail: GuardrailResult = field(
        default_factory=lambda: GuardrailResult(triggered=False)
    )
    save_chat_history: bool = True


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
        self.guardrail_evaluator = GuardrailEvaluator()
        self.language_enhancer = LanguageEnhancer()
        self.enable_query_refinement = enable_query_refinement
        self.enable_suggested_questions = enable_suggested_questions
        self.enable_guardrail_checks = enable_guardrail_checks

    def _get_control_response(
        self,
        latest_user_query: str,
    ) -> PipelineResult | None:
        """Return an early response for empty input or a triggered guardrail.

        Args:
            latest_user_query: Most recent user message.

        Returns:
            A PipelineResult when processing should stop, otherwise None.
        """
        latest_user_query = latest_user_query.strip()

        if not latest_user_query:
            return PipelineResult(answer=EMPTY_QUERY_RESPONSE, save_chat_history=False)

        if self.enable_guardrail_checks:
            input_result = self.guardrail_evaluator.check_input(latest_user_query)
            if input_result.triggered:
                return PipelineResult(
                    answer=GUARDRAIL_RESPONSE,
                    guardrail=input_result,
                    save_chat_history=False,
                )

        return None

    def run(
        self,
        chat_history: list[dict[str, str]],
        security_filter: str | None = None,
    ) -> PipelineResult:
        """Run input controls, retrieval, generation, and output processing.

        Args:
            chat_history: Conversation messages with role and content keys.
            security_filter: OData filter for document-level security. None
                bypasses document-level filtering.

        Returns:
            PipelineResult containing the answer, references, suggestions,
            document context, guardrail state, and history-save decision.
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

        if self.enable_query_refinement:
            user_query = self.language_enhancer.refine_query(chat_history)
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
            app_config.large_deployed_model,
            main_agent_messages + chat_history,
        )

        output_result = self.guardrail_evaluator.check_output(model_answer)
        if output_result.triggered:
            return PipelineResult(
                answer=GUARDRAIL_RESPONSE,
                guardrail=output_result,
                save_chat_history=False,
            )

        generated_id_questions = (
            self.language_enhancer.generate_suggested_questions(
                chat_history, documents_joined
            )
            if self.enable_suggested_questions
            else []
        )
        model_answer, text_citation_map = align_references_and_answer(
            model_answer,
            text_citation_map,
        )

        return PipelineResult(
            answer=model_answer,
            suggested_questions=generated_id_questions,
            references=text_citation_map,
            document_context=documents_joined,
            guardrail=output_result,
            save_chat_history=True,
        )
