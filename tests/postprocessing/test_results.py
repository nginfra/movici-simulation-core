import functools

import numpy as np
import pytest

from movici_simulation_core.utils.moment import string_to_datetime, TimelineInfo
from movici_simulation_core.data_tracker.data_format import (
    EntityInitDataFormat,
    extract_dataset_data,
)
from movici_simulation_core.core.schema import UNDEFINED, AttributeSpec, DataType
from movici_simulation_core.data_tracker.index import Index
from movici_simulation_core.postprocessing.results import (
    merge_updates,
    TimeProgressingState,
    ReversibleUpdate,
    SimulationResults,
)
from movici_simulation_core.testing.helpers import assert_dataset_dicts_equal


@pytest.fixture
def dataset_a():
    return "dataset_a"


@pytest.fixture
def entity_1():
    return "entity_1"


@pytest.fixture
def init_data(dataset_a, entity_1):
    return {
        dataset_a: {
            entity_1: {
                "id": {"data": np.array([1, 2])},
                "attr": {"data": np.array([10, 20])},
            }
        }
    }


@pytest.fixture
def update_0(dataset_a, entity_1):
    return {
        "timestamp": 0,
        "iteration": 0,
        dataset_a: {
            entity_1: {
                "id": {"data": np.array([1])},
                "attr": {"data": np.array([11])},
            }
        },
    }


@pytest.fixture
def update_1(dataset_a, entity_1):
    return {
        "timestamp": 1,
        "iteration": 1,
        dataset_a: {
            entity_1: {
                "id": {"data": np.array([2])},
                "attr": {"data": np.array([22])},
            }
        },
    }


@pytest.fixture
def additional_attributes():
    return [
        AttributeSpec("attr", DataType(int, (), False)),
        AttributeSpec("new_attr", DataType(int, (), False)),
        AttributeSpec("str_attr", DataType(str, (), False)),
        AttributeSpec("csr_attr", DataType(int, (), True)),
    ]


def test_merge_updates(dataset_a, entity_1):
    result = merge_updates(
        {
            dataset_a: {
                entity_1: {
                    "id": {"data": np.array([1])},
                    "attr": {"data": np.array([10])},
                }
            }
        },
        {
            dataset_a: {
                entity_1: {
                    "id": {"data": np.array([2])},
                    "attr": {"data": np.array([21])},
                }
            }
        },
    )
    assert_dataset_dicts_equal(
        result,
        {
            dataset_a: {
                entity_1: {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 21])},
                }
            }
        },
    )


def test_time_progressing_state(init_data, update_0, update_1, dataset_a, entity_1):
    state = TimeProgressingState()
    state.add_init_data(init_data)
    state.add_updates_to_timeline([update_0, update_1])
    data = state.get_attribute(dataset_a, entity_1, (None, "attr"))
    assert np.array_equal(data.array, [11, 22])

    state.move_to(0)
    assert np.array_equal(data.array, [11, 20])
    state.move_to(1)
    assert np.array_equal(data.array, [11, 22])


@pytest.mark.xfail(reason="not yet implemented")
def test_time_progressing_state_with_new_id(init_data, dataset_a, entity_1):
    update = {
        "timestamp": 1,
        "iteration": 1,
        dataset_a: {
            entity_1: {
                "id": {"data": np.array([3])},
                "attr": {"data": np.array([31])},
            }
        },
    }
    state = TimeProgressingState()
    state.add_init_data(init_data)
    state.add_updates_to_timeline([update])
    data = state.get_attribute(dataset_a, entity_1, (None, "attr"))
    assert np.array_equal(data.array, [10, 20, 31])

    state.move_to(0)
    assert np.array_equal(data.array, [10, 20, UNDEFINED[int]])
    state.move_to(1)
    assert np.array_equal(data.array, [10, 20, 31])


