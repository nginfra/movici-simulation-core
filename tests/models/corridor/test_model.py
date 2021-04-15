import pytest
from model_engine import testing

from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.models.corridor.model import Model


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
    }


class TestCorridor:
    @pytest.mark.xfail
    def test_corridor(
        self,
        get_entity_update,
        config,
        model_name,
        road_network_name,
        corridor_dataset_name,
    ):
        scenario = {
            "updates": [
                {
                    "time": 0,
                    "data": {
                        road_network_name: {
                            "road_segment_entities": {
                                "id": [101, 102, 103, 104],
                                "transport.passenger_flow": [5, 15, 30, 40],
                                "transport.cargo_flow": [4, 4, 3, 1],
                                "traffic_properties": {"average_time": [10, 11, 12, 13]},
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
                {"time": 1, "data": {}},
            ],
            "expected_results": [
                {
                    "time": 0,
                    "data": {
                        corridor_dataset_name: {
                            "road_segment_entities": {
                                "id": [1, 2],
                                "transport.passenger_flow": [5, 15],
                                "transport.cargo_flow": [2, 3],
                                "traffic_properties": {"average_time": [23, 16.7143]},
                                "transport.passenger_car_unit": [9, 21],
                                "transport.co2_emission.hours": [64.1304, 116.3044],
                                "transport.nox_emission.hours": [153.2609, 309.7826],
                                "transport.energy_consumption.hours": [2.9565, 5.0435],
                            },
                        }
                    },
                },
                {"time": 1, "data": {}},
            ],
        }

        scenario.update(config)
        testing.ModelDriver.run_scenario(
            model=model_factory(Model),
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )
