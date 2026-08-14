from dataclasses import FrozenInstanceError

import pytest

from raglib.config import Config, config


def test_config_has_valid_immutable_values() -> None:
    assert isinstance(config, Config)
    assert isinstance(config.large_deployed_model, str)
    assert config.large_deployed_model
    assert config.chunk_size > 0
    assert config.number_documents_retrieve > 0
    assert config.embedding_dimensions > 0

    with pytest.raises(FrozenInstanceError):
        config.chunk_size = 2000