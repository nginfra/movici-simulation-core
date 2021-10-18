from pathlib import Path

import numpy as np
import pytest

from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.traffic_kpi.model import Model
from movici_simulation_core.testing.model_tester import ModelTester
from movici_simulation_core.utils.moment import Moment


@pytest.fixture
def road_network(road_network):
    road_network["data"]["road_segment_entities"]["line_properties"]["length"] = [2.0, 1.5, 1.0]
    return road_network


@pytest.fixture
def coefficients_csv_name():
    return "coefficients_csv"


@pytest.fixture
def coefficients_csv_path():
    return Path(__file__).parent.joinpath("coefficients.csv")


@pytest.fixture
def scenario_parameters_csv_name():
    return "scenario_interpolated_csv"


@pytest.fixture
def scenario_parameters_csv_path():
    return Path(__file__).parent.joinpath("scenario_interpolated.csv")


@pytest.fixture
def init_data(
    road_network_name,
    coefficients_csv_name,
    scenario_parameters_csv_name,
    road_network,
    coefficients_csv_path,
    scenario_parameters_csv_path,
):
    return [
        {"name": road_network_name, "data": road_network},
        {"name": coefficients_csv_name, "data": coefficients_csv_path},
        {"name": scenario_parameters_csv_name, "data": scenario_parameters_csv_path},
    ]


@pytest.fixture
def model_config(
    model_name,
    road_network_name,
    coefficients_csv_name,
    scenario_parameters_csv_name,
):
    return {
        "name": model_name,
        "type": "traffic_kpi",
        "roads": [road_network_name],
        "coefficients_csv": [coefficients_csv_name],
        "scenario_parameters": [scenario_parameters_csv_name],
        "cargo_scenario_parameters": ["h2_share_freight_road"],
        "energy_consumption_property": [None, "transport.energy_consumption_h2.hours"],
        "co2_emission_property": [None, "transport.co2_emission_h2.hours"],
        "nox_emission_property": [None, "transport.nox_emission_h2.hours"],
    }


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def init_data_handler(
    init_data_handler,
    add_init_data,
    coefficients_csv_name,
    coefficients_csv_path,
    scenario_parameters_csv_name,
    scenario_parameters_csv_path,
):
    add_init_data(coefficients_csv_name, coefficients_csv_path)
    add_init_data(scenario_parameters_csv_name, scenario_parameters_csv_path)
    return init_data_handler


@pytest.fixture
def model(model_config, state, init_data_handler, global_schema):
    model = Model(model_config)
    model.setup(state, init_data_handler=init_data_handler, schema=global_schema)
    return model


def test_model_reads_coefficients(model):
    model.coefficients_tape.proceed_to(Moment(0))
    assert np.array_equal(model.coefficients_tape[("passenger", "co2")][0], [16, 19, 20])
    assert len(model.coefficients_tape[("cargo", "co2")]) == 3
    assert np.array_equal(model.coefficients_tape[("cargo", "co2")][0], [1, 13, 10])
    assert model.coefficients_tape.timeline[0] == 0
    assert model.coefficients_tape.timeline[1] == 2


def test_model_returns_coefficients_by_time(model):
    model.coefficients_tape.proceed_to(Moment(2))
    assert np.array_equal(model.coefficients_tape[("passenger", "co2")][0], [15, 18, 19])
    assert len(model.coefficients_tape[("cargo", "co2")]) == 3
    assert np.array_equal(model.coefficients_tape[("cargo", "co2")][0], [0, 12, 9])


def test_coefficients_without_category_return_empty_list(model):
    model.coefficients_tape.proceed_to(Moment(2))
    assert np.array_equal(model.coefficients_tape[("other_category", "co2")], [])
    assert np.array_equal(model.coefficients_tape[("cargo", "other_kpi")], [])


def test_tape_returns_changed_first_call_after_update(model):
    assert not model.coefficients_tape.has_update()

    model.coefficients_tape.proceed_to(Moment(0))
    assert model.coefficients_tape.has_update()

    model.coefficients_tape.proceed_to(Moment(0))
    assert not model.coefficients_tape.has_update()

    model.coefficients_tape.proceed_to(Moment(2))
    assert model.coefficients_tape.has_update()


