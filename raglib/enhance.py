"""
Query enhancement utilities: refinement and suggested questions.
"""
import os
import re
import uuid

from raglib.azure_ai import send_llm_request
from raglib.prompts.markdown_loader import markdown_loader

# Load prompts
prompt_query_refinement = markdown_loader("prompt_query_refinement")
number_suggested_questions = int(os.getenv('PARAMETER_SUGGESTED_QUESTIONS', '3'))
prompt_suggested_questions = markdown_loader("prompt_suggested_questions", number_suggested_questions=number_suggested_questions)

###
# Functions for query refinement and suggested questions generation
###
def query_refinement(messages: list, deployment: str) -> str:
    """
    Function to refine a user's query based on the conversation history.
    """
    message_content = "Conversation History:\n" + "\n".join(
        [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
    )

    query_refinement_messages = [
        {"role": "system", "content": prompt_query_refinement + "\n##########\n" + message_content + "\n##########"}
    ]

    return send_llm_request(
        deployment,
        query_refinement_messages
    ).strip()


def generate_suggested_questions(
    messages: list[dict[str, str]],
    documents_joined: str
) -> list[dict[str, str]]:
    """
    Generate follow-up questions based on conversation and retrieved documents.

    Args:
        messages: List of message dicts with 'role' and 'content' keys.
        documents_joined: Concatenated document content string.

    Returns:
        List of dicts with 'id' (UUID) and 'text' (question) for each suggestion.
    """
    message_content = "Context:\n" + documents_joined + "\n\nConversation History:" + "\n".join(
        [f"{m['role']}: {m['content']}" for m in messages if m["role"] != "system"]
    )

    generate_suggested_questions_messages = [
        {"role": "system", "content": prompt_suggested_questions + "\n\n" + message_content}
    ]

    answer = send_llm_request(
        os.getenv("AZURE_FOUNDRY_LARGE_DEPLOYED_MODEL"),
        generate_suggested_questions_messages
    ).strip()

    pattern_match = r'\[([^\[\]]*?\?)\]'
    matches = re.findall(pattern_match, answer)

    if not matches:
        return []
    return [{"id": str(uuid.uuid4()), "text": question} for question in matches]
