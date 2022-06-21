import pytest

from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.models.traffic_assignment_calculation.model import Model
from movici_simulation_core.testing.helpers import assert_dataset_dicts_equal
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def model_name():
    return "test_traffic_assignment_calculation"


@pytest.fixture
def global_schema(global_schema: AttributeSchema):
    global_schema.add_attributes(Model.get_schema_attributes())
    return global_schema


@pytest.fixture
def legacy_model_config(model_name, road_network_name):
    return {
        "name": model_name,
        "type": "traffic_assignment_calculation",
        "vdf_alpha": 0.15,
        "roads": [road_network_name],
        "waterways": [],
        "tracks": [],
    }


@pytest.fixture
def model_config(model_name, road_network_name):
    return {
        "name": model_name,
        "type": "traffic_assignment_calculation",
        "vdf_alpha": 0.15,
        "dataset": road_network_name,
        "modality": "roads",
    }


class TestTrafficAssignmentRoads:
    @pytest.fixture(params=["road_network_for_traffic", "road_network_for_traffic_with_line3d"])
    def init_data(
        self,
        request,
        road_network_name,
    ):
        road_network = request.getfixturevalue(request.param)

        return [
            {"name": road_network_name, "data": road_network},
        ]

    @pytest.fixture
    def model_config(self, model_name, road_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "vdf_alpha": 0.15,
            "dataset": road_network_name,
            "modality": "roads",
        }

    def test_traffic_assignment_roads(
        self, get_entity_update, config, model_name, road_network_name, time_scale, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[0, 20, 0], [5, 0, 0], [0, 100, 0]],
                                "transport.cargo_demand": [
                                    [0, 10, 10],
                                    [10, 0, 10],
                                    [10, 10, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [
                                    [0, 10, 0],
                                    [2.5, 0, 0],
                                    [0, 50, 0],
                                ],
                                "transport.cargo_demand": [
                                    [0, 5, 5],
                                    [5, 0, 5],
                                    [5, 5, 0],
                                ],
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_vehicle_flow": [4.1667, 20, 120, 0.8333],
                                "transport.cargo_vehicle_flow": [25, 30, 30, 5],
                                "transport.delay_factor": [1.171, 1.0527, 24.5561, 1.171],
                                "transport.volume_to_capacity_ratio": [
                                    1.0333,
                                    0.77,
                                    3.54,
                                    1.0333,
                                ],
                                "transport.passenger_car_unit": [51.6667, 77, 177, 10.3333],
                                "transport.average_time": [
                                    0.4216,
                                    0.3032,
                                    4.4203,
                                    0.4216,
                                ],
                            },
                        },
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_vehicle_flow": [2.0834, 10, 60, 0.4167],
                                "transport.cargo_vehicle_flow": [12.5, 15, 15, 2.5],
                                "transport.delay_factor": [1.011, 1.003, 2.472, 1.011],
                                "transport.volume_to_capacity_ratio": [
                                    0.5167,
                                    0.385,
                                    1.77,
                                    0.5167,
                                ],
                                "transport.passenger_car_unit": [25.8334, 38.5, 88.5, 5.1667],
                                "transport.average_time": [0.3639, 0.289, 0.445, 0.3639],
                            },
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


class TestTrafficAssignmentWaterways:
    @pytest.fixture
    def init_data(self, water_network_name, water_network_for_traffic):
        return [
            {"name": water_network_name, "data": water_network_for_traffic},
        ]

    @pytest.fixture
    def model_config(self, model_name, water_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "vdf_alpha": 0.15,
            "dataset": water_network_name,
            "modality": "waterways",
        }

    def test_traffic_assignment_waterways(
        self, get_entity_update, config, model_name, water_network_name, time_scale, global_schema
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[0, 20, 0], [5, 0, 0], [0, 100, 0]],
                                "transport.cargo_demand": [
                                    [0, 10, 10],
                                    [10, 0, 10],
                                    [10, 10, 0],
                                ],
                            }
                        }
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [
                                    [0, 10, 0],
                                    [2.5, 0, 0],
                                    [0, 50, 0],
                                ],
                                "transport.cargo_demand": [
                                    [0, 5, 5],
                                    [5, 0, 5],
                                    [5, 5, 0],
                                ],
                            }
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        water_network_name: {
                            "waterway_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_vehicle_flow": [5, 20, 120, 0],
                                "transport.cargo_vehicle_flow": [30, 30, 30, 0],
                                "transport.delay_factor": [1.0, 5.1547, 1, 1],
                                "transport.volume_to_capacity_ratio": [
                                    0,
                                    0.77,
                                    0,
                                    0,
                                ],
                                "transport.passenger_car_unit": [62, 77, 177, 0],
                                "transport.average_time": [
                                    0.3600,
                                    7115.0348,
                                    1.1800,
                                    1e6,
                                ],
                            },
                        },
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "waterway_segment_entities": {
                                "id": [101, 102, 103],
                                "transport.passenger_vehicle_flow": [2.5, 10, 60],
                                "transport.cargo_vehicle_flow": [15.0, 15, 15],
                                "transport.delay_factor": [
                                    None,
                                    1.1392,
                                    None,
                                ],
                                "transport.volume_to_capacity_ratio": [
                                    None,
                                    0.385,
                                    None,
                                ],
                                "transport.passenger_car_unit": [31, 38.5, 88.5],
                                "transport.average_time": [
                                    None,
                                    1572.3614,
                                    None,
                                ],
                            },
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
            rtol=0.01,
            global_schema=global_schema,
        )


class TestRoadLinksChanges:
    @pytest.fixture()
    def init_data(
        self,
        road_network_for_traffic,
        road_network_name,
    ):

        return [
            {"name": road_network_name, "data": road_network_for_traffic},
        ]

    @pytest.fixture
    def model_config(self, model_name, road_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "vdf_alpha": 0.15,
            "dataset": road_network_name,
            "modality": "roads",
        }

    @pytest.fixture
    def tester_with_base_result(self, init_data, model_config, global_schema, road_network_name):
        inst = Model(model_config)
        tester = ModelTester(inst, schema=global_schema)
        for dataset in init_data:
            tester.add_init_data(dataset["name"], dataset["data"])
        tester.initialize()
        result, _ = tester.update(
            0,
            {
                road_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.passenger_demand": [[0, 20, 0], [5, 0, 0], [0, 100, 0]],
                        "transport.cargo_demand": [
                            [0, 10, 10],
                            [10, 0, 10],
                            [10, 10, 0],
                        ],
                    },
                }
            },
        )
        return tester, result

    @pytest.fixture
    def tester(self, tester_with_base_result):
        return tester_with_base_result[0]

    @pytest.fixture
    def road_segment_data(self, road_network_name):
        def _inner(entity_content):
            return {
                road_network_name: {
                    "road_segment_entities": entity_content,
                },
            }

        return _inner

    def test_base_result(self, road_segment_data, tester_with_base_result):
        _, result = tester_with_base_result
        assert_dataset_dicts_equal(
            result,
            road_segment_data(
                {
                    "id": [101, 102, 103, 104],
                    "transport.passenger_vehicle_flow": [4.1667, 20, 120, 0.8333],
                    "transport.cargo_vehicle_flow": [25, 30, 30, 5],
                    "transport.delay_factor": [1.171, 1.0527, 24.5561, 1.171],
                    "transport.volume_to_capacity_ratio": [
                        1.0333,
                        0.77,
                        3.54,
                        1.0333,
                    ],
                    "transport.passenger_car_unit": [51.6667, 77, 177, 10.3333],
                    "transport.average_time": [
                        0.4216,
                        0.3032,
                        4.4203,
                        0.4216,
                    ],
                }
            ),
            rtol=0.01,
        )

    def test_roads_capacity_changes(self, road_segment_data, tester: ModelTester):
        result, _ = tester.update(
            0,
            road_segment_data(
                {
                    "id": [104],
                    "transport.capacity.hours": [5],
                }
            ),
        )
        assert_dataset_dicts_equal(
            result,
            road_segment_data(
                {
                    "id": [101, 104],
                    "transport.passenger_vehicle_flow": [4.5455, 0.4545],
                    "transport.cargo_vehicle_flow": [27.2727, 2.7278],
                    "transport.delay_factor": [1.2422, 1.2422],
                    "transport.volume_to_capacity_ratio": [1.1273, 1.1273],
                    "transport.passenger_car_unit": [56.3636, 5.6364],
                    "transport.average_time": [0.4472, 0.4472],
                }
            ),
            rtol=0.01,
        )

    def test_road_max_speed_changes(self, tester, road_segment_data):
        result, _ = tester.update(
            0,
            road_segment_data(
                {
                    "id": [104],
                    "transport.max_speed": [1],
                }
            ),
        )
        assert_dataset_dicts_equal(
            result,
            road_segment_data(
                {
                    "id": [101, 104],
                    "transport.passenger_vehicle_flow": [5.0, 0.0],
                    "transport.cargo_vehicle_flow": [30.0, 0.0],
                    "transport.delay_factor": [1.35, 1.0],
                    "transport.volume_to_capacity_ratio": [1.24, 0.0],
                    "transport.passenger_car_unit": [62.0, 0.0],
                    "transport.average_time": [0.487, 0.998],
                }
            ),
            rtol=0.01,
        )

    def test_road_layout_changes(self, tester, road_segment_data):
        result, _ = tester.update(
            0,
            road_segment_data(
                {
                    "id": [104],
                    "transport.layout": [[0, 0, 0, 0]],
                }
            ),
        )
        assert_dataset_dicts_equal(
            result,
            road_segment_data(
                {
                    "id": [101, 104],
                    "transport.passenger_vehicle_flow": [5.0, 0.0],
                    "transport.cargo_vehicle_flow": [30.0, 0.0],
                    "transport.delay_factor": [1.355, 1.355],
                    "transport.volume_to_capacity_ratio": [1.24, 1.24],
                    "transport.passenger_car_unit": [62.0, 0.0],
                    "transport.average_time": [0.487, 0.487],
                }
            ),
            atol=0.01,
        )


