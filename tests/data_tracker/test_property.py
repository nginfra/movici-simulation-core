import numpy as np
import pytest

from movici_simulation_core.data_tracker.arrays import TrackedCSRArray, TrackedArray
from movici_simulation_core.data_tracker.property import (
    UniformProperty,
    DataType,
    PropertyOptions,
    Property,
    ensure_csr_data,
    ensure_uniform_data,
    create_empty_property,
)


def get_entity_with_initalized_properties(len):
    class MyEntity:
        prop = create_empty_property(data_type=DataType(int, (), False))
        multidim = create_empty_property(data_type=DataType(int, (2,), False))
        csr_prop = create_empty_property(data_type=DataType(int, (), True))
        str_prop = create_empty_property(data_type=DataType(str, (), False))
        csr_str_prop = create_empty_property(data_type=DataType(str, (), True))

        def __init__(self, length):
            MyEntity.prop.initialize(length)
            MyEntity.multidim.initialize(length)
            MyEntity.csr_prop.initialize(length)
            MyEntity.str_prop.initialize(length)
            MyEntity.csr_str_prop.initialize(length)

    return MyEntity(len)


def assert_equal_csr_arrays(a, b):
    assert np.array_equal(a.data, b.data)
    assert np.array_equal(a.row_ptr, b.row_ptr)


def test_can_set_property_on_uniform_array():
    obj = get_entity_with_initalized_properties(3)
    obj.prop.array = [1, 2, 3]
    assert isinstance(obj.prop, UniformProperty)
    assert np.array_equal(obj.prop.array, [1, 2, 3])


def test_tracks_changes_when_updating():
    obj = get_entity_with_initalized_properties(3)
    obj.prop.array = [1, 2, 3]
    assert np.array_equal(obj.prop.changed, [False, False, False])
    obj.prop.array[:] = [2, 2, 2]
    assert np.array_equal(obj.prop.array, [2, 2, 2])
    assert np.array_equal(obj.prop.changed, [True, False, True])


def test_can_test_uniform_property_for_special_value():
    obj = get_entity_with_initalized_properties(2)
    obj.prop.options = PropertyOptions(special=-10)
    obj.prop.update([1, -10], [0, 1])
    assert np.all(obj.prop.is_special() == [False, True])


def test_can_test_csr_property_for_special_value():
    obj = get_entity_with_initalized_properties(2)
    obj.csr_prop.options = PropertyOptions(special=-10)
    obj.csr_prop.update(TrackedCSRArray([-10], [0, 1]), [0])
    assert np.array_equal(obj.csr_prop.is_special(), [True, False])


def test_can_initialize_array_with_undefined_values():
    obj = get_entity_with_initalized_properties(2)
    assert np.array_equal(obj.prop.is_undefined(), [True, True])


def test_can_initialize_multidimensional_array():
    obj = get_entity_with_initalized_properties(3)
    assert obj.multidim.array.shape == (3, 2)
    assert np.array_equal(obj.multidim.is_undefined(), [True, True, True])


def test_can_initialize_csr_property():
    obj = get_entity_with_initalized_properties(3)
    assert obj.csr_prop.csr.size == 3
    assert np.array_equal(obj.csr_prop.is_undefined(), [True, True, True])


@pytest.mark.parametrize("attr", ["prop", "csr_prop"])
def test_initialized_array_has_no_changes(attr):
    obj = get_entity_with_initalized_properties(2)

    prop: Property = getattr(obj, attr)
    assert np.all(prop.changed == [False, False])


def test_can_set_item_through_property():
    obj = get_entity_with_initalized_properties(1)
    obj.prop[0] = 3
    assert np.array_equal(obj.prop.array, [3])


def test_uniform_property_can_assign_smaller_string():
    obj = get_entity_with_initalized_properties(1)
    assert np.array_equal(obj.str_prop.array, ["_udf_"])
    obj.str_prop[0] = "bla"
    assert np.array_equal(obj.str_prop.array, ["bla"])


def test_uniform_property_can_increase_string_size_when_setting_new_string():
    obj = get_entity_with_initalized_properties(1)
    assert np.array_equal(obj.str_prop.array, ["_udf_"])
    obj.str_prop[0] = "something_long"
    assert np.array_equal(obj.str_prop.array, ["something_long"])


def test_uniform_property_can_increase_string_size_when_setting_new_array():
    obj = get_entity_with_initalized_properties(1)
    assert np.array_equal(obj.str_prop.array, ["_udf_"])
    obj.str_prop[:] = np.array(["something_long"], dtype="U")
    assert np.array_equal(obj.str_prop.array, ["something_long"])


