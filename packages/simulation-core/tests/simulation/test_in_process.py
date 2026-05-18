import pytest

from movici_simulation_core.core import AttributeSchema, Service
from movici_simulation_core.settings import Settings
from movici_simulation_core.simulation.common import ServiceInfo
from movici_simulation_core.simulation.in_process import (
    InProcessSimulationRunner,
    InProcessUpdateDataClient,
)


def test_store_and_retrieve_updates():
    client = InProcessUpdateDataClient()
    address, key = client.put({"some": "data"})
    assert client.get(address, key, mask=None) == {"some": "data"}


def test_retrieve_update_with_mask():
    client = InProcessUpdateDataClient()
    address, key = client.put({"some": "data", "other": "data"})
    assert client.get(address, key, mask={"some": None}) == {"some": "data"}


def test_retrieve_data_with_invalid_mask_raises():
    client = InProcessUpdateDataClient()
    address, key = client.put({"some": "data"})

    with pytest.raises(ValueError):
        client.get(address, key, mask={"invalid": "mask"})


def test_retrieve_data_with_invalid_key_raises():
    client = InProcessUpdateDataClient()
    with pytest.raises(ValueError):
        client.get(address="", key="invalid", mask=None)


def test_additional_services_are_not_supported():
    with pytest.raises(ValueError, match="additional"):
        InProcessSimulationRunner(
            {"additional": ServiceInfo("additional", daemon=False, cls=Service)},
            settings=Settings(),
            schema=AttributeSchema(),
            strategies=[],
        )
