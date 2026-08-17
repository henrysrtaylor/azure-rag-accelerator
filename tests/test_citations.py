from raglib.citations import (
    PLACEHOLDER_CITATION,
    Citation,
    align_references_and_answer,
    create_text_citation_map,
)


def test_create_text_citation_map_preserves_document_order() -> None:
    documents = {
        "First document": {"documents": "First content"},
        "Second document": {"documents": "Second content"},
    }

    assert create_text_citation_map(documents) == [
        Citation(id=1, text="First document"),
        Citation(id=2, text="Second document"),
    ]


def test_align_references_filters_and_renumbers_used_citations() -> None:
    citation_map = [
        Citation(id=1, text="Unused"),
        Citation(id=2, text="Used second"),
        Citation(id=3, text="Used third"),
    ]
    answer = (
        f"Start [{PLACEHOLDER_CITATION}3], then "
        f"[{PLACEHOLDER_CITATION}2] and [{PLACEHOLDER_CITATION}3] again."
    )

    new_answer, aligned = align_references_and_answer(answer, citation_map)

    assert new_answer == "Start [2], then [1] and [2] again."
    assert aligned == [
        Citation(id=1, text="Used second"),
        Citation(id=2, text="Used third"),
    ]
