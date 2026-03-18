from movici_simulation_core.simulation.synchronous import SynchronousUpdateDataClient


def test_store_and_retrieve_updates():
    client = SynchronousUpdateDataClient()
    address, key = client.put({"some": "data"})
    assert client.get(address, key, mask=None) == {"some": "data"}


def test_retrieve_update_with_mask():
    client = SynchronousUpdateDataClient()
    address, key = client.put({"some": "data", "other": "data"})
    assert client.get(address, key, mask={"some": None}) == {"some": "data"}
