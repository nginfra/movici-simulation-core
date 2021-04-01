import pytest

from ..conftest import get_dataset


@pytest.fixture
def water_network(water_network_name):
    return get_dataset(
        name=water_network_name,
        ds_type="random_type",
        data={
            "water_pipe_entities": {
                "id": [1, 2, 3],
                "reference": ["Water1", "Water2", "Water3"],
                "shape_properties": {
                    "linestring_3d": [
                        [[0.0, 0, 0.0], [1.0, 0, 0]],
                        [[1.0, 1.0, 1.0], [-1.0, 1.0, -1.0]],
                        [[-100, 0, 0], [-101, 0, 0]],
                    ]
                },
            }
        },
    )


@pytest.fixture
def mv_network(mv_network_name):
    return get_dataset(
        name=mv_network_name,
        ds_type="mv_network",
        general={"enum": {"label": ["distribution", "industrial"]}},
        data={
            "electrical_node_entities": {
                "id": [0, 2, 4, 6, 8],
                "reference": ["Mv0", "Mv2", "Mv4", "Mv6", "Mv8"],
                "labels": [[1], [0], [0], [0], [0]],
                "point_properties": {
                    "position_x": [1.5, 0.5, 0.5, 0.0, 1.5],
                    "position_y": [0.4, 0.0, 1.5, 1.0, 0.5],
                    "position_z": [0.0, 1.0, None, None, 0.0],
                },
            },
            "electrical_load_entities": {
                "id": [20, 10, 30, 40, 15],
                "oneside_element_properties": {"node_id": [4, 2, 6, 8, 0]},
                "operation_status_properties": {
                    "is_working_properly": [True, True, True, True, True]
                },
            },
        },
    )
