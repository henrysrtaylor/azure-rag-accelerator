from dataclasses import FrozenInstanceError

import pytest

from raglib.config import app_config


def test_config_has_valid_immutable_values() -> None:
    assert app_config is not None
    assert isinstance(app_config.large_deployed_model, str)
    assert app_config.large_deployed_model
    assert app_config.chunk_size > 0
    assert app_config.number_documents_retrieve > 0
    assert app_config.number_chunks_retrieve > 0
    assert app_config.indexer_batch_size > 0
    assert app_config.embedding_dimensions > 0
    assert app_config.search_mode in {"any", "all"}

    with pytest.raises(FrozenInstanceError):
        app_config.chunk_size = 2000


def test_guardrail_thresholds_are_grouped() -> None:
    assert app_config.guardrails.hate >= 0
    assert app_config.guardrails.self_harm >= 0
    assert app_config.guardrails.sexual >= 0
    assert app_config.guardrails.violence >= 0


def test_task_model_config_builds_model_parameters() -> None:
    parameters = app_config.main_agent.as_model_parameters()
    assert parameters == {
        "reasoning_effort": app_config.main_agent.reasoning_effort,
        "max_completion_tokens": app_config.main_agent.max_tokens,
    }

