import os

import pytest

from movici_simulation_core.models.unit_conversions.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def scenario_parameters_csv_name():
    return "scenario_parameters_csv"


@pytest.fixture
def scenario_parameters_csv_path():
    return os.path.join(os.path.dirname(__file__), "coefficients.csv")


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
def legacy_model_config(
    model_name,
    road_network_name,
    scenario_parameters_csv_name,
):
    return {
        "name": model_name,
        "type": "unit_conversions",
        "flow_entities": [
            [road_network_name, "transport_node_entities"],
            [road_network_name, "road_segment_entities"],
        ],
        "flow_types": ["roads", "waterways"],
        "od_entities": [[road_network_name, "virtual_node_entities"]],
        "od_types": ["waterways"],
        "parameters": [scenario_parameters_csv_name],
    }


@pytest.fixture
def model_config(
    model_name,
    road_network_name,
    scenario_parameters_csv_name,
):
    return {
        "name": model_name,
        "type": "unit_conversions",
        "conversions": [
            {
                "class": "od",
                "modality": "waterways",
                "entity_group": [road_network_name, "virtual_node_entities"],
            },
            {
                "class": "flow",
                "modality": "roads",
                "entity_group": [road_network_name, "transport_node_entities"],
            },
            {
                "class": "flow",
                "modality": "waterways",
                "entity_group": [road_network_name, "road_segment_entities"],
            },
        ],
        "parameters_dataset": scenario_parameters_csv_name,
    }


def test_unit_conversions(config, model_name, road_network_name, global_schema):
    scenario = {
        "updates": [
            {"time": 0, "data": None},
            {
                "time": 0,
                "data": {
                    road_network_name: {
                        "transport_node_entities": {
                            "id": [0, 1, 2],
                            "transport.cargo_vehicle_flow": [1, 2, 3],
                            "transport.passenger_vehicle_flow": [4, 5, 6],
                        },
                        "road_segment_entities": {
                            "id": [101, 102, 103, 104],
                            "transport.cargo_vehicle_flow": [1, 2, 3, 4],
                        },
                        "virtual_node_entities": {
                            "id": [10, 11, 12],
                            "transport.total_outward_cargo_demand_vehicles": [1, 2, 3],
                            "transport.total_inward_cargo_demand_vehicles": [4, 5, 6],
                            "transport.total_inward_passenger_demand_vehicles": [7, 8, 9],
                            "transport.total_outward_passenger_demand_vehicles": [8, 7, 6],
                        },
                    }
                },
            },
            {"time": 2, "data": None},
        ],
        "expected_results": [
            {
                "time": 0,
                "data": None,
                "next_time": 2,
            },
            {
                "time": 0,
                "data": {
                    road_network_name: {
                        "transport_node_entities": {
                            "id": [0, 1, 2],
                            "transport.cargo_flow": [
                                (1 * 4 + 2 * 5 + 3 * 6) * i for i in [1, 2, 3]
                            ],
                            "transport.passenger_flow": [(11 * 12) * i for i in [4, 5, 6]],
                        },
                        "road_segment_entities": {
                            "id": [101, 102, 103, 104],
                            "transport.cargo_flow": [(7 * 9 + 8 * 10) * i for i in [1, 2, 3, 4]],
                        },
                        "virtual_node_entities": {
                            "id": [10, 11, 12],
                            "transport.total_outward_cargo_demand": [
                                (7 * 9 + 8 * 10) * i for i in [1, 2, 3]
                            ],
                            "transport.total_inward_cargo_demand": [
                                (7 * 9 + 8 * 10) * i for i in [4, 5, 6]
                            ],
                            "transport.total_inward_passenger_demand": [
                                (11 * 12) * i for i in [7, 8, 9]
                            ],
                            "transport.total_outward_passenger_demand": [
                                (11 * 12) * i for i in [8, 7, 6]
                            ],
                        },
                    }
                },
                "next_time": 2,
            },
            {
                "time": 2,
                "data": {
                    road_network_name: {
                        "transport_node_entities": {
                            "id": [0, 1, 2],
                            "transport.cargo_flow": [
                                (0 * 3 + 1 * 4 + 2 * 5) * i for i in [1, 2, 3]
                            ],
                            "transport.passenger_flow": [(10 * 11) * i for i in [4, 5, 6]],
                        },
                        "road_segment_entities": {
                            "id": [101, 102, 103, 104],
                            "transport.cargo_flow": [(6 * 8 + 7 * 9) * i for i in [1, 2, 3, 4]],
                        },
                        "virtual_node_entities": {
                            "id": [10, 11, 12],
                            "transport.total_outward_cargo_demand": [
                                (6 * 8 + 7 * 9) * i for i in [1, 2, 3]
                            ],
                            "transport.total_inward_cargo_demand": [
                                (6 * 8 + 7 * 9) * i for i in [4, 5, 6]
                            ],
                            "transport.total_inward_passenger_demand": [
                                (10 * 11) * i for i in [7, 8, 9]
                            ],
                            "transport.total_outward_passenger_demand": [
                                (10 * 11) * i for i in [8, 7, 6]
                            ],
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


def test_convert_legacy_model_config(legacy_model_config, model_config):
    del model_config["name"]
    del model_config["type"]
    assert Model(legacy_model_config).config == model_config
