import pytest
from model_engine import testing
from movici_simulation_core.models.overlap_status.model import Model


@pytest.fixture
def time_scale():
    return 86400


@pytest.fixture
def model_name():
    return "test_overlap_status"


@pytest.fixture
def config(
    model_config,
    init_data,
    time_scale,
):
    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 730,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture
def init_data(
    water_network_name,
    water_network,
    road_network_name,
    road_network,
    mv_network_name,
    mv_network,
    overlap_dataset_name,
    overlap_dataset,
):
    return [
        {"name": water_network_name, "data": water_network},
        {"name": road_network_name, "data": road_network},
        {"name": mv_network_name, "data": mv_network},
        {"name": overlap_dataset_name, "data": overlap_dataset},
    ]


@pytest.fixture
def model_config(
    model_name, overlap_dataset_name, water_network_name, road_network_name, mv_network_name
):
    return {
        "name": model_name,
        "type": "overlap_status",
        "from_dataset": [(water_network_name, "water_pipe_entities")],
        "from_dataset_geometry": "lines",
        "to_points_datasets": [
            (mv_network_name, "electrical_node_entities"),
        ],
        "to_lines_datasets": [
            (road_network_name, "road_segment_entities"),
        ],
        "output_dataset": [overlap_dataset_name],
        "check_overlapping_from": (
            "operation_status_properties",
            "is_working_properly",
        ),  # optional
        "check_overlapping_to": (
            "operation_status_properties",
            "is_working_properly",
        ),  # optional
        "distance_threshold": 0.1,
    }


class TestOverlapStatus:
    def test_overlap(
        self,
        get_entity_update,
        get_overlap_update,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        mv_network_name,
        road_network_name,
        time_scale,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                properties=[False, False, False, False, False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
                {
                    "time": 1,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1],
                                properties=[True],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [3],
                                properties=[True],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
                {
                    "time": 3,
                    "data": {
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [2],
                                properties=[True],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
                {
                    "time": 4,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [3],
                                properties=[False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
                {
                    "time": 5,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1],
                                properties=[False],
                                component_name="operation_status_properties",
                                key_name="is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1, 2, 3, 4, 5],
                                "overlap.active": [False, False, False, False, False],
                                "point_properties": {
                                    "position_x": [0.5, 0.0, 0.0, 1.0, 1.025],
                                    "position_y": [0.0, 1.0, 0.0, 1.0, 1.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {mv_network_name} reference Mv6",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road3",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road2",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1, 2, 1, 2, 2],
                                    "to_id": [2, 6, 3, 3, 2],
                                    "from_reference": [
                                        "Water1",
                                        "Water2",
                                        "Water1",
                                        "Water2",
                                        "Water2",
                                    ],
                                    "to_reference": ["Mv2", "Mv6", "Road3", "Road3", "Road2"],
                                    "from_dataset": [
                                        water_network_name,
                                        water_network_name,
                                        water_network_name,
                                        water_network_name,
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        mv_network_name,
                                        mv_network_name,
                                        road_network_name,
                                        road_network_name,
                                        road_network_name,
                                    ],
                                },
                            }
                        },
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                            ),
                        },
                    },
                },
                {
                    "time": 1,
                    "data": {},
                },
                {
                    "time": 2,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [3],
                                properties=[True],
                            ),
                        },
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1],
                                properties=[True],
                            ),
                        },
                    },
                },
                {
                    "time": 3,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                properties=[True],
                            ),
                        },
                    },
                },
                {
                    "time": 4,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [3],
                                properties=[False],
                            ),
                        },
                    },
                },
                {
                    "time": 4,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                properties=[False],
                            ),
                        },
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1],
                                properties=[False],
                            ),
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=Model,
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )
