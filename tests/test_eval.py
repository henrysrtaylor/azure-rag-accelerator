import pytest

from raglib import eval as eval_module
from raglib.eval import LLMJudge, f1_score, precision_recall_at_k


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


def test_judge_parses_fenced_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eval_module,
        "send_llm_request",
        lambda deployment, messages: (
            '```json\n{"score": 4, "reasoning": "Mostly grounded"}\n```'
        ),
    )
    judge = LLMJudge("test-model")
    assert judge.groundedness("q", "ctx", "resp")["score"] == 4


def test_judge_parses_plain_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eval_module,
        "send_llm_request",
        lambda deployment, messages: '{"score": 5, "reasoning": "Perfect"}',
    )
    judge = LLMJudge("test-model")
    result = judge.relevance("q", "resp")
    assert result["score"] == 5
    assert result["reasoning"] == "Perfect"


def test_judge_handles_malformed_json(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        eval_module,
        "send_llm_request",
        lambda deployment, messages: "not json at all",
    )
    judge = LLMJudge("test-model")
    result = judge.fluency("resp")
    assert result["score"] is None
    assert "JSON parse error" in result["reasoning"]
