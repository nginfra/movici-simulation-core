from typing import Iterable, Dict

import pytest

from movici_simulation_core.core.schema import AttributeSpec
from movici_simulation_core.models.overlap_status.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def time_scale():
    return 86400


@pytest.fixture
def init_data(
    water_network_name,
    road_network_name,
    mv_network_name,
    knotweed_dataset_name,
    overlap_dataset_name,
    water_network,
    road_network,
    mv_network,
    knotweed_dataset,
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
        "from_check_status_property": (None, "operational.is_working_properly"),
        "to_entity_groups": [
            (mv_network_name, "electrical_node_entities"),
            (road_network_name, "road_segment_entities"),
        ],
        "to_geometry_types": [
            "point",
            "line",
        ],
        "to_check_status_properties": [
            (None, "operational.is_working_properly"),
            (None, "operational.is_working_properly"),
        ],
        "output_dataset": [overlap_dataset_name],
        "distance_threshold": 0.1,
    }


@pytest.fixture
def additional_attributes():
    from movici_simulation_core.core import DataType

    return [
        AttributeSpec("knotweed.stem_density", DataType(float, (), False)),
        AttributeSpec("topology.node_id", data_type=DataType(int, (), False)),
        AttributeSpec(
            "operational.is_working_properly",
            data_type=DataType(bool, (), False),
        ),
    ]


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
        get_entity_update,
        get_overlap_update,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                attributes=[False, False, False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1 * time_scale,
                    "data": None,
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "geometry.x": [0.0],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [3],
                                "connection.from_reference": [
                                    "Water1",
                                ],
                                "connection.to_reference": ["Road3"],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    road_network_name,
                                ],
                            }
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
                                "geometry.x": [0.5],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [2],
                                "connection.from_reference": [
                                    "Water1",
                                ],
                                "connection.to_reference": ["Mv2"],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    mv_network_name,
                                ],
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
                                attributes=[False],
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
                                attributes=[False],
                            ),
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
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
        get_entity_update,
        get_overlap_update,
        global_schema,
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
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                attributes=[False, False, False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1 * time_scale,
                    "data": None,
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "geometry.x": [0.0],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"{water_network_name} 1 {road_network_name} 3",
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [3],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    road_network_name,
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 3 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [2],
                                "overlap.active": [True],
                                "geometry.x": [0.5],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"{water_network_name} 1 {mv_network_name} 2",
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [2],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    mv_network_name,
                                ],
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
                                attributes=[False],
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
                                attributes=[False],
                            ),
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
        )

    def test_overlap_without_status_attribute(
        self,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        mv_network_name,
        road_network_name,
        time_scale,
        get_entity_update,
        global_schema,
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
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                attributes=[False, False, False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
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
                                "overlap.active": [True, True, True, True, True],
                                "geometry.x": [0.5, 0.0, 0.0, 1.025, 1.0],
                                "geometry.y": [0.0, 1.0, 0.0, 1.0, 1.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {mv_network_name} reference Mv6",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road2",  # noqa: E501
                                    f"Overlap from {water_network_name} reference Water2 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection.from_id": [1, 2, 1, 2, 2],
                                "connection.to_id": [2, 6, 3, 2, 3],
                                "connection.from_reference": [
                                    "Water1",
                                    "Water2",
                                    "Water1",
                                    "Water2",
                                    "Water2",
                                ],
                                "connection.to_reference": [
                                    "Mv2",
                                    "Mv6",
                                    "Road3",
                                    "Road2",
                                    "Road3",
                                ],
                                "connection.from_dataset": [
                                    water_network_name,
                                    water_network_name,
                                    water_network_name,
                                    water_network_name,
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    mv_network_name,
                                    mv_network_name,
                                    road_network_name,
                                    road_network_name,
                                    road_network_name,
                                ],
                            }
                        },
                    },
                },
                {
                    "time": 1 * time_scale,
                    "data": None,
                },
                {
                    "time": 2 * time_scale,
                    "data": None,
                },
                {
                    "time": 3 * time_scale,
                    "data": None,
                },
                {
                    "time": 4 * time_scale,
                    "data": None,
                },
                {
                    "time": 5 * time_scale,
                    "data": None,
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
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
        get_entity_update,
        get_overlap_update,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1 * time_scale,
                    "data": {
                        water_network_name: {
                            "water_pipe_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[True, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        road_network_name: {
                            "road_segment_entities": get_entity_update(
                                [1, 2, 3],
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                        mv_network_name: {
                            "electrical_node_entities": get_entity_update(
                                [0, 2, 4, 6, 8],
                                attributes=[False, False, False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {"time": 0, "data": None},
                {
                    "time": 1 * time_scale,
                    "data": None,
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "geometry.x": [0.0],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {road_network_name} reference Road3",  # noqa: E501
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [3],
                                "connection.from_reference": [
                                    "Water1",
                                ],
                                "connection.to_reference": ["Road3"],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    road_network_name,
                                ],
                            }
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
                                "geometry.x": [0.5],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {mv_network_name} reference Mv2",  # noqa: E501
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [2],
                                "connection.from_reference": [
                                    "Water1",
                                ],
                                "connection.to_reference": ["Mv2"],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    mv_network_name,
                                ],
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
                                attributes=[False],
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
                                attributes=[False],
                            ),
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
        )

    def test_overlap_with_polygons(
        self,
        config,
        model_name,
        overlap_dataset_name,
        water_network_name,
        knotweed_dataset_name,
        time_scale,
        get_entity_update,
        get_overlap_update,
        global_schema,
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
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {"time": 0, "data": None},
                {
                    "time": 1 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
                                "geometry.x": [0.0],
                                "geometry.y": [0.0],
                                "display_name": [
                                    f"Overlap from {water_network_name} reference Water1 to {knotweed_dataset_name} reference Knotweed1",  # noqa: E501
                                ],
                                "connection.from_id": [1],
                                "connection.to_id": [0],
                                "connection.from_reference": [
                                    "Water1",
                                ],
                                "connection.to_reference": ["Knotweed1"],
                                "connection.from_dataset": [
                                    water_network_name,
                                ],
                                "connection.to_dataset": [
                                    knotweed_dataset_name,
                                ],
                            }
                        }
                    },
                },
                {
                    "time": 2 * time_scale,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": get_overlap_update(
                                [1],
                                attributes=[False],
                            ),
                        }
                    },
                },
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
        )


