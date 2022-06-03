import numpy as np
import pytest

from movici_simulation_core.core import attributes
from movici_simulation_core.core.data_type import NP_TYPES
from movici_simulation_core.core.schema import (
    DataType,
    infer_data_type_from_array,
    AttributeSchema,
    AttributeSpec,
)


@pytest.mark.parametrize(
    "array,expected",
    [
        ({"data": np.array([1])}, DataType(int, (), False)),
        ({"data": np.array([1.0])}, DataType(float, (), False)),
        ({"data": np.array([True])}, DataType(bool, (), False)),
        ({"data": np.array([1], dtype=NP_TYPES[bool])}, DataType(bool, (), False)),
        ({"data": np.array(["string"])}, DataType(str, (), False)),
        ({"data": np.array([[1.0, 2.0]])}, DataType(float, (2,), False)),
        ({"data": np.array([1.0]), "row_ptr": np.array([0, 1])}, DataType(float, (), True)),
    ],
)
def test_infer_data_type_from_array(array, expected):
    assert infer_data_type_from_array(array) == expected


def test_read_schema_from_plugin():
    schema = AttributeSchema()
    schema.use(attributes.GlobalAttributes)
    assert schema.get("geometry.x") is not None


def test_read_schema_from_namespace():
    schema = AttributeSchema()
    schema.add_from_namespace(attributes)
    assert schema.get("geometry.x") is not None


@pytest.mark.parametrize(
    "name, default_data_type, expected",
    [
        ("existing", None, DataType(float)),
        ("not_existing", None, None),
        ("not_existing", DataType(int), DataType(int)),
        ("not_existing", lambda: DataType(bool), DataType(bool)),
    ],
)
def test_get_spec(name, default_data_type, expected):
    schema = AttributeSchema([AttributeSpec("existing", DataType(float))])
    spec = schema.get_spec(name, default_data_type)
    data_type = spec.data_type if spec is not None else None
    assert data_type == expected


default = object()


@pytest.mark.parametrize("caches, expected", [(default, int), (True, float), (False, int)])
def test_get_spec_caches(caches, expected):
    schema = AttributeSchema()
    kwargs = {} if caches is default else dict(cache=caches)
    schema.get_spec("attr", DataType(float), **kwargs)
    spec = schema.get_spec(
        "attr",
        DataType(int),
    )
    assert spec.data_type == DataType(expected)


def test_schema_legacy_get_spec():
    spec = AttributeSpec("attr", float)
    schema = AttributeSchema([spec])
    assert schema.get_spec((None, "attr")) is spec


@pytest.mark.parametrize(
    "inp, exception, pattern",
    [
        (("component", "attr"), ValueError, "Components are no longer supported"),
        ((), TypeError, "name must be a string"),
        (("toolong", "component", "attr"), TypeError, "name must be a string"),
    ],
)
def test_schema_legacy_invalid(inp, exception, pattern):
    schema = AttributeSchema()

    with pytest.raises(exception, match=pattern):
        schema.get_spec(inp)
