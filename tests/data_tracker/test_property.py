import numpy as np
import pytest

from movici_simulation_core.data_tracker.property import (
    PUB,
    PropertyField,
    UniformProperty,
    DataType,
    PropertySpec,
    Property,
)


class MyEntity:
    prop = PropertyField("prop", component=None, dtype=DataType(int, (), False), flags=PUB)
    multidim = PropertyField(
        "multidim", component=None, dtype=DataType(int, (2,), False), flags=PUB
    )
    csr_prop = PropertyField("csr", component=None, dtype=DataType(int, (), True), flags=PUB)
    str_prop = PropertyField("strprop", component=None, dtype=DataType(str, (), False), flags=PUB)

    def __init__(self, length):
        MyEntity.prop.initialize_for(self, length)
        MyEntity.multidim.initialize_for(self, length)
        MyEntity.csr_prop.initialize_for(self, length)
        MyEntity.str_prop.initialize_for(self, length)


def test_can_set_property_on_uniform_array():
    obj = MyEntity(3)
    obj.prop.array = [1, 2, 3]
    assert isinstance(obj.prop, UniformProperty)
    assert np.array_equal(obj.prop.array, [1, 2, 3])


def test_tracks_changes_when_updating():
    obj = MyEntity(3)
    obj.prop.array = [1, 2, 3]
    assert np.array_equal(obj.prop.changed, [False, False, False])
    obj.prop.array[:] = [2, 2, 2]
    assert np.array_equal(obj.prop.array, [2, 2, 2])
    assert np.array_equal(obj.prop.changed, [True, False, True])


def test_can_test_for_special_value():
    obj = MyEntity(2)
    obj.prop.spec = PropertySpec(special=-10)
    obj.prop.array = [1, -10]
    assert np.all(obj.prop.is_special() == [False, True])


def test_can_initialize_array_with_undefined_values():
    obj = MyEntity(2)
    assert np.array_equal(obj.prop.is_undefined(), [True, True])


def test_can_initialize_multidimensional_array():
    obj = MyEntity(3)
    assert obj.multidim.array.shape == (3, 2)
    assert np.array_equal(obj.multidim.is_undefined(), [True, True, True])


def test_can_initialize_csr_property():
    obj = MyEntity(3)
    assert obj.csr_prop.csr.size == 3
    assert np.array_equal(obj.csr_prop.is_undefined(), [True, True, True])


@pytest.mark.parametrize("attr", ["prop", "csr_prop"])
def test_initialized_array_has_no_changes(attr):
    obj = MyEntity(2)

    prop: Property = getattr(obj, attr)
    assert np.all(prop.changed == [False, False])


def test_can_set_item_through_property():
    obj = MyEntity(1)
    obj.prop[0] = 3
    assert np.array_equal(obj.prop.array, [3])


def test_can_increase_string_size_when_setting_new_string():
    obj = MyEntity(1)
    assert np.array_equal(obj.str_prop.array, ["_udf_"])
    obj.str_prop[0] = "something_long"
    assert np.array_equal(obj.str_prop.array, ["something_long"])


def test_can_increase_string_size_when_setting_new_array():
    obj = MyEntity(1)
    assert np.array_equal(obj.str_prop.array, ["_udf_"])
    obj.str_prop[:] = np.array(["something_long"], dtype="U")
    assert np.array_equal(obj.str_prop.array, ["something_long"])
