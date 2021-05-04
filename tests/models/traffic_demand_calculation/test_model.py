import os

import pytest

from model_engine import testing
from movici_simulation_core.base_model.base import model_factory
from movici_simulation_core.models.traffic_demand_calculation.model import Model


@pytest.fixture
def scenario_parameters_csv_name():
    return "scenario_parameters_csv"


@pytest.fixture
def scenario_parameters_csv_path():
    return os.path.join(os.path.dirname(__file__), "scenario_parameters.csv")


@pytest.fixture
def init_data(
    road_network_name,
    road_network_for_traffic,
    scenario_parameters_csv_name,
    scenario_parameters_csv_path,
):
    return [
        {"name": road_network_name, "data": road_network_for_traffic},
        {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
    ]


@pytest.fixture
def model_config(
    model_name,
    road_network_name,
    scenario_parameters_csv_name,
):
    return {
        "name": model_name,
        "type": "traffic_demand_calculation",
        "transport_dataset": [road_network_name],
        "scenario_parameters": [scenario_parameters_csv_name],
        "global_parameters": ["gp1", "gp2"],
        "global_elasticity": [2, -1],
    }


def test_demand_calculation(
    config,
    model_name,
    road_network_name,
):
    scenario = {
        "updates": [
            {
                "time": 0,
                "data": {
                    road_network_name: {
                        "virtual_node_entities": {
                            "id": [10, 11, 12],
                            "transport.passenger_demand": [[1, 2, 3], [5, 0, 0], [0, 0, 0]],
                            "transport.cargo_demand": [
                                [6, 0, 0],
                                [10, 0, 0],
                                [0, 0, 0],
                            ],
                        }
                    }
                },
            },
            {"time": 2, "data": {}},
        ],
        "expected_results": [
            {
                "time": 0,
                "data": {},
                "next_time": 2,
            },
            {
                "time": 2,
                "data": {
                    road_network_name: {
                        "virtual_node_entities": {
                            "id": [10, 11],
                            "transport.passenger_demand": [
                                [20.25, 40.50, 60.75],
                                [101.25, 0, 0],
                            ],
                            "transport.cargo_demand": [
                                [121.5, 0, 0],
                                [202.5, 0, 0],
                            ],
                        }
                    }
                },
            },
        ],
    }
    scenario.update(config)
    testing.ModelDriver.run_scenario(
        model=model_factory(Model),
        name=model_name,
        scenario=scenario,
        rtol=0.01,
    )