def test_time_progressing_state_with_new_attribute(init_data, dataset_a, entity_1):
    update = {
        "timestamp": 1,
        "iteration": 1,
        dataset_a: {
            entity_1: {
                "id": {"data": np.array([1])},
                "attr_2": {"data": np.array([31])},
            }
        },
    }
    state = TimeProgressingState()
    state.add_init_data(init_data)
    state.add_updates_to_timeline([update])
    data = state.get_attribute(dataset_a, entity_1, (None, "attr_2"))
    assert np.array_equal(data.array, [31, UNDEFINED[int]])

    state.move_to(0)
    assert np.array_equal(data.array, [UNDEFINED[int], UNDEFINED[int]])
    state.move_to(1)
    assert np.array_equal(data.array, [31, UNDEFINED[int]])


def test_time_progressing_state_with_new_entity_group(init_data, dataset_a, entity_1):
    update = {
        "timestamp": 1,
        "iteration": 1,
        dataset_a: {
            "entity_2": {
                "id": {"data": np.array([1])},
                "attr": {"data": np.array([12])},
            }
        },
    }
    state = TimeProgressingState()
    state.add_init_data(init_data)
    state.add_updates_to_timeline([update])
    data = state.get_attribute(dataset_a, "entity_2", (None, "attr"))
    assert np.array_equal(data.array, [12])

    state.move_to(0)
    assert np.array_equal(data.array, [UNDEFINED[int]])
    state.move_to(1)
    assert np.array_equal(data.array, [12])


class TestReversableUpdate:
    @pytest.fixture
    def state(self, init_data):
        state = TimeProgressingState()
        state.add_init_data(init_data)
        return state

    @pytest.fixture
    def rev_update(self, update_0, init_data, dataset_a, entity_1):
        index = Index(init_data[dataset_a][entity_1]["id"]["data"])

        return ReversibleUpdate(
            timestamp=update_0["timestamp"],
            iteration=update_0["iteration"],
            dataset=dataset_a,
            entity_group=entity_1,
            indices=index[update_0[dataset_a][entity_1]["id"]["data"]],
            update=update_0[dataset_a][entity_1],
        )

    def test_calculate_reverse_update(self, state, rev_update):
        rev_update.calculate_reverse_update(state)
        assert_dataset_dicts_equal(
            rev_update.reverse_update,
            {
                "id": {
                    "data": np.array([1]),
                },
                "attr": {
                    "data": np.array([10]),
                },
            },
        )


