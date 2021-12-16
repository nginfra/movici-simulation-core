import pytest

from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.models.opportunities.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def init_data(
    road_network_name,
    overlap_dataset_name,
    road_network,
    overlap_dataset,
):
    return [
        {"name": road_network_name, "data": road_network},
        {"name": overlap_dataset_name, "data": overlap_dataset},
    ]


@pytest.fixture
def model_config(model_name, overlap_dataset_name, road_network_name):
    return {
        "name": model_name,
        "type": "opportunity",
        "overlap_dataset": [overlap_dataset_name],
        "opportunity_taken_property": [(None, "maintenance.under_maintenance")],
        "total_length_property": [(None, "maintenance.length")],
        "opportunity_entity": [
            (road_network_name, "road_segment_entities"),
        ],
        "cost_per_meter": [10.0],
    }


@pytest.fixture
def additional_attributes():
    return [AttributeSpec("maintenance.under_maintenance", DataType(bool))]


class TestOpportunity:
    def test_opportunity(
        self,
        config,
        model_name,
        overlap_dataset_name,
        road_network_name,
        time_scale,
        get_entity_update,
        water_network_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
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
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "maintenance.under_maintenance": [False, False, True],
                            }
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "opportunity": [0.0, 0.0, 0.0],
                                "missed_opportunity": [0.0, 0.0, 0.0],
                                "maintenance.length": [0.0, 0.0, 0.0],
                            }
                        }
                    },
                },
                {
                    "time": 1,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [3],
                                "opportunity": [53.154],
                                "maintenance.length": [5.3154],
                            }
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

    def test_missed_opportunity(
        self,
        config,
        model_name,
        overlap_dataset_name,
        road_network_name,
        time_scale,
        get_entity_update,
        water_network_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [True],
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
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "maintenance.under_maintenance": [False, False, False],
                            }
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [False],
                            }
                        },
                    },
                },
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "maintenance.under_maintenance": [False, False, True],
                            }
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "opportunity": [0.0, 0.0, 0.0],
                                "missed_opportunity": [0.0, 0.0, 0.0],
                                "maintenance.length": [0.0, 0.0, 0.0],
                            }
                        }
                    },
                },
                {
                    "time": 1,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [3],
                                "missed_opportunity": [53.154],
                                "opportunity": [53.154],
                            }
                        },
                    },
                },
                {
                    "time": 2,
                    "data": None,
                },
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {"id": [3], "maintenance.length": [5.3154]}
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

    def test_total_length(
        self,
        config,
        model_name,
        overlap_dataset_name,
        road_network_name,
        time_scale,
        get_entity_update,
        water_network_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": None,
                },
                {
                    "time": 1,
                    "data": {
                        overlap_dataset_name: {
                            "overlap_entities": {
                                "id": [1],
                                "overlap.active": [False],
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
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "maintenance.under_maintenance": [False, False, True],
                            }
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1],
                                "maintenance.under_maintenance": [True],
                            }
                        }
                    },
                },
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "maintenance.under_maintenance": [False, True, False],
                            }
                        },
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [1, 2, 3],
                                "opportunity": [0.0, 0.0, 0.0],
                                "missed_opportunity": [0.0, 0.0, 0.0],
                                "maintenance.length": [0.0, 0.0, 0.0],
                            }
                        }
                    },
                },
                {
                    "time": 1,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {"id": [3], "maintenance.length": [5.3154]}
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {"id": [1], "maintenance.length": [1.4142]}
                        },
                    },
                },
                {
                    "time": 3,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {"id": [2], "maintenance.length": [2.0006]}
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