class BaseTestTrafficAssignmentRailways:
    @pytest.fixture()
    def init_data(self, railway_network_name, railway_network_for_traffic):

        return [
            {"name": railway_network_name, "data": railway_network_for_traffic},
        ]

    @pytest.fixture
    def model_config(self, model_name, railway_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "vdf_alpha": 0.15,
            "dataset": railway_network_name,
            "modality": "tracks",
        }

    @pytest.fixture
    def tester(self, init_data, model_config, global_schema):
        inst = Model(model_config)
        rv = ModelTester(inst, schema=global_schema)
        for dataset in init_data:
            rv.add_init_data(dataset["name"], dataset["data"])
        return rv


class TestRailwayAssignment(BaseTestTrafficAssignmentRailways):
    def test_with_track_network(self, tester: ModelTester, railway_network_name):
        tester.initialize()
        result, _ = tester.update(
            0,
            {
                railway_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.passenger_demand": [
                            [0, 0, 10],
                            [0, 0, 5],
                            [0, 0, 0],
                        ],
                        "transport.cargo_demand": [
                            [0, 0, 1],
                            [0, 0, 0],
                            [0, 0, 0],
                        ],
                    },
                }
            },
        )
        result = result[railway_network_name]["track_segment_entities"]
        assert_dataset_dicts_equal(
            result,
            {
                "id": [101, 102, 103, 104, 105],
                "transport.passenger_flow": [10.0, 5.0, 15.0, 0.0, 0.0],
                "transport.cargo_flow": [1.0, 0.0, 1.0, 0.0, 0.0],
            },
        )


class TestRailwayPassengerAssignment(BaseTestTrafficAssignmentRailways):
    @pytest.fixture
    def model_config(self, model_name, railway_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "modality": "passenger_tracks",
            "dataset": railway_network_name,
        }

    def test_passenger_assignment_only(self, tester: ModelTester, railway_network_name):
        tester.initialize()
        result, _ = tester.update(
            0,
            {
                railway_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.passenger_demand": [
                            [0, 0, 10],
                            [0, 0, 5],
                            [0, 0, 0],
                        ],
                        "transport.cargo_demand": [
                            [0, 0, 1],
                            [0, 0, 0],
                            [0, 0, 0],
                        ],
                    },
                }
            },
        )
        result = result[railway_network_name]["track_segment_entities"]
        assert_dataset_dicts_equal(
            result,
            {
                "id": [101, 102, 103, 104, 105],
                "transport.passenger_flow": [10.0, 5.0, 15.0, 0.0, 0.0],
                "transport.passenger_average_time": [1.41 / 2, 1.41 / 2, 1.0, 1.41 / 2, 1.41 / 2],
            },
            atol=1e-2,
        )


class TestRailwayCargoAssignment(BaseTestTrafficAssignmentRailways):
    @pytest.fixture
    def model_config(self, model_name, railway_network_name):
        return {
            "name": model_name,
            "type": "traffic_assignment_calculation",
            "modality": "cargo_tracks",
            "dataset": railway_network_name,
        }

    def test_cargo_assignment_only(self, tester: ModelTester, railway_network_name):
        tester.initialize()
        result, _ = tester.update(
            0,
            {
                railway_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.cargo_demand": [
                            [0, 0, 10],
                            [0, 0, 5],
                            [0, 0, 0],
                        ],
                        "transport.passenger_demand": [
                            [0, 0, 1],
                            [0, 0, 0],
                            [0, 0, 0],
                        ],
                    },
                }
            },
        )
        result = result[railway_network_name]["track_segment_entities"]
        assert_dataset_dicts_equal(
            result,
            {
                "id": [101, 102, 103, 104, 105],
                "transport.cargo_flow": [10.0, 5.0, 15.0, 0.0, 0.0],
                "transport.cargo_average_time": [1.41, 1.41, 2.0, 1.41, 1.41],
            },
            atol=1e-2,
        )

    def test_assigment_with_non_cargo_tracks(self, tester: ModelTester, railway_network_name):
        tester.initialize()
        result, _ = tester.update(
            0,
            {
                railway_network_name: {
                    "virtual_node_entities": {
                        "id": [10, 11, 12],
                        "transport.cargo_demand": [
                            [0, 0, 10],
                            [0, 0, 5],
                            [0, 0, 0],
                        ],
                        "transport.passenger_demand": [
                            [0, 0, 1],
                            [0, 0, 0],
                            [0, 0, 0],
                        ],
                    },
                    "track_segment_entities": {
                        "id": [103],
                        "transport.cargo_allowed": [False],
                    },
                }
            },
        )
        result = result[railway_network_name]["track_segment_entities"]
        assert_dataset_dicts_equal(
            result,
            {
                "id": [101, 102, 103, 104, 105],
                "transport.cargo_flow": [10.0, 5.0, 0.0, 15.0, 15.0],
                "transport.cargo_average_time": [1.41, 1.41, 1e9, 1.41, 1.41],
            },
            atol=1e-2,
        )


def test_convert_legacy_model_config(legacy_model_config, model_config):
    del model_config["name"]
    del model_config["type"]
    assert Model(legacy_model_config).config == model_config