def test_csr_property_can_increase_string_size_when_setting_new_string_array():
    obj = get_entity_with_initalized_properties(1)
    assert_equal_csr_arrays(obj.csr_str_prop.csr, TrackedCSRArray(np.array(["_udf_"]), [0, 1]))

    upd = TrackedCSRArray(np.array(["longer_string"]), [0, 1])
    obj.csr_str_prop.update(upd, np.array([0]))
    assert_equal_csr_arrays(obj.csr_str_prop.csr, upd)


@pytest.mark.parametrize(
    "valid_data",
    [
        TrackedCSRArray([1, 2], [0, 1]),
        {"data": np.array([1, 2]), "indptr": np.array([0, 1])},
        ([1, 2], [0, 1]),
    ],
)
def test_valid_csr_data(valid_data):
    assert isinstance(ensure_csr_data(valid_data), TrackedCSRArray)


@pytest.mark.parametrize(
    "invalid_data",
    [
        {},
        [1, 2, 3],
        [1, 2],
        {
            "data": np.array([1, 2]),
        },
        np.array([1, 2]),
    ],
)
def test_invalid_csr_data(invalid_data):
    with pytest.raises(TypeError):
        ensure_csr_data(invalid_data)


@pytest.mark.parametrize(
    "valid_data",
    [
        TrackedArray([1, 2]),
        {"data": np.array([1, 2])},
        [1, 2, 3],
        np.ndarray([1, 2]),
    ],
)
def test_valid_uniform_data(valid_data):
    assert isinstance(ensure_uniform_data(valid_data), np.ndarray)


@pytest.mark.parametrize(
    "invalid_data",
    [
        TrackedCSRArray([1, 2], [0, 1]),
        {"data": np.array([1, 2]), "indptr": np.array([0, 1])},
        ([1, 2], [0, 1]),
        {},
    ],
)
def test_invalid_uniform_data(invalid_data):
    with pytest.raises(TypeError):
        ensure_uniform_data(invalid_data)


def test_generate_update_uniform_numeric():
    entity = get_entity_with_initalized_properties(2)
    entity.prop[:] = [1, 2]
    entity.prop.reset()

    entity.prop[0] = 42
    undefined = entity.prop.data_type.undefined
    assert np.array_equal(entity.prop.generate_update([1, 1])["data"], np.array([42, undefined]))


def test_generate_update_with_existing_data():
    entity = get_entity_with_initalized_properties(2)
    entity.prop[:] = [1, 2]
    entity.prop.reset()

    entity.prop[0] = 42
    undefined = entity.prop.data_type.undefined
    assert np.array_equal(entity.prop.generate_update([1, 1])["data"], np.array([42, undefined]))


@pytest.mark.parametrize("item", ["bla", "something_long"])
def test_generate_update_uniform_unicode(item):
    entity = get_entity_with_initalized_properties(2)
    entity.str_prop[0] = item
    undefined = entity.str_prop.data_type.undefined
    assert np.array_equal(
        entity.str_prop.generate_update([1, 1])["data"], np.array([item, undefined])
    )


def test_generate_update_without_mask():
    entity = get_entity_with_initalized_properties(2)
    entity.prop[0] = 42
    assert np.array_equal(entity.prop.generate_update(None)["data"], np.array([42]))


def test_generate_update_csr_numeric():
    entity = get_entity_with_initalized_properties(2)
    entity.csr_prop.update((np.array([42]), np.array([0, 1])), np.array([0]))
    undefined = entity.csr_prop.data_type.undefined
    update = entity.csr_prop.generate_update([1, 1])

    assert np.array_equal(update["data"], np.array([42, undefined]))
    assert np.array_equal(update["indptr"], np.array([0, 1, 2]))


@pytest.mark.parametrize("item", ["bla", "something_long"])
def test_generate_update_csr_unicode(item):
    entity = get_entity_with_initalized_properties(2)
    entity.csr_str_prop.update((np.array([item]), np.array([0, 1])), np.array([0]))
    undefined = entity.csr_str_prop.data_type.undefined
    update = entity.csr_str_prop.generate_update([1, 1])
    assert np.array_equal(update["data"], np.array([item, undefined]))
    assert np.array_equal(update["indptr"], np.array([0, 1, 2]))


