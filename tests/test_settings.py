import pytest

from movici_simulation_core.settings import Settings


def test_deprecated_disk_storage_setting():
    with pytest.warns(FutureWarning):
        settings = Settings(storage="disk")
    assert settings.storage == "file"
