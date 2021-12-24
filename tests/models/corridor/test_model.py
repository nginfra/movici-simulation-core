import pytest

from movici_simulation_core.models.corridor.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def model_name():
    return "test_corridor"


@pytest.fixture(params=["road_network_for_traffic", "road_network_for_traffic_with_line3d"])
def init_data(request, road_network_name, corridor_dataset_name, corridor_dataset):
    road_network = request.getfixturevalue(request.param)

    return [
        {"name": road_network_name, "data": road_network},
        {"name": corridor_dataset_name, "data": corridor_dataset},
    ]


@pytest.fixture
def model_config(model_name, road_network_name, corridor_dataset_name):
    return {
        "name": model_name,
        "type": "corridor",
        "corridors": [corridor_dataset_name],
        "roads": [road_network_name],
        "waterways": [],
        "tracks": [],
        "cargo_pcu": 2.0,
        "publish_corridor_geometry": True,
    }


class TestCorridor:
    def test_corridor(
        self,
        get_entity_update,
        config,
        model_name,
        road_network_name,
        corridor_dataset_name,
        global_schema,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_vehicle_flow": [5, 15, 30, 40],
                                "transport.cargo_vehicle_flow": [4, 4, 3, 1],
                                "transport.average_time": [10, 11, 12, 13],
                                "transport.passenger_car_unit": [
                                    13,
                                    23,
                                    36,
                                    42,
                                ],  # assume cargo pcu=2
                                "transport.co2_emission.hours": [100, 100, 100, 100],
                                "transport.nox_emission.hours": [100, 200, 300, 400],
                                "transport.energy_consumption.hours": [5, 5, 4, 5],
                            },
                            "virtual_node_entities": {
                                "id": [10, 11, 12],
                                "transport.passenger_demand": [[0, 5, 10], [5, 0, 1], [0, 5, 0]],
                                "transport.cargo_demand": [
                                    [0, 2, 1],
                                    [0, 0, 0],
                                    [0, 0, 0],
                                ],
                            },
                        }
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [102, 103],
                                "transport.passenger_vehicle_flow": [2, 2],
                                "transport.cargo_vehicle_flow": [1, 0],
                                "transport.average_time": [10, 40],
                                "transport.passenger_car_unit": [
                                    4,
                                    2,
                                ],
                                "transport.co2_emission.hours": [100, 100],
                                "transport.nox_emission.hours": [200, 400],
                                "transport.energy_consumption.hours": [10, 4],
                            },
                            "virtual_node_entities": {
                                "id": [10],
                                "transport.passenger_demand": [[0, 2, 0]],
                                "transport.cargo_demand": [[0, 0, 1]],
                            },
                        }
                    },
                },
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        corridor_dataset_name: {
                            "corridor_entities": {
                                "id": [1, 2],
                                "transport.passenger_vehicle_flow": [5, 15],
                                "transport.cargo_vehicle_flow": [2, 3],
                                "transport.average_time": [23.0, 16.1429],
                                "transport.passenger_car_unit": [9, 21],
                                "transport.co2_emission.hours": [64.1304, 116.3044],
                                "transport.nox_emission.hours": [153.2609, 257.6087],
                                "transport.energy_consumption.hours": [2.9565, 5.5652],
                                "transport.volume_to_capacity_ratio": [0.72, 0.72],
                                "transport.delay_factor": [49.1420, 49.1420],
                                "geometry.linestring_2d": [
                                    [
                                        [97700, 434000],
                                        [97702, 434000],
                                        [97704, 434000],
                                        [97701, 434000],
                                    ],
                                    [
                                        [97700, 434000],
                                        [97702, 434000],
                                        [97704, 434000],
                                        [97701, 434000],
                                    ],
                                ],
                            },
                        }
                    },
                },
                {"time": 1, "data": None},
                {
                    "time": 2,
                    "data": {
                        corridor_dataset_name: {
                            "corridor_entities": {
                                "id": [1, 2],
                                "transport.passenger_vehicle_flow": [2, 2],
                                "transport.cargo_vehicle_flow": [0, 1],
                                "transport.average_time": [50, 30],
                                "transport.passenger_car_unit": [2, 4],
                                "transport.co2_emission.hours": [150, 200],
                                "transport.nox_emission.hours": [500, 600],
                                "transport.energy_consumption.hours": [9, 14],
                                "transport.volume_to_capacity_ratio": [0.04, 0.04],
                                "transport.delay_factor": [106.8305, 106.8305],
                            },
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
            rtol=0.01,
            global_schema=global_schema,
        )