class TestSimulationResults:
    @pytest.fixture
    def empty_init_data_dir(self, tmp_path_factory):
        return tmp_path_factory.mktemp("init_data")

    @pytest.fixture
    def empty_updates_dir(self, tmp_path_factory):
        return tmp_path_factory.mktemp("updates")

    @pytest.fixture
    def init_data_dir(self, empty_init_data_dir, init_data, dataset_a):
        file = empty_init_data_dir / f"{dataset_a}.json"
        dataset_name, dataset_data = next(extract_dataset_data(init_data))
        file.write_text(EntityInitDataFormat().dumps({"name": dataset_a, "data": dataset_data}))
        return empty_init_data_dir

    @pytest.fixture
    def add_update(self, empty_updates_dir):
        def _add_update(
            data,
            dataset=None,
            timestamp=None,
            iteration=None,
        ):
            timestamp = timestamp if timestamp is not None else data.get("timestamp")
            iteration = iteration if iteration is not None else data.get("iteration")
            dataset_name, update_data = next(extract_dataset_data(data))
            dataset = dataset if dataset is not None else dataset_name
            file = empty_updates_dir / f"t{timestamp}_{iteration}_{dataset}.json"
            file.write_text(EntityInitDataFormat().dumps({"data": update_data}))

        return _add_update

    @pytest.fixture
    def updates_dir(self, empty_updates_dir, add_update, update_0, update_1):
        add_update(update_0)
        add_update(update_1)
        return empty_updates_dir

    @pytest.fixture
    def update_with_new_attribute(self, empty_updates_dir, add_update, dataset_a, entity_1):
        add_update(
            {
                dataset_a: {
                    entity_1: {
                        "id": {
                            "data": np.array([1, 2]),
                        },
                        "new_attr": {
                            "data": np.array([11, 12]),
                        },
                    },
                }
            },
            timestamp=0,
            iteration=0,
        )

    @pytest.fixture
    def timeline_info(self):
        reference = string_to_datetime("2020").timestamp()
        return TimelineInfo(reference, 1, 0)

    @pytest.fixture
    def get_simulation_results(self, timeline_info, global_schema):
        return functools.partial(
            SimulationResults, timeline_info=timeline_info, attributes=global_schema
        )

    @pytest.fixture
    def simulation_results(self, init_data_dir, updates_dir, get_simulation_results):
        return get_simulation_results(init_data_dir, updates_dir)

    def test_slice_at_single_timestamp(self, simulation_results, dataset_a, entity_1):
        dataset = simulation_results.get_dataset(dataset_a)
        result = dataset.slice(entity_1, 0)
        assert_dataset_dicts_equal(
            result,
            {
                "id": {"data": np.array([1, 2])},
                "attr": {"data": np.array([11, 20])},
            },
        )

    @pytest.mark.parametrize(
        "update, expected, slice_timestamp",
        [
            (
                {
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1, 2]),
                            },
                            "new_attr": {
                                "data": np.array([11, 12]),
                            },
                        },
                    }
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                    "new_attr": {"data": np.array([11, 12])},
                },
                0,
            ),
            (
                {
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1, 2]),
                            },
                            "new_attr": {
                                "data": np.array([11, UNDEFINED[int]]),
                            },
                        },
                    }
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                    "new_attr": {"data": np.array([11, UNDEFINED[int]])},
                },
                0,
            ),
            (
                {
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1, 2]),
                            },
                            "new_attr": {
                                "data": np.array([11, 12]),
                            },
                        },
                    }
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                    "new_attr": {"data": np.array([11, 12])},
                },
                1,
            ),
            (
                {
                    "timestamp": 1,
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1, 2]),
                            },
                            "attr": {
                                "data": np.array([11, 12]),
                            },
                        },
                    },
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                },
                0,
            ),
            (
                {
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1]),
                            },
                            "str_attr": {
                                "data": np.array(["str"]),
                            },
                        },
                    },
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                    "str_attr": {"data": np.array(["str", UNDEFINED[str]])},
                },
                0,
            ),
            (
                {
                    "dataset_a": {
                        "entity_1": {
                            "id": {
                                "data": np.array([1]),
                            },
                            "csr_attr": {"data": np.array([1]), "row_ptr": np.array([0, 1])},
                        },
                    },
                },
                {
                    "id": {"data": np.array([1, 2])},
                    "attr": {"data": np.array([10, 20])},
                    "csr_attr": {
                        "data": np.array([1, UNDEFINED[int]]),
                        "indptr": np.array([0, 1, 2]),
                    },
                },
                0,
            ),
        ],
    )
    def test_slice_different_kinds_of_updates(
        self,
        init_data_dir,
        empty_updates_dir,
        add_update,
        update,
        slice_timestamp,
        expected,
        get_simulation_results,
    ):
        add_update(
            update, timestamp=update.get("timestamp", 0), iteration=update.get("iteration", 0)
        )
        dataset = get_simulation_results(init_data_dir, empty_updates_dir).get_dataset("dataset_a")
        result = dataset.slice("entity_1", slice_timestamp)
        assert_dataset_dicts_equal(result, expected)

    def test_slice_single_attribute(self, simulation_results, dataset_a, entity_1):
        dataset = simulation_results.get_dataset(dataset_a)
        result = dataset.slice(entity_1, attribute="attr")
        assert_dataset_dicts_equal(
            result,
            {
                "id": np.array([1, 2]),
                "timestamps": [0, 1],
                "data": [
                    {"data": np.array([11, 20])},
                    {"data": np.array([11, 22])},
                ],
            },
        )

    def test_slice_single_entity(self, simulation_results, dataset_a, entity_1):
        dataset = simulation_results.get_dataset(dataset_a)
        result = dataset.slice(entity_1, entity_selector=2)
        assert_dataset_dicts_equal(
            result,
            {
                "timestamps": [0, 1],
                "data": {"attr": [20, 22]},
            },
        )

    def test_slice_single_entity_with_key(self, simulation_results, dataset_a, entity_1):
        dataset = simulation_results.get_dataset(dataset_a)
        result = dataset.slice(entity_1, entity_selector=20, key="attr")
        assert_dataset_dicts_equal(
            result,
            {
                "timestamps": [0, 1],
                "data": {"attr": [20, 22]},
            },
        )
