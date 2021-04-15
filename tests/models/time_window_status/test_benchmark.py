import random

import numpy as np
import pytest

from model_engine import testing
from movici_simulation_core.models.time_window_status.model import Model

random.seed(4001)
np.random.seed(4002)
entity_count = 30000


@pytest.fixture
def time_scale():
    return 86400


@pytest.fixture
def model_name():
    return "test_time_window_status"


@pytest.fixture
def water_network_name():
    return "a_water_network"


def generate_water_network(water_network_name, entity_count):
    return {
        "version": 3,
        "name": water_network_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {
            "water_pipe_entities": {
                "id": list(range(entity_count)),
                "reference": [f"W{i}" for i in range(entity_count)],
                "maintenance.window_begin.date": [
                    f"2020-01-{random.randint(1,25)}" for _ in range(entity_count)
                ],
                "maintenance.window_end.date": [
                    f"2021-01-{random.randint(1,25)}" for _ in range(entity_count)
                ],
            }
        },
    }


@pytest.fixture
def init_data(water_network_name):
    return [
        {
            "name": water_network_name,
            "data": generate_water_network(water_network_name, entity_count),
        },
    ]


@pytest.fixture
def model_config(model_name, water_network_name):
    return {
        "name": model_name,
        "type": "time_window_status",
        "time_window_dataset": [(water_network_name, "water_pipe_entities")],
        "status_datasets": [
            (water_network_name, "water_pipe_entities"),
        ],
        "time_window_begin": (None, "maintenance.window_begin.date"),
        "time_window_end": (None, "maintenance.window_end.date"),
        "time_window_status": ("operation_status_properties", "is_working_properly"),
    }


def run_model(model_name, scenario):
    testing.ModelDriver.run_scenario(
        model=Model,
        name=model_name,
        scenario=scenario,
        atol=0.01,
    )


class TestTimeWindowStatusBenchmark:
    def test_benchmark(
        self,
        benchmark,
        get_entity_update,
        config,
        model_name,
        time_scale,
    ):
        update_times = [0, 10, 20, 30, 350, 360, 370, 400]

        scenario = {"updates": [{"time": t * time_scale, "data": {}} for t in update_times]}

        scenario.update(config)
        benchmark.pedantic(run_model, args=(model_name, scenario))
