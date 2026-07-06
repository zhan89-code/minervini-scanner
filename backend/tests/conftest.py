import pytest

from app.config import DEFAULT_SETTINGS


class FakeConfig:
    """cfg.get(key) over DEFAULT_SETTINGS, no DB round-trip -- lets pipeline
    unit tests stay pure per CODE_BLUEPRINT.md §2 ("takes a DataFrame,
    returns a result... can be unit-tested against fixture OHLCV without
    hitting the network")."""

    def __init__(self, overrides: dict | None = None):
        self._values = {k: v for k, (v, _t) in DEFAULT_SETTINGS.items()}
        self._values.update(overrides or {})

    def get(self, key: str):
        return self._values[key]


@pytest.fixture
def cfg():
    return FakeConfig()
