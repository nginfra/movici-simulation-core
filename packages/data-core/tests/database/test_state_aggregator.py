import numpy as np
import pytest

from movici_data_core.database import model as db
from movici_data_core.database.repository.state_aggregator import DatasetStateAggregator
from movici_simulation_core import NP_TYPES, UNDEFINED
from movici_simulation_core.core.schema import DEFAULT_ROWPTR_KEY
from movici_simulation_core.testing import assert_dataset_dicts_equal, dataset_data_to_numpy


def create_attribute(entity_group, attribute_name, data, rowptr=None):
    return db.Attribute(
        entity_type=db.EntityType(name=entity_group),
        attribute_type=db.AttributeType(name=attribute_name),
        data=db.DataArray(
            dtype=data.dtype.str,
            shape=data.shape,
            data=data.tobytes(),
        ),
        rowptr=db.RowptrArray(data=rowptr.tobytes()) if rowptr is not None else None,
    )


def data_to_attributes(data: dict):
    return [
        create_attribute(
            entity_group, attribute_name, attr_data["data"], rowptr=attr_data.get("rowptr")
        )
        for entity_group, attrs in data.items()
        for attribute_name, attr_data in attrs.items()
    ]


def test_empty_state():
    assert DatasetStateAggregator().state == {}


def test_create_initial_state_from_dataset():
    initial_data = dataset_data_to_numpy(
        {
            "some_entities": {
                "id": [1, 2, 3],
                "attr": [11.0, 12.0, 13.0],
                "text": ["a", "b", "c"],
            },
            "other_entities": {
                "id": [4, 5, 6],
                "attr": [21.0, 22.0, 23.0],
            },
        }
    )

    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(initial_data, is_initial=True)
    assert_dataset_dicts_equal(aggregator.state, initial_data)


def test_build_state_from_initial_data_and_updates():
    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(
        dataset_data_to_numpy({"roads": {"id": [1, 2, 3], "attr": [10.0, 20.0, 30.0]}}),
        is_initial=True,
    )
    aggregator.add_dataset_data(
        dataset_data_to_numpy({"roads": {"id": [1, 3], "attr": [11.0, 31.0], "another": [6, 7]}})
    )
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [1, 2, 3],
                    "attr": [11.0, 20.0, 31.0],
                    "another": [6, UNDEFINED[int], 7],
                }
            }
        ),
    )


def test_update_csr_attribute():
    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [1, 2, 3],
                    "csr": {"data": [10.0, 20.0, 30.0], "rowptr": [0, 1, 1, 3]},
                }
            }
        ),
        is_initial=True,
    )
    aggregator.add_dataset_data(
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [2, 3],
                    "csr": {"data": [11.0, 12.0, 13.0], "rowptr": [0, 2, 3]},
                    "newcsr": {"data": [100, 200, 300], "rowptr": [0, 1, 3]},
                }
            }
        )
    )
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [1, 2, 3],
                    "csr": {"data": [10.0, 11.0, 12.0, 13.0], DEFAULT_ROWPTR_KEY: [0, 1, 3, 4]},
                    "newcsr": {
                        "data": [UNDEFINED[int], 100, 200, 300],
                        DEFAULT_ROWPTR_KEY: [0, 1, 2, 4],
                    },
                }
            }
        ),
    )


@pytest.mark.parametrize(
    "value",
    [1, True, 1.0, "a"],
)
def test_creates_array_with_correct_undefineds(value):
    py_type = type(value)
    undefined = UNDEFINED[py_type]
    dtype = NP_TYPES[py_type]
    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1, 2]}}), is_initial=True)
    aggregator.add_dataset_data(
        dataset_data_to_numpy({"roads": {"id": [1], "attr": np.array([value], dtype=dtype)}})
    )
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy({"roads": {"id": [1, 2], "attr": [value, undefined]}}),
    )


def test_grows_unicode_array_if_necessary():
    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(
        dataset_data_to_numpy({"roads": {"id": [1], "text": ["a"]}}), is_initial=True
    )
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1], "text": ["b" * 40]}}))
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy({"roads": {"id": [1], "text": ["b" * 40]}}),
    )


def test_checks_for_ids_in_dataset():
    aggregator = DatasetStateAggregator()
    with pytest.raises(ValueError, match="No 'id' array found for entity group 'roads'"):
        aggregator.add_dataset_data(
            dataset_data_to_numpy({"roads": {"no_id": [1]}}), is_initial=True
        )


def test_checks_for_ids_in_update():
    aggregator = DatasetStateAggregator()
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    with pytest.raises(ValueError, match="No 'id' array found for entity group 'roads'"):
        aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"no_id": [1]}}))


def test_ensures_ids_in_update_exists():
    aggregator = DatasetStateAggregator(allow_new_entities=False)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    with pytest.raises(ValueError, match="id 2 not found in dataset"):
        aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [2]}}))


def test_creates_new_entity_if_id_does_not_exist_if_allowed():
    aggregator = DatasetStateAggregator(allow_new_entities=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [2], "attr": [5]}}))
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy({"roads": {"id": [1, 2], "attr": [UNDEFINED[int], 5]}}),
    )


@pytest.mark.parametrize("sentinel", [UNDEFINED[int], -1])
def test_generates_new_ids_if_allowed(sentinel):
    aggregator = DatasetStateAggregator(allow_new_entities=True)
    aggregator.add_dataset_data(
        dataset_data_to_numpy(
            {
                "roads": {"id": [1]},
                "others": {"id": [2, 3, 4]},
            }
        ),
        is_initial=True,
    )
    aggregator.add_dataset_data(
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [sentinel, sentinel],
                    "attr": [50, 60],
                }
            }
        )
    )
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy(
            {
                "roads": {
                    "id": [1, 5, 6],
                    "attr": [UNDEFINED[int], 50, 60],
                },
                "others": {"id": [2, 3, 4]},
            }
        ),
    )


def test_raises_if_id_is_from_other_entity_group():
    aggregator = DatasetStateAggregator(allow_new_entities=True)
    aggregator.add_dataset_data(
        dataset_data_to_numpy({"roads": {"id": [1]}, "others": {"id": [2]}}), is_initial=True
    )
    with pytest.raises(ValueError):
        aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [2], "attr": [5]}}))


def test_creates_new_entity_group_in_update_if_allowed():
    aggregator = DatasetStateAggregator(allow_new_entities=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"others": {"id": [2], "attr": [4]}}))
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy({"roads": {"id": [1]}, "others": {"id": [2], "attr": [4]}}),
    )


def test_creates_new_entity_group_with_generated_ids_in_update_if_allowed():
    aggregator = DatasetStateAggregator(allow_new_entities=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    aggregator.add_dataset_data(dataset_data_to_numpy({"others": {"id": [-1, -1]}}))
    assert_dataset_dicts_equal(
        aggregator.state,
        dataset_data_to_numpy({"roads": {"id": [1]}, "others": {"id": [2, 3]}}),
    )


def test_raises_on_new_entity_group_if_not_allowed():
    aggregator = DatasetStateAggregator(allow_new_entities=False)
    aggregator.add_dataset_data(dataset_data_to_numpy({"roads": {"id": [1]}}), is_initial=True)
    with pytest.raises(ValueError, match="'others' is not valid entity group for this dataset"):
        aggregator.add_dataset_data(dataset_data_to_numpy({"others": {"id": [1]}}))