class TestOverlapWithoutActualOverlaps:
    @pytest.fixture
    def knotweed_dataset(self, knotweed_dataset):
        knotweed_dataset["data"]["knotweed_entities"]["geometry.polygon"] = [
            [
                [-10000, -10000],
                [-10000, -10001],
                [-10001, -10001],
                [-10001, -10000],
                [-10000, -10000],
            ],
            [
                [-10000, -10000],
                [-10000, -10001],
                [-10001, -10001],
                [-10001, -10000],
                [-10000, -10000],
            ],
        ]
        return knotweed_dataset

    def test_overlap_without_actual_overlap(
        self,
        config,
        model_name,
        water_network_name,
        knotweed_dataset_name,
        time_scale,
        get_entity_update,
        get_overlap_update,
        global_schema,
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
                                attributes=[False, False, False],
                                key_name="operational.is_working_properly",
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
                                attributes=[True],
                                key_name="operational.is_working_properly",
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
                                attributes=[False],
                                key_name="operational.is_working_properly",
                            ),
                        },
                    },
                },
            ],
            "expected_results": [
                {"time": 0, "data": None},
                {"time": 1 * time_scale, "data": None},
                {"time": 2 * time_scale, "data": None},
            ],
        }

        scenario.update(config)
        ModelTester.run_scenario(
            model=Model,
            model_name=model_name,
            scenario=scenario,
            atol=0.01,
            global_schema=global_schema,
        )


@pytest.fixture
def get_overlap_update(get_entity_update):
    def _factory(
        ids: Iterable,
        attributes: Iterable,
    ) -> Dict:
        return get_entity_update(ids, attributes, key_name="overlap.active")

    return _factory
