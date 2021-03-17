import pytest


@pytest.fixture
def road_network(road_network_name):
    return {
        "version": 3,
        "name": road_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "data": {
            "road_segment_entities": {
                "id": [101, 102, 103, 104],
                "reference": ["RS1", "RS102", "RS103", "RS104"],
                "line_properties": {"from_node_id": [1, 0, 1, 0], "to_node_id": [0, 2, 2, 1]},
                "shape_properties": {
                    "linestring_2d": [
                        [[97701, 434000], [97700, 434000]],
                        [[97700, 434000], [97702, 434000]],
                        [[97702, 434000], [97704, 434000], [97700, 434000]],
                        [[97700, 434000], [97700, 434000]],
                    ]
                },
                "transport.direction": [True, True, False, False],
                "transport.max_speed": [10, 25, 100, 10],
                "transport.capacity.hours": [50, 100, 50, 10],
            },
            "road_vertex_entities": {
                "id": [0, 1, 2],
                "reference": ["RN0", "RN1", "RN2"],
                "point_properties": {
                    "position_x": [97700, 97701, 97702],
                    "position_y": [434000, 434000, 434000],
                },
            },
        },
    }


@pytest.fixture
def virtual_nodes_name():
    return "some_virtual_nodes"


@pytest.fixture
def virtual_nodes_dataset(virtual_nodes_name, road_network_name):
    return {
        "version": 3,
        "name": virtual_nodes_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "data": {
            "virtual_node_entities": {
                "id": [10, 11, 12],
                "reference": ["VN1", "VN2", "VN3"],
                "connection_properties": {
                    "to_dataset": [road_network_name, road_network_name, road_network_name],
                    "to_ids": [[0], [1], [2]],
                },
            }
        },
    }
