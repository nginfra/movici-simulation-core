import json

import numpy as np
import pytest
from movici_simulation_core.core.data_type import UNDEFINED

from movici_simulation_core.data_tracker.data_format import (
    create_array,
    EntityInitDataFormat,
    parse_list,
    infer_data_type_from_list,
    data_keys,
)
from movici_simulation_core.data_tracker.serialization import load_update, dump_update
from movici_simulation_core.core.schema import (
    AttributeSpec,
    DEFAULT_ROWPTR_KEY,
    AttributeSchema,
)
from movici_simulation_core.core import DataType
from movici_simulation_core.testing.helpers import assert_dataset_dicts_equal
from movici_simulation_core.types import FileType


@pytest.fixture
def list_init_data():
    return json.dumps(
        {
            "name": "some_name",
            "data": {
                "some_entities": {
                    "bla": [4.0, 5.0, 6.0],
                    "csr_attr": [[1, 2], [3], []],
                    "component": {
                        "unknown_str": ["a", "b", "c"],
                    },
                },
            },
        }
    )


@pytest.fixture
def array_init_data():
    return {
        "name": "some_name",
        "data": {
            "some_entities": {
                "bla": {
                    "data": np.array([4, 5, 6], dtype=float),
                },
                "csr_attr": {
                    "data": np.array([1, 2, 3], dtype=int),
                    DEFAULT_ROWPTR_KEY: np.array([0, 2, 3, 3], dtype=int),
                },
                "component": {"unknown_str": {"data": np.array(["a", "b", "c"])}},
            },
        },
    }


@pytest.fixture
def schema():
    return AttributeSchema(
        [
            AttributeSpec("bla", DataType(float, (), False)),
            AttributeSpec("csr_attr", DataType(int, (), True)),
            AttributeSpec(
                component="component", name="unknown_str", data_type=DataType(str, (), False)
            ),
        ]
    )


def test_init_data_format(list_init_data, array_init_data, schema):
    fmt = EntityInitDataFormat(schema)
    result = fmt.loads(list_init_data, FileType.JSON)
    assert_dataset_dicts_equal(result, array_init_data)


@pytest.mark.parametrize(
    "data_type, py_data, expected",
    [
        (DataType(int, (), False), [1, None], np.array([1, UNDEFINED[int]])),
        (DataType(float, (), False), [1, None], np.array([1, UNDEFINED[float]])),
        (DataType(str, (), False), ["1", None], np.array(["1", UNDEFINED[str]])),
        (DataType(bool, (), False), [True, None], np.array([True, UNDEFINED[bool]])),
        (
            DataType(int, (2,), False),
            [[1, 1], None],
            np.array(
                [
                    [
                        1,
                        1,
                    ],
                    [
                        UNDEFINED[int],
                        UNDEFINED[int],
                    ],
                ]
            ),
        ),
        (
            DataType(int, (2,), False),
            [[1, None]],
            np.array(
                [
                    [
                        UNDEFINED[int],
                        UNDEFINED[int],
                    ],
                ]
            ),
        ),
    ],
)
def test_create_array(data_type, py_data, expected):
    result = create_array(py_data, data_type)
    if data_type.py_type is float:
        assert np.allclose(result, expected, equal_nan=True)
    else:
        assert np.array_equal(result, expected)


@pytest.mark.parametrize(
    "data, data_type, expected",
    [
        ([1, 2, 3], DataType(int, (), False), {"data": np.array([1, 2, 3], dtype=int)}),
        ([1, 2, 3], DataType(float, (), False), {"data": np.array([1, 2, 3], dtype=float)}),
        (
            [True, True, False],
            DataType(bool, (), False),
            {"data": np.array([True, True, False], dtype=bool)},
        ),
        (
            ["a", "aaaa", "aaaaa"],
            DataType(str, (), False),
            {"data": np.array(["a", "aaaa", "aaaaa"], dtype=str)},
        ),
        (
            [[1, 2], [2, 2], [3, 2]],
            DataType(int, (2,), False),
            {"data": np.array([[1, 2], [2, 2], [3, 2]], dtype=float)},
        ),
        (
            [[1], [2, 2], [3, 3, 3]],
            DataType(int, (), True),
            {
                "data": np.array([1, 2, 2, 3, 3, 3], dtype=int),
                DEFAULT_ROWPTR_KEY: np.array([0, 1, 3, 6]),
            },
        ),
        (
            [[[1, 2]], [[2, 2], [2, 2]]],
            DataType(int, (2,), True),
            {
                "data": np.array([[1, 2], [2, 2], [2, 2]], dtype=int),
                DEFAULT_ROWPTR_KEY: np.array([0, 1, 3]),
            },
        ),
        (
            [[1, 2], [2, 2], [3, 2]],
            DataType(int, (2,), False),
            {"data": np.array([[1, 2], [2, 2], [3, 2]], dtype=float)},
        ),
        ([1, None], DataType(int, (), False), {"data": np.array([1, UNDEFINED[int]], dtype=int)}),
    ],
)
def test_parse_list(data, data_type, expected):
    result = parse_list(data, data_type)
    assert_dataset_dicts_equal(result, expected)
    if data_type is not None:
        assert result["data"].dtype == data_type.np_type


@pytest.mark.parametrize(
    "data, expected",
    [
        (["a", "b", "c"], DataType(str, (), False)),
        ([1, 2, 3], DataType(int, (), False)),
        ([1.0, 2.0, 3.0], DataType(float, (), False)),
        ([1.0, 2.0, 3.0], DataType(float, (), False)),
        ([True], DataType(bool, (), False)),
        ([[1]], DataType(int, (), True)),
    ],
)
def test_infer_datatype(data, expected):
    assert infer_data_type_from_list(data) == expected


def test_dump_dataset(list_init_data, array_init_data):
    fmt = EntityInitDataFormat()
    result = fmt.dumps(array_init_data)
    assert json.loads(result) == json.loads(list_init_data)


def test_can_dump_entity_group(list_init_data, array_init_data):
    fmt = EntityInitDataFormat()
    result = fmt.dumps(array_init_data["data"])
    assert json.loads(result) == json.loads(list_init_data)["data"]


@pytest.mark.parametrize(
    "data",
    [
        {"dataset": np.array([1, 2, 3])},
        {"dataset": np.array([1.0, 2.0, 3.0])},
        {"dataset": np.array([[1.0, 2.0], [3.0, 4.0]])},
    ],
)
def test_serialization_round_trip(data):
    assert_dataset_dicts_equal(data, load_update(dump_update(data)))


@pytest.mark.parametrize(
    "data,ignored, expected",
    [
        (
            {"data": {}},
            None,
            {"data"},
        ),
        (
            {"non_dict": "some_val", "my_data": {}},
            None,
            {"my_data"},
        ),
        (
            {"my_data": {}, "other_data": {}},
            None,
            {"my_data", "other_data"},
        ),
        (
            {"general": {}, "my_data": {}},
            None,
            {"my_data"},
        ),
        (
            {"ignored": {}, "my_data": {}},
            {"ignored"},
            {"my_data"},
        ),
        (
            {"data": {"invalid": "format"}},
            None,
            set(),
        ),
    ],
)
def test_data_keys(data, ignored, expected):
    result = data_keys(data, ignored) if ignored is not None else data_keys(data)
    assert result == expected
