"""
Query enhancement utilities: refinement and suggested questions.
"""

import re
import uuid

from raglib.azure_ai import send_llm_request
from raglib.config import app_config
from raglib.prompts.prompts import QUERY_REFINEMENT_PROMPT, SUGGESTED_QUESTIONS_PROMPT  


# Functions for query refinement and suggested questions generation
def query_refinement(messages: list, deployment: str) -> str:
    """
    Function to refine a user's query based on the conversation history.
    """
    message_content = "Conversation History:\n" + "\n".join(
        [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
    )

    query_refinement_messages = [
        {
            "role": "system",
            "content": QUERY_REFINEMENT_PROMPT
            + "\n##########\n"
            + message_content
            + "\n##########",
        }
    ]

    return send_llm_request(deployment, query_refinement_messages).strip()


def generate_suggested_questions(
    messages: list[dict[str, str]], documents_joined: str
) -> list[dict[str, str]]:
    """
    Generate follow-up questions based on conversation and retrieved documents.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        documents_joined: Concatenated document content string.

    Returns:
        List of dicts with 'id' (UUID) and 'text' (question) for each suggestion.
    """

    message_content = (
        "Context:\n"
        + documents_joined
        + "\n\nConversation History:"
        + "\n".join(
            [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
        )
    )

    generate_suggested_questions_messages = [
        {
            "role": "system",
            "content": SUGGESTED_QUESTIONS_PROMPT + "\n\n" + message_content,
        }
    ]

    answer = send_llm_request(
        app_config.large_deployed_model, generate_suggested_questions_messages
    ).strip()

    pattern_match = r"\[([^\[\]]*?\?)\]"
    matches = re.findall(pattern_match, answer)

    if not matches:
        return []
    return [{"id": str(uuid.uuid4()), "text": question} for question in matches]
