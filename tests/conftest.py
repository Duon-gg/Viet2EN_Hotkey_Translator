from __future__ import annotations

import copy

import pytest

from utils import config


@pytest.fixture(autouse=True)
def isolated_config():
    previous = config.config
    config.config = config._validated(copy.deepcopy(config.DEFAULT_CONFIG))
    try:
        yield config.config
    finally:
        config.config = previous
