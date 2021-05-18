import pytest

from model_engine import testing
from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.models.traffic_assignment_calculation.model import Model


@pytest.fixture
def model_name():
    return "test_traffic_assignment_calculation"


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
            "roads": [road_network_name],
            "waterways": [],
            "tracks": [],
        }

    def test_traffic_assignment_roads(
        self,
        get_entity_update,
        config,
        model_name,
        road_network_name,
        time_scale,
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
                {"time": 1, "data": {}},
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
                                "traffic_properties": {
                                    "average_time": [
                                        0.4216,
                                        0.3032,
                                        4.4203,
                                        0.4216,
                                    ],
                                },
                            },
                        },
                    },
                },
                {"time": 1, "data": {}},
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
                                "traffic_properties": {
                                    "average_time": [0.3639, 0.289, 0.445, 0.3639],
                                },
                            },
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=model_factory(Model),
            name=model_name,
            scenario=scenario,
            atol=0.01,
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
            "roads": [],
            "waterways": [water_network_name],
            "tracks": [],
        }

    def test_traffic_assignment_waterways(
        self,
        get_entity_update,
        config,
        model_name,
        water_network_name,
        time_scale,
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
                {"time": 1, "data": {}},
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
                                "transport.passenger_vehicle_flow": [4.1667, 20, 120, 0.8333],
                                "transport.cargo_vehicle_flow": [25, 30, 30, 5],
                                "transport.delay_factor": [1.171, 1.0527, 24.5561, 1.171],
                                "transport.volume_to_capacity_ratio": [
                                    1.03333,
                                    0.77,
                                    3.54,
                                    1.03333,
                                ],
                                "transport.passenger_car_unit": [51.6667, 77, 177, 10.3333],
                                "traffic_properties": {
                                    "average_time": [
                                        0.4216,
                                        0.3032,
                                        4.4203,
                                        0.4216,
                                    ],
                                },
                            },
                        },
                    },
                },
                {"time": 1, "data": {}},
                {
                    "time": 2,
                    "data": {
                        water_network_name: {
                            "waterway_segment_entities": {
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
                                "traffic_properties": {
                                    "average_time": [0.3639, 0.289, 0.445, 0.3639],
                                },
                            },
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=model_factory(Model),
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )


class TestRoadsCapacityChanges:
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
            "roads": [road_network_name],
            "waterways": [],
            "tracks": [],
        }

    def test_roads_capacity_changes(
        self,
        get_entity_update,
        config,
        model_name,
        road_network_name,
        time_scale,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [104],
                                "transport.capacity.hours": [0],
                            },
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
                },
                {
                    "time": 1,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [104],
                                "transport.capacity.hours": [10],
                            },
                        }
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [104],
                                "transport.capacity.hours": [5],
                            },
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
                                "transport.passenger_vehicle_flow": [5, 20, 120, 0],
                                "transport.cargo_vehicle_flow": [30, 30, 30, 0],
                                "transport.delay_factor": [1.3546, 1.0527, 24.5561, 1],
                                "transport.volume_to_capacity_ratio": [
                                    1.24,
                                    0.77,
                                    3.54,
                                    0,
                                ],
                                "transport.passenger_car_unit": [62, 77, 177, 0],
                                "traffic_properties": {
                                    "average_time": [
                                        0.4877,
                                        0.3032,
                                        4.4203,
                                        1e9,
                                    ],
                                },
                            },
                        },
                    },
                },
                {
                    "time": 1,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 104],
                                "transport.passenger_vehicle_flow": [4.1667, 0.8333],
                                "transport.cargo_vehicle_flow": [25, 5],
                                "transport.delay_factor": [1.171, 1.171],
                                "transport.volume_to_capacity_ratio": [
                                    1.0333,
                                    1.0333,
                                ],
                                "transport.passenger_car_unit": [51.6667, 10.3333],
                                "traffic_properties": {
                                    "average_time": [
                                        0.4216,
                                        0.4216,
                                    ],
                                },
                            },
                        },
                    },
                },
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 104],
                                "transport.passenger_vehicle_flow": [4.5455, 0.4545],
                                "transport.cargo_vehicle_flow": [27.2727, 2.7278],
                                "transport.delay_factor": [1.2422, 1.2422],
                                "transport.volume_to_capacity_ratio": [
                                    1.1273,
                                    1.1273,
                                ],
                                "transport.passenger_car_unit": [56.3636, 5.6364],
                                "traffic_properties": {
                                    "average_time": [0.4472, 0.4472],
                                },
                            },
                        },
                    },
                },
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=model_factory(Model),
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )
