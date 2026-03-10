import pytest


@pytest.fixture
def corridor_dataset_name():
    return "a_corridor_dataset"


@pytest.fixture
def corridor_dataset(corridor_dataset_name):
    return {
        "version": 3,
        "display_name": "",
        "epsg_code": 28992,
        "name": corridor_dataset_name,
        "type": "corridor",
        "data": {
            "corridor_entities": {
                "id": [1, 2],
                "connection.from_ids": [[10], [10]],
                "connection.to_ids": [[11], [11, 12]],
            }
        },
    }
