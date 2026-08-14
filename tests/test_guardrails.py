import pytest

from raglib import guardrails as guardrails_module


@pytest.mark.parametrize(
    ("scores", "expected"),
    [
        ({"hate": 3, "self_harm": 3, "sexual": 3, "violence": 3}, False),
        ({"hate": 4, "self_harm": 0, "sexual": 0, "violence": 0}, True),
    ],
)
def test_content_moderation_thresholds(
    monkeypatch: pytest.MonkeyPatch,
    scores: dict[str, int],
    expected: bool,
) -> None:
    monkeypatch.setattr(guardrails_module, "moderate_content", lambda text: scores)

    assert guardrails_module._is_content_moderation_detected("input") is expected


def test_guardrail_decision_prioritizes_content_moderation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    results = {
        "content_moderation_detected": True,
        "prompt_injection_detected": True,
        "off_topic_detected": True,
    }
    monkeypatch.setattr(
        guardrails_module,
        "_run_guardrails",
        lambda query, check_prompt_and_topic: results,
    )

    result = guardrails_module.guardrails("input")

    assert result["guardrail_type"] == "inappropriate_text"
    assert result["guardrail_triggered"] is True
