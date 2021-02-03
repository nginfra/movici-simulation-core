import collections
from typing import Iterable, Optional, Dict

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
    knotweed_dataset_name,
    knotweed_dataset,
    overlap_dataset_name,
    overlap_dataset,
):
    return [
        {"name": water_network_name, "data": water_network},
        {"name": road_network_name, "data": road_network},
        {"name": mv_network_name, "data": mv_network},
        {"name": knotweed_dataset_name, "data": knotweed_dataset},
        {"name": overlap_dataset_name, "data": overlap_dataset},
    ]


@pytest.fixture
def model_config(
    model_name, overlap_dataset_name, water_network_name, road_network_name, mv_network_name
):
    return {
        "name": model_name,
        "type": "overlap_status",
        "from_entity_group": [
            (water_network_name, "water_pipe_entities"),
        ],
        "from_geometry_type": "line",
        "from_check_status_property": ("operation_status_properties", "is_working_properly"),
        "to_entity_groups": [
            (mv_network_name, "electrical_node_entities"),
            (road_network_name, "road_segment_entities"),
        ],
        "to_geometry_types": [
            "point",
            "line",
        ],
        "to_check_status_properties": [
            ("operation_status_properties", "is_working_properly"),
            ("operation_status_properties", "is_working_properly"),
        ],
        "output_dataset": [overlap_dataset_name],
        "distance_threshold": 0.1,
    }


