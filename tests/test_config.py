from dataclasses import FrozenInstanceError

import pytest

from raglib.config import app_config


def test_config_has_valid_immutable_values() -> None:
    assert app_config is not None
    assert isinstance(app_config.large_deployed_model, str)
    assert app_config.large_deployed_model
    assert app_config.chunk_size > 0
    assert app_config.number_documents_retrieve > 0
    assert app_config.embedding_dimensions > 0

    with pytest.raises(FrozenInstanceError):
        app_config.chunk_size = 2000
