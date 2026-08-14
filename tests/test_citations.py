from raglib.citations import (
    PLACEHOLDER_CITATION,
    align_references_and_answer,
    create_text_citation_map,
)


def test_create_text_citation_map_preserves_document_order() -> None:
    documents = {
        "First document": {"documents": "First content"},
        "Second document": {"documents": "Second content"},
    }

    assert create_text_citation_map(documents) == [
        {"id": 1, "text": "First document"},
        {"id": 2, "text": "Second document"},
    ]


def test_align_references_filters_and_renumbers_used_citations() -> None:
    citation_map = [
        {"id": 1, "text": "Unused"},
        {"id": 2, "text": "Used second"},
        {"id": 3, "text": "Used third"},
    ]
    answer = (
        f"Start [{PLACEHOLDER_CITATION}3], then "
        f"[{PLACEHOLDER_CITATION}2] and [{PLACEHOLDER_CITATION}3] again."
    )

    result = align_references_and_answer(answer, citation_map)

    assert result["answer"] == "Start [2], then [1] and [2] again."
    assert result["text_citation_map"] == [
        {"id": 1, "text": "Used second"},
        {"id": 2, "text": "Used third"},
    ]
