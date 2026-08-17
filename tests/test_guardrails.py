import pytest

from raglib.guardrails import GuardrailEvaluator


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
    evaluator = GuardrailEvaluator()
    monkeypatch.setattr(evaluator, "moderate_content", lambda text: scores)

    assert evaluator._is_content_moderation_detected("input") is expected


def test_guardrail_decision_prioritizes_content_moderation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = GuardrailEvaluator()
    results = {
        "content_moderation_detected": True,
        "prompt_injection_detected": True,
        "off_topic_detected": True,
    }
    monkeypatch.setattr(
        evaluator,
        "_run_checks",
        lambda query, check_prompt_and_topic: results,
    )

    result = evaluator.check_input("input")

    assert result.guardrail_type == "inappropriate_text"
    assert result.triggered is True


def test_output_check_only_runs_content_moderation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    evaluator = GuardrailEvaluator()
    monkeypatch.setattr(
        evaluator,
        "_is_content_moderation_detected",
        lambda text: False,
    )
    monkeypatch.setattr(
        evaluator,
        "detect_jailbreak",
        lambda text: pytest.fail("output check ran jailbreak detection"),
    )
    monkeypatch.setattr(
        evaluator,
        "_is_off_topic",
        lambda text: pytest.fail("output check ran topic detection"),
    )

    from raglib.guardrails import GuardrailResult

    result = evaluator.check_output("model response")

    assert result == GuardrailResult(triggered=False)