class TestOverlapStatus:
    def test_overlap(
        self,
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
                    "time": 1 * time_scale,
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
                    "time": 2 * time_scale,
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
                    "time": 3 * time_scale,
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
                    "time": 4 * time_scale,
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
                    "time": 5 * time_scale,
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
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                            ),
                        },
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": {},
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.0],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [3],
                                    "from_reference": [
                                        "Water1",
                                    ],
                                    "to_reference": ["Road3"],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        road_network_name,
                                    ],
                                },
                            }
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
                    "time": 3 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [2],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.5],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [2],
                                    "from_reference": [
                                        "Water1",
                                    ],
                                    "to_reference": ["Mv2"],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        mv_network_name,
                                    ],
                                },
                            }
                        },
                    },
                },
                {
                    "time": 4 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                properties=[False],
                            ),
                        },
                    },
                },
                {
                    "time": 5 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [2],
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

    def test_overlap_without_reference(
        self,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        mv_network_name,
        road_network_name,
        water_network,
        mv_network,
        road_network,
        time_scale,
    ):

        del water_network["data"]["water_pipe_entities"]["reference"]
        del road_network["data"]["road_segment_entities"]["reference"]
        del mv_network["data"]["electrical_node_entities"]["reference"]

        config["config"]["models"][0][
            "display_name_template"
        ] = "{from_dataset_name} {from_id} {to_dataset_name} {to_id}"

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
                    "time": 1 * time_scale,
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
                    "time": 2 * time_scale,
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
                    "time": 3 * time_scale,
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
                    "time": 4 * time_scale,
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
                    "time": 5 * time_scale,
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
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                            ),
                        },
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": {},
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.0],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"{water_network_name} 1 {road_network_name} 3",
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [3],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        road_network_name,
                                    ],
                                },
                            }
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
                    "time": 3 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [2],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.5],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"{water_network_name} 1 {mv_network_name} 2",
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [2],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        mv_network_name,
                                    ],
                                },
                            }
                        },
                    },
                },
                {
                    "time": 4 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                properties=[False],
                            ),
                        },
                    },
                },
                {
                    "time": 5 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [2],
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

    def test_overlap_without_status_property(
        self,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        mv_network_name,
        road_network_name,
        time_scale,
    ):
        del config["config"]["models"][0]["from_check_status_property"]
        config["config"]["models"][0]["to_check_status_properties"][0] = None
        config["config"]["models"][0]["to_check_status_properties"][1] = (None, None)

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
                    "time": 1 * time_scale,
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
                    "time": 2 * time_scale,
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
                    "time": 3 * time_scale,
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
                    "time": 4 * time_scale,
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
                    "time": 5 * time_scale,
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
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[True, True, False],
                            ),
                        },
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1, 2, 3, 4, 5],
                                "overlap.active": [True, True, True, True, True],
                                "point_properties": {
                                    "position_x": [0.5, 0.0, 0.0, 1.025, 1.0],
                                    "position_y": [0.0, 1.0, 0.0, 1.0, 1.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {mv_network_name} reference Mv6",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road2",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1, 2, 1, 2, 2],
                                    "to_id": [2, 6, 3, 2, 3],
                                    "from_reference": [
                                        "Water1",
                                        "Water2",
                                        "Water1",
                                        "Water2",
                                        "Water2",
                                    ],
                                    "to_reference": ["Mv2", "Mv6", "Road3", "Road2", "Road3"],
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
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": {},
                },
                {
                    "time": 2 * time_scale,
                    "data": {},
                },
                {
                    "time": 3 * time_scale,
                    "data": {},
                },
                {
                    "time": 4 * time_scale,
                    "data": {},
                },
                {
                    "time": 5 * time_scale,
                    "data": {},
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

    def test_overlap_status_starting_null(
        self,
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
                    "data": {},
                },
                {
                    "time": 1 * time_scale,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1, 2, 3],
                                properties=[True, False, False],
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
                    "time": 2 * time_scale,
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
                    "time": 3 * time_scale,
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
                    "time": 4 * time_scale,
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
                    "time": 5 * time_scale,
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
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                            ),
                        },
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": {},
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.0],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [3],
                                    "from_reference": [
                                        "Water1",
                                    ],
                                    "to_reference": ["Road3"],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        road_network_name,
                                    ],
                                },
                            }
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
                    "time": 3 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [2],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.5],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [2],
                                    "from_reference": [
                                        "Water1",
                                    ],
                                    "to_reference": ["Mv2"],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        mv_network_name,
                                    ],
                                },
                            }
                        },
                    },
                },
                {
                    "time": 4 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                properties=[False],
                            ),
                        },
                    },
                },
                {
                    "time": 5 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [2],
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

    def test_overlap_with_polygons(
        self,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        knotweed_dataset_name,
        time_scale,
    ):

        config["config"]["models"][0]["to_entity_groups"] = [
            (knotweed_dataset_name, "knotweed_entities")
        ]
        config["config"]["models"][0]["to_geometry_types"] = ["polygon"]
        del config["config"]["models"][0]["to_check_status_properties"]

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
                    },
                },
                {
                    "time": 1 * time_scale,
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
                    "time": 2 * time_scale,
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
                        water_network_name: {
                            "water_pipe_entities": get_overlap_update(
                                [1, 2, 3],
                                properties=[False, False, False],
                            ),
                        },
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "point_properties": {
                                    "position_x": [0.0],
                                    "position_y": [0.0],
                                },
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {knotweed_dataset_name} reference Knotweed1",  # noqa: E501
                                ],
                                "connection_properties": {
                                    "from_id": [1],
                                    "to_id": [0],
                                    "from_reference": [
                                        "Water1",
                                    ],
                                    "to_reference": ["Knotweed1"],
                                    "from_dataset": [
                                        water_network_name,
                                    ],
                                    "to_dataset": [
                                        knotweed_dataset_name,
                                    ],
                                },
                            }
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
                    "time": 2 * time_scale,
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


def get_entity_update(
    ids: Iterable, properties: Iterable, key_name: str, component_name: Optional[str] = None
) -> Dict:
    if not isinstance(ids, collections.Iterable):
        ids = [ids]
    entities = {"id": list(ids)}
    for key, prop, component in [
        (key_name, properties, component_name),
    ]:
        if prop is not None:
            if not isinstance(prop, collections.Iterable):
                prop = [prop for _ in ids]
            if component is None:
                entities[key] = prop
            else:
                if component not in entities:
                    entities[component] = {}
                entities[component][key] = prop

    return entities


def get_overlap_update(ids: Iterable, properties: Iterable) -> Dict:
    return get_entity_update(ids, properties, component_name=None, key_name="overlap.active")
