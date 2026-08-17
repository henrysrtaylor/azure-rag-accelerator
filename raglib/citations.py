"""Citation handling for RAG responses.

Manages placeholder-based citations in LLM responses, allowing documents to be
referenced by number and later resolved to actual document titles.
"""

from dataclasses import dataclass

PLACEHOLDER_CITATION = "PlaceholderTitleCitation_"


@dataclass(frozen=True)
class Citation:
    id: int
    text: str


def create_text_citation_map(
    retrieved_documents: dict[str, dict],
) -> list[Citation]:
    """
    Create a citation for each retrieved document title.

    Args:
        retrieved_documents: Dict of documents keyed by title.

    Returns:
        List of Citation objects with sequential IDs.
    """
    return [
        Citation(id=idx, text=title)
        for idx, title in enumerate(retrieved_documents.keys(), start=1)
    ]


def format_documents_with_citations(
    retrieved_documents: dict[str, dict], text_citation_map: list[Citation]
) -> str:
    """
    Format documents with citation placeholders for LLM consumption.

    Args:
        retrieved_documents: Dict of documents keyed by title.
        text_citation_map: List of Citation objects from create_text_citation_map.

    Returns:
        Formatted string with all documents and their citation placeholders.
    """
    formatted_documents = []
    for citation in text_citation_map:
        document_content = retrieved_documents[citation.text]["documents"]
        formatted_documents.append(
            f"TextTitle: [{PLACEHOLDER_CITATION}{citation.id}] | "
            f"TextContext: [{document_content}]"
        )
    return "\n".join(formatted_documents)


def align_references_and_answer(
    answer: str, text_citation_map: list[Citation]
) -> tuple[str, list[Citation]]:
    """
    Filter citations to only those used in the answer and renumber them.

    Args:
        answer: The LLM response containing citation placeholders.
        text_citation_map: Full list of citation mappings.

    Returns:
        Tuple of (updated answer text, filtered and renumbered citations).
    """
    used = [c for c in text_citation_map if f"{PLACEHOLDER_CITATION}{c.id}" in answer]
    aligned: list[Citation] = []
    for new_id, citation in enumerate(used, start=1):
        old_placeholder = f"{PLACEHOLDER_CITATION}{citation.id}"
        answer = answer.replace(old_placeholder, str(new_id))
        aligned.append(Citation(id=new_id, text=citation.text))
    return answer, aligned
