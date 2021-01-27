import pytest


@pytest.fixture
def water_network_name():
    return "a_water_network"


@pytest.fixture
def water_network(water_network_name):
    return {
        "version": 3,
        "name": water_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {
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
    }


@pytest.fixture
def mv_network_name():
    return "an_mv_network"


@pytest.fixture
def mv_network(mv_network_name):
    return {
        "version": 3,
        "name": mv_network_name,
        "type": "mv_network",
        "display_name": "",
        "epsg_code": 28992,
        "general": {"enum": {"label": ["distribution", "industrial"]}},
        "data": {
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
    }


@pytest.fixture
def road_network_name():
    return "a_road_network"


@pytest.fixture
def road_network(road_network_name):
    return {
        "version": 3,
        "name": road_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {
            "road_segment_entities": {
                "id": [1, 2, 3],
                "reference": ["Road1", "Road2", "Road3"],
                "shape_properties": {
                    "linestring_3d": [
                        [[0.0, -10.0, 0.0], [1.0, -10.0, 1.0]],
                        [[1.1, 1.0, 1.0], [1.05, 1.0, -1.0]],
                        [[0, 0, 0.0], [0.1, 0.0, -1.0], [1, 1, 1.0], [-0.9, 1, 1.0]],
                    ]
                },
            }
        },
    }


@pytest.fixture
def overlap_dataset_name():
    return "an_overlap_dataset"


@pytest.fixture
def overlap_dataset(overlap_dataset_name):
    return {
        "version": 3,
        "name": overlap_dataset_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {"overlap_entities": {"id": list(range(1, 1000))}},
    }


@pytest.fixture
def knotweed_dataset_name():
    return "a_knotweed_dataset"


@pytest.fixture
def knotweed_dataset(knotweed_dataset_name):
    return {
        "version": 3,
        "name": knotweed_dataset_name,
        "type": "knotweed",
        "display_name": "",
        "epsg_code": 28992,
        "data": {
            "knotweed_entities": {
                "point_properties": {
                    "position_x": [0, 1],
                    "position_y": [0, 1],
                    "position_z": [1.2, 1.2],
                },
                "shape_properties": {
                    "polygon": [
                        [
                            [0, 0],
                            [0, 1],
                            [1, 1],
                            [1, 0],
                            [0, 0],
                        ],
                        [
                            [1, 1],
                            [1, 2],
                            [2, 2],
                            [2, 1],
                            [1, 1],
                        ],
                    ]
                },
                "id": [0, 1],
                "knotweed.stem_density": [80.0, 100.0],
                "reference": ["Knotweed1", "Knotweed2"],
            }
        },
    }
