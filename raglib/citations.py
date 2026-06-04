"""Citation handling for RAG responses.

Manages placeholder-based citations in LLM responses, allowing documents to be
referenced by number and later resolved to actual document titles.
"""

PLACEHOLDER_CITATION = "PlaceholderTitleCitation_"


def create_text_citation_map(retrieved_documents: dict[str, dict]) -> list[dict[str, int | str]]:
    """
    Create a mapping of document titles to citation IDs.

    Args:
        retrieved_documents: Dict of documents keyed by title.

    Returns:
        List of dicts with 'id' (int) and 'text' (title) for each document.
    """
    titles = list(retrieved_documents.keys()) # Get titles from retrieved documents
    text_citation_map = [{"id": idx, "text": title} for idx, title in enumerate(titles, start=1)]
    return text_citation_map


def format_documents_with_citations(
    retrieved_documents: dict[str, dict],
    text_citation_map: list[dict[str, int | str]]
) -> str:
    """
    Format documents with citation placeholders for LLM consumption.

    Args:
        retrieved_documents: Dict of documents keyed by title.
        text_citation_map: List of citation mappings from create_text_citation_map.

    Returns:
        Formatted string with all documents and their citation placeholders.
    """
    formatted_documents = []
    
    for citation_dict in text_citation_map:
        citation_id = citation_dict['id']
        title = citation_dict['text']
        document_content = retrieved_documents[title]['documents']
        formatted_document = f"TextTitle: [{PLACEHOLDER_CITATION}{citation_id}] | TextContext: [{document_content}]"
        formatted_documents.append(formatted_document)
    
    return "\n".join(formatted_documents)


def align_references_and_answer(
    answer: str,
    text_citation_map: list[dict[str, int | str]]
) -> dict[str, str | list]:
    """
    Filter citations to only those used in the answer and renumber them.

    Args:
        answer: The LLM response containing citation placeholders.
        text_citation_map: Full list of citation mappings.

    Returns:
        Dict with 'answer' (updated text) and 'text_citation_map' (filtered citations).
    """
    # Filter to only citations that appear in the answer
    used_citations = [
        c for c in text_citation_map
        if f"{PLACEHOLDER_CITATION}{c['id']}" in answer
    ]

    for new_id, citation in enumerate(used_citations, start=1):
        old_placeholder = f"{PLACEHOLDER_CITATION}{citation['id']}"
        answer = answer.replace(old_placeholder, str(new_id))
        citation['id'] = new_id

    return {"answer": answer, "text_citation_map": used_citations}