def test_kpi_calculation(
    config, model_name, road_network_name, knotweed_dataset_name, global_schema
):
    scenario = {
        "updates": [
            {"time": 0, "data": None},
            {
                "time": 0,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2, 3],
                            "transport.cargo_vehicle_flow": [1.5, 0, 0],
                        }
                    },
                },
            },
            {"time": 1, "data": None},
            {
                "time": 2,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2, 3],
                            "transport.cargo_vehicle_flow": [1, 1, 0],
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
                            "transport.cargo_vehicle_flow": [10, 10, 0],
                        }
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
                "time": 0,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2, 3],
                            # flow * length * coef * share * load_capacity
                            # * scenario_multipliers ("load_factor_multiplier"
                            # * PI<energy_type>_share_freight_<modeality>")
                            "transport.co2_emission_h2.hours": [
                                1.5 * 2 * (1 * 13 * 10 + 2 * 14 * 11 + 3 * 15 * 12) * 0 * 1e-6,
                                0,
                                0,
                            ],
                            "transport.nox_emission_h2.hours": [
                                1.5 * 2 * (4 * 13 * 10 + 5 * 14 * 11 + 6 * 15 * 12) * 0 * 1e-6,
                                0,
                                0,
                            ],
                            "transport.energy_consumption_h2.hours": [
                                1.5 * 2 * (7 * 13 * 10 + 8 * 14 * 11 + 9 * 15 * 12) * 0 * 1e-3,
                                0,
                                0,
                            ],
                        },
                    },
                },
                "next_time": 2,
            },
            {
                "time": 1,
                "data": None,
                "next_time": 2,
            },
            {
                "time": 2,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2],
                            # flow * length * coef * share * load_capacity
                            # * scenario_multipliers ("load_factor_multiplier"
                            # * PI<energy_type>_share_freight_<modeality>")
                            "transport.co2_emission_h2.hours": [
                                1
                                * 2
                                * (0 * 12 * 9 + 1 * 13 * 10 + 2 * 14 * 11)
                                * 0.004545454545455
                                * 1e-6,
                                1
                                * 1.5
                                * (0 * 12 * 9 + 1 * 13 * 10 + 2 * 14 * 11)
                                * 0.004545454545455
                                * 1e-6,
                            ],
                            "transport.nox_emission_h2.hours": [
                                1
                                * 2
                                * (3 * 12 * 9 + 4 * 13 * 10 + 5 * 14 * 11)
                                * 0.004545454545455
                                * 1e-6,
                                1
                                * 1.5
                                * (3 * 12 * 9 + 4 * 13 * 10 + 5 * 14 * 11)
                                * 0.004545454545455
                                * 1e-6,
                            ],
                            "transport.energy_consumption_h2.hours": [
                                1
                                * 2
                                * (6 * 12 * 9 + 7 * 13 * 10 + 8 * 14 * 11)
                                * 0.004545454545455
                                * 1e-3,
                                1
                                * 1.5
                                * (6 * 12 * 9 + 7 * 13 * 10 + 8 * 14 * 11)
                                * 0.004545454545455
                                * 1e-3,
                            ],
                        },
                    },
                },
                "next_time": 3,
            },
            {
                "time": 3,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2],
                            # flow * length * coef * share * load_capacity
                            # * scenario_multipliers ("load_factor_multiplier"
                            # * PI<energy_type>_share_freight_<modeality>")
                            "transport.co2_emission_h2.hours": [
                                10
                                * 2
                                * (-1 * 11 * 8 + 0 * 12 * 9 + 1 * 13 * 10)
                                * 0.009090909090909
                                * 1e-6,
                                10
                                * 1.5
                                * (-1 * 11 * 8 + 0 * 12 * 9 + 1 * 13 * 10)
                                * 0.009090909090909
                                * 1e-6,
                            ],
                            "transport.nox_emission_h2.hours": [
                                10
                                * 2
                                * (2 * 11 * 8 + 3 * 12 * 9 + 4 * 13 * 10)
                                * 0.009090909090909
                                * 1e-6,
                                10
                                * 1.5
                                * (2 * 11 * 8 + 3 * 12 * 9 + 4 * 13 * 10)
                                * 0.009090909090909
                                * 1e-6,
                            ],
                            "transport.energy_consumption_h2.hours": [
                                10
                                * 2
                                * (5 * 11 * 8 + 6 * 12 * 9 + 7 * 13 * 10)
                                * 0.009090909090909
                                * 1e-3,
                                10
                                * 1.5
                                * (5 * 11 * 8 + 6 * 12 * 9 + 7 * 13 * 10)
                                * 0.009090909090909
                                * 1e-3,
                            ],
                        },
                    },
                },
                "next_time": 94608000,
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
