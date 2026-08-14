import pytest

from raglib import eval as eval_module
from raglib.eval import f1_score, precision_recall_at_k


@pytest.mark.parametrize(
    ("retrieved", "ground_truth", "k", "expected"),
    [
        (["doc1", "doc2"], ["doc1", "doc3"], 2, (0.5, 0.5)),
    ],
)
def test_precision_recall_at_k(
    retrieved: list[str],
    ground_truth: list[str],
    k: int,
    expected: tuple[float, float],
) -> None:
    assert precision_recall_at_k(retrieved, ground_truth, k) == expected


def test_f1_score_partial_overlap() -> None:
    assert f1_score("quick fox", "quick brown fox") == pytest.approx(0.8)


def test_call_judge_parses_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eval_module,
        "send_llm_request",
        lambda deployment, messages: (
            '```json\n{"score": 4, "reasoning": "Mostly grounded"}\n```'
        ),
    )

    assert eval_module._call_judge("criteria", "content")["score"] == 4
