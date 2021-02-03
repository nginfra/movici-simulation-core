import collections
from typing import Iterable, Optional, Dict

import numpy as np
import pytest

from model_engine import testing
from movici_simulation_core.models.overlap_status.model import Model

np.random.seed(4002)
entity_count = 1000
update_count = 1
active_chance = 0.1


@pytest.fixture
def time_scale():
    return 86400


@pytest.fixture
def model_name():
    return "test_overlap_status"


@pytest.fixture
def overlap_dataset(overlap_dataset_name):
    return {
        "version": 3,
        "name": overlap_dataset_name,
        "type": "random_type",
        "display_name": "",
        "epsg_code": 28992,
        "general": None,
        "data": {"overlap_entities": {"id": list(range(1, 100000))}},
    }


@pytest.fixture
def config(
    model_config,
    init_data,
    time_scale,
):
    return {
        "config": {
            "version": 4,
            "simulation_info": {
                "reference_time": 1_577_833_200,
                "start_time": 0,
                "time_scale": time_scale,
                "duration": 730,
            },
            "models": [model_config],
        },
        "init_data": init_data,
    }


@pytest.fixture
def from_network_name():
    return "from_network"


@pytest.fixture
def to_network_name1():
    return "to_network1"


@pytest.fixture
def to_network_name2():
    return "to_network2"


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
                "reference": [f"Water{i}" for i in range(entity_count)],
                "shape_properties": {
                    "linestring_3d": np.random.rand(entity_count, 10, 3).tolist()
                },
            }
        },
    }


@pytest.fixture
def init_data(
    from_network_name,
    to_network_name1,
    to_network_name2,
    water_network,
    overlap_dataset_name,
    overlap_dataset,
):
    return [
        {
            "name": from_network_name,
            "data": generate_water_network(from_network_name, entity_count),
        },
        {"name": to_network_name1, "data": generate_water_network(to_network_name1, entity_count)},
        {"name": to_network_name2, "data": generate_water_network(to_network_name2, entity_count)},
        {"name": overlap_dataset_name, "data": overlap_dataset},
    ]


@pytest.fixture
def model_config(
    model_name, overlap_dataset_name, from_network_name, to_network_name1, to_network_name2
):
    return {
        "name": model_name,
        "type": "overlap_status",
        "from_dataset": [(from_network_name, "water_pipe_entities")],
        "from_dataset_geometry": "lines",
        "to_points_datasets": None,
        "to_lines_datasets": [
            (to_network_name1, "water_pipe_entities"),
            (to_network_name2, "water_pipe_entities"),
        ],
        "output_dataset": [overlap_dataset_name],
        "check_overlapping_from": (
            "operation_status_properties",
            "is_working_properly",
        ),  # optional
        "check_overlapping_to": (
            "operation_status_properties",
            "is_working_properly",
        ),  # optional
        "distance_threshold": 0.01,
    }


def get_random_update(entity_count, true_chance):
    ids = list(range(entity_count))
    properties = np.random.rand(entity_count)
    properties[properties <= true_chance] = 1
    properties[properties > true_chance] = 0
    properties = properties.astype(np.bool).tolist()

    return {
        "water_pipe_entities": get_entity_update(
            ids,
            properties=properties,
            component_name="operation_status_properties",
            key_name="is_working_properly",
        )
    }


def run_model(model_name, scenario):
    try:
        testing.ModelDriver.run_scenario(
            model=Model,
            name=model_name,
            scenario=scenario,
            atol=0.01,
        )
    except AssertionError:
        # intended
        pass


class TestBenchmark:
    def test_benchmark(
        self,
        config,
        model_name,
        benchmark,
        time_scale,
        overlap_dataset_name,
        from_network_name,
        to_network_name1,
        to_network_name2,
    ):

        scenario = {
            "updates": [
                {
                    "time": i * time_scale,
                    "data": {
                        from_network_name: get_random_update(entity_count, active_chance),
                        to_network_name1: get_random_update(entity_count, active_chance),
                        to_network_name2: get_random_update(entity_count, active_chance),
                    },
                }
                for i in range(update_count)
            ],
            "expected_results": [
                {
                    "time": i * time_scale,
                    "data": {},
                }
                for i in range(update_count)
            ],
        }

        scenario.update(config)

        benchmark.pedantic(run_model, args=(model_name, scenario))


def get_entity_update(
    ids: Iterable, properties: Iterable, key_name: str, component_name: Optional[str] = None
) -> Dict:
    if not isinstance(ids, collections.Iterable):
        ids = [ids]
    entities = {"id": list(ids)}
    for key, prop, component in [
        (key_name, properties, component_name),
    ]:
        if prop is not None:
            if not isinstance(prop, collections.Iterable):
                prop = [prop for _ in ids]
            if component is None:
                entities[key] = prop
            else:
                if component not in entities:
                    entities[component] = {}
                entities[component][key] = prop

    return entities


def get_overlap_update(ids: Iterable, properties: Iterable) -> Dict:
    return get_entity_update(ids, properties, component_name=None, key_name="overlap.active")
