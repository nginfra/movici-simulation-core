import os

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
    return os.path.join(os.path.dirname(__file__), "coefficients.csv")


@pytest.fixture
def init_data(road_network_name, coefficients_csv_name, road_network, coefficients_csv_path):
    return [
        {"name": road_network_name, "data": road_network},
        {"name": coefficients_csv_name, "data": coefficients_csv_path},
    ]


@pytest.fixture
def model_config(
    model_name,
    road_network_name,
    coefficients_csv_name,
):
    return {
        "name": model_name,
        "type": "traffic_kpi",
        "roads": [road_network_name],
        "coefficients_csv": [coefficients_csv_name],
    }


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def init_data_handler(
    init_data_handler, add_init_data, coefficients_csv_name, coefficients_csv_path
):
    add_init_data(coefficients_csv_name, coefficients_csv_path)
    return init_data_handler


@pytest.fixture
def model(model_config, state, init_data_handler):
    model = Model(model_config)
    model.setup(state, init_data_handler=init_data_handler)
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
                            "transport.passenger_vehicle_flow": [1.5, 0, 0],
                        }
                    },
                },
            },
            {"time": 1, "data": None},
            {"time": 2, "data": None},
            {
                "time": 3,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2, 3],
                            "transport.cargo_vehicle_flow": [1, 1, 0],
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
                            "transport.co2_emission.hours": [
                                1.5 * 2 * 16 * 19 * 20 * 1e-6,
                                0,
                                0,
                            ],  # flow * length * coef * share * load_capacity
                            "transport.nox_emission.hours": [1.5 * 2 * 17 * 19 * 20 * 1e-6, 0, 0],
                            "transport.energy_consumption.hours": [
                                1.5 * 2 * 18 * 19 * 20 * 1e-3,
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
                            "id": [1],
                            "transport.co2_emission.hours": [1.5 * 2 * 15 * 18 * 19 * 1e-6],
                            "transport.nox_emission.hours": [1.5 * 2 * 16 * 18 * 19 * 1e-6],
                            "transport.energy_consumption.hours": [1.5 * 2 * 17 * 18 * 19 * 1e-3],
                        },
                    },
                },
                "next_time": None,
            },
            {
                "time": 3,
                "data": {
                    road_network_name: {
                        "road_segment_entities": {
                            "id": [1, 2],
                            "transport.co2_emission.hours": [
                                # flow * length * coef * share * load_capacity
                                (
                                    1.5 * 2 * 15 * 18 * 19
                                    + 1 * 2 * (0 * 12 * 9 + 1 * 13 * 10 + 2 * 14 * 11)
                                )
                                * 1e-6,
                                (1 * 1.5 * (0 * 12 * 9 + 1 * 13 * 10 + 2 * 14 * 11)) * 1e-6,
                            ],
                            "transport.nox_emission.hours": [
                                (
                                    1.5 * 2 * 16 * 18 * 19
                                    + 1 * 2 * (3 * 12 * 9 + 4 * 13 * 10 + 5 * 14 * 11)
                                )
                                * 1e-6,
                                1 * 1.5 * (3 * 12 * 9 + 4 * 13 * 10 + 5 * 14 * 11) * 1e-6,
                            ],
                            "transport.energy_consumption.hours": [
                                (
                                    1.5 * 2 * 17 * 18 * 19
                                    + 1 * 2 * (6 * 12 * 9 + 7 * 13 * 10 + 8 * 14 * 11)
                                )
                                * 1e-3,
                                1 * 1.5 * (6 * 12 * 9 + 7 * 13 * 10 + 8 * 14 * 11) * 1e-3,
                            ],
                        },
                    },
                },
                "next_time": None,
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