def test_generate_csr_update_without_mask():
    entity = get_entity_with_initalized_properties(2)
    entity.csr_prop.update((np.array([42]), np.array([0, 1])), np.array([0]))
    update = entity.csr_prop.generate_update(None)
    assert np.array_equal(update["data"], np.array([42]))
    assert np.array_equal(update["indptr"], np.array([0, 1]))


def test_generate_csr_update_without_changes():
    entity = get_entity_with_initalized_properties(2)
    update = entity.csr_prop.generate_update(None)
    assert np.array_equal(update["data"], np.array([]))
    assert np.array_equal(update["indptr"], np.array([0]))


int_data_type = DataType(int, (), False)
int_undefined = int_data_type.undefined


@pytest.mark.parametrize(
    "key,value",
    [
        (slice(None, None), int_undefined),  # slice(None,None) is equivalent to [:]
        (0, int_undefined),
        ([0], int_undefined),
        ([0], [int_undefined]),
        ([0], np.array([int_undefined])),
    ],
)
def test_doesnt_overwrite_uniform_property_with_undefined(key, value):
    prop = UniformProperty(TrackedArray([0]), data_type=int_data_type)
    prop[key] = value
    assert not any(prop.is_undefined())


def test_doesnt_change_input_array():
    prop = UniformProperty(TrackedArray([0, 1]), data_type=int_data_type)
    update = np.array([int_undefined, int_undefined])
    update.flags.writeable = False
    prop[:] = update
    assert np.array_equal(update, [int_undefined, int_undefined])


str_data_type = DataType(str, (), False)
str_undefined = str_data_type.undefined


@pytest.mark.parametrize(
    "key,value",
    [
        (slice(None, None), str_undefined),  # slice(None,None) is equivalent to [:]
        (0, str_undefined),
        ([0], str_undefined),
        ([0], [str_undefined]),
        ([0], np.array([str_undefined])),
    ],
)
def test_doesnt_overwrite_uniform_property_undefined_string_array(key, value):
    prop = UniformProperty(TrackedArray(["asdf"]), data_type=str_data_type)
    prop[key] = value
    assert not any(prop.is_undefined())


def test_doesnt_overwrite_csr_property_with_undefined():
    prop = create_empty_property(data_type=DataType(int, (), True), length=1)
    prop.csr = TrackedCSRArray(np.array([1]), np.array([0, 1]))
    prop.update(TrackedCSRArray([int_undefined], [0, 1]), [0])
    assert not any(prop.is_undefined())


def test_doesnt_overwrite_unicode_csr_property_with_undefined():
    prop = create_empty_property(data_type=DataType(str, (), True), length=1)
    prop.csr = TrackedCSRArray(np.array(["bla"]), np.array([0, 1]))
    prop.update(TrackedCSRArray(np.array([str_undefined]), [0, 1]), [0])
    assert not any(prop.is_undefined())


@pytest.mark.parametrize(
    "prop,expected",
    [
        (create_empty_property(data_type=DataType(int, (), False), length=1), 1),
        (create_empty_property(data_type=DataType(int, (), False), length=2), 2),
        (create_empty_property(data_type=DataType(int, (2,), False), length=3), 3),
        (create_empty_property(data_type=DataType(int, (2,), True), length=3), 3),
        (create_empty_property(data_type=DataType(int, (), True), length=3), 3),
    ],
)
def test_property_length(prop, expected):
    assert len(prop) == expected


def test_uniform_property_has_tracked_array():
    prop = UniformProperty([1, 2, 3], data_type=int_data_type)
    assert isinstance(prop.array, TrackedArray)


@pytest.mark.parametrize(
    "prop",
    [
        (create_empty_property(data_type=DataType(int, (), False), length=1)),
        (create_empty_property(data_type=DataType(int, (), False), length=2)),
        (create_empty_property(data_type=DataType(int, (2,), False), length=3)),
        (
            create_empty_property(
                data_type=DataType(
                    int,
                    (
                        2,
                        2,
                    ),
                    False,
                ),
                length=1,
            )
        ),
    ],
)
def test_uniform_is_special_returns_false_if_not_set(prop):
    assert np.array_equal(prop.is_special(), np.zeros(prop.array.shape))


@pytest.mark.parametrize(
    "prop",
    [
        (create_empty_property(data_type=DataType(int, (), True), length=3)),
        (create_empty_property(data_type=DataType(int, (2,), True), length=3)),
    ],
)
def test_csr_is_special_returns_false_if_not_set(prop):
    assert np.array_equal(prop.is_special(), np.zeros(prop.csr.data.shape))
