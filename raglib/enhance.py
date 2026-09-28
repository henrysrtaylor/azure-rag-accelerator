"""
Query enhancement utilities: refinement and suggested questions.
"""

import re
import uuid

from raglib.azure_ai import send_llm_request
from raglib.config import app_config
from raglib.prompts.prompts import (
    QUERY_REFINEMENT_PROMPT,
    SUGGESTED_QUESTIONS_PROMPT,
)


class LanguageEnhancer:
    """Query refinement and suggested question generation."""

    def __init__(self, config=app_config) -> None:
        self.config = config

    def refine_query(self, messages: list[dict[str, str]]) -> str:
        """Refine the latest user query using conversation history.

        The editable, use-case-specific background context
        (``prompt_shared_context``, shared with the main agent) is baked into
        ``QUERY_REFINEMENT_PROMPT`` at load time, so the model can resolve
        references and enrich the standalone query with facts that live outside
        the indexed documents.
        """
        conversation_history = "\n".join(
            [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
        )
        refinement_messages = [
            {
                "role": "system",
                "content": QUERY_REFINEMENT_PROMPT
                + "\n\n## Conversation History:\n"
                + conversation_history,
            }
        ]
        return send_llm_request(
            self.config.large_deployed_model,
            refinement_messages,
            self.config.query_refinement.as_model_parameters(),
        ).strip()

    def generate_suggested_questions(
        self, messages: list[dict[str, str]], documents_joined: str
    ) -> list[dict[str, str]]:
        """Generate follow-up questions from conversation and documents."""
        message_content = (
            "## Source Material:\n"
            + documents_joined
            + "\n\n## Conversation History:\n"
            + "\n".join(
                [
                    f"{m['role']}: {m['content']}"
                    for m in messages
                    if m["role"] != "system"
                ]
            )
        )
        suggestion_messages = [
            {
                "role": "system",
                "content": SUGGESTED_QUESTIONS_PROMPT + "\n\n" + message_content,
            }
        ]
        answer = send_llm_request(
            self.config.large_deployed_model,
            suggestion_messages,
            self.config.suggested_questions.as_model_parameters(),
        ).strip()

        pattern = r"\[([^\[\]]*?\?)\]"
        matches = re.findall(pattern, answer)
        if not matches:
            return []
        return [{"id": str(uuid.uuid4()), "text": q} for q in matches]
