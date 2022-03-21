import numpy as np
import pytest
from movici_simulation_core.core import DataType

from movici_simulation_core.data_tracker.arrays import TrackedCSRArray, TrackedArray
from movici_simulation_core.data_tracker.attribute import (
    UniformAttribute,
    AttributeOptions,
    Attribute,
    ensure_csr_data,
    ensure_uniform_data,
    create_empty_attribute,
    CSRAttribute,
)


def get_entity_with_initialized_attributes(len):
    class MyEntity:
        attr = create_empty_attribute(data_type=DataType(int, (), False))
        multidim = create_empty_attribute(data_type=DataType(int, (2,), False))
        csr_attr = create_empty_attribute(data_type=DataType(int, (), True))
        str_attr = create_empty_attribute(data_type=DataType(str, (), False))
        csr_str_attr = create_empty_attribute(data_type=DataType(str, (), True))
        csr_float_attr = create_empty_attribute(data_type=DataType(float, (), True))
        csr_float_multidim_attr = create_empty_attribute(data_type=DataType(float, (2,), True))

        def __init__(self, length):
            MyEntity.attr.initialize(length)
            MyEntity.multidim.initialize(length)
            MyEntity.csr_attr.initialize(length)
            MyEntity.str_attr.initialize(length)
            MyEntity.csr_str_attr.initialize(length)
            MyEntity.csr_float_attr.initialize(length)
            MyEntity.csr_float_multidim_attr.initialize(length)

    return MyEntity(len)


def assert_equal_csr_arrays(a, b):
    assert np.array_equal(a.data, b.data)
    assert np.array_equal(a.row_ptr, b.row_ptr)


def test_can_set_attribute_on_uniform_array():
    obj = get_entity_with_initialized_attributes(3)
    obj.attr.array = [1, 2, 3]
    assert isinstance(obj.attr, UniformAttribute)
    assert np.array_equal(obj.attr.array, [1, 2, 3])


def test_tracks_changes_when_updating():
    obj = get_entity_with_initialized_attributes(3)
    obj.attr.array = [1, 2, 3]
    assert np.array_equal(obj.attr.changed, [False, False, False])
    obj.attr.array[:] = [2, 2, 2]
    assert np.array_equal(obj.attr.array, [2, 2, 2])
    assert np.array_equal(obj.attr.changed, [True, False, True])


def test_can_test_uniform_attribute_for_special_value():
    obj = get_entity_with_initialized_attributes(2)
    obj.attr.options = AttributeOptions(special=-10)
    obj.attr.update([1, -10], [0, 1])
    assert np.all(obj.attr.is_special() == [False, True])


def test_can_test_csr_attribute_for_special_value():
    obj = get_entity_with_initialized_attributes(2)
    obj.csr_attr.options = AttributeOptions(special=-10)
    obj.csr_attr.update(TrackedCSRArray([-10], [0, 1]), [0])
    assert np.array_equal(obj.csr_attr.is_special(), [True, False])


def test_can_initialize_array_with_undefined_values():
    obj = get_entity_with_initialized_attributes(2)
    assert np.array_equal(obj.attr.is_undefined(), [True, True])


def test_can_initialize_multidimensional_array():
    obj = get_entity_with_initialized_attributes(3)
    assert obj.multidim.array.shape == (3, 2)
    assert np.array_equal(obj.multidim.is_undefined(), [True, True, True])


def test_can_initialize_csr_attribute():
    obj = get_entity_with_initialized_attributes(3)
    assert obj.csr_attr.csr.size == 3
    assert np.array_equal(obj.csr_attr.is_undefined(), [True, True, True])


@pytest.mark.parametrize("attr", ["attr", "csr_attr"])
def test_initialized_array_has_no_changes(attr):
    obj = get_entity_with_initialized_attributes(2)

    attr: Attribute = getattr(obj, attr)
    assert np.all(attr.changed == [False, False])


def test_can_set_item_through_attribute():
    obj = get_entity_with_initialized_attributes(1)
    obj.attr[0] = 3
    assert np.array_equal(obj.attr.array, [3])


def test_uniform_attribute_can_assign_smaller_string():
    obj = get_entity_with_initialized_attributes(1)
    assert np.array_equal(obj.str_attr.array, ["_udf_"])
    obj.str_attr[0] = "bla"
    assert np.array_equal(obj.str_attr.array, ["bla"])


def test_uniform_attribute_can_increase_string_size_when_setting_new_string():
    obj = get_entity_with_initialized_attributes(1)
    assert np.array_equal(obj.str_attr.array, ["_udf_"])
    obj.str_attr[0] = "something_long"
    assert np.array_equal(obj.str_attr.array, ["something_long"])


def test_uniform_attribute_can_increase_string_size_when_setting_new_array():
    obj = get_entity_with_initialized_attributes(1)
    assert np.array_equal(obj.str_attr.array, ["_udf_"])
    obj.str_attr[:] = np.array(["something_long"], dtype="U")
    assert np.array_equal(obj.str_attr.array, ["something_long"])


def test_csr_attribute_can_increase_string_size_when_setting_new_string_array():
    obj = get_entity_with_initialized_attributes(1)
    assert_equal_csr_arrays(obj.csr_str_attr.csr, TrackedCSRArray(np.array(["_udf_"]), [0, 1]))

    upd = TrackedCSRArray(np.array(["longer_string"]), [0, 1])
    obj.csr_str_attr.update(upd, np.array([0]))
    assert_equal_csr_arrays(obj.csr_str_attr.csr, upd)


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
    entity = get_entity_with_initialized_attributes(2)
    entity.attr[:] = [1, 2]
    entity.attr.reset()

    entity.attr[0] = 42
    undefined = entity.attr.data_type.undefined
    assert np.array_equal(entity.attr.generate_update([1, 1])["data"], np.array([42, undefined]))


def test_generate_update_with_existing_data():
    entity = get_entity_with_initialized_attributes(2)
    entity.attr[:] = [1, 2]
    entity.attr.reset()

    entity.attr[0] = 42
    undefined = entity.attr.data_type.undefined
    assert np.array_equal(entity.attr.generate_update([1, 1])["data"], np.array([42, undefined]))


def test_generate_update_multidim():
    entity = get_entity_with_initialized_attributes(2)
    entity.multidim[:] = [[1, 0], [2, 0]]
    entity.multidim.reset()

    entity.multidim[0] = [2, 0]

    np.testing.assert_array_equal(entity.multidim.generate_update()["data"], np.array([[2, 0]]))


def test_generate_update_multidim_with_slice():
    entity = get_entity_with_initialized_attributes(2)
    entity.multidim[:] = [[1, 0], [2, 0]]
    entity.multidim.reset()

    entity.multidim[0] = [2, 0]
    undefined = entity.attr.data_type.undefined

    np.testing.assert_array_equal(
        entity.multidim.generate_update([1, 1])["data"], np.array([[2, 0], [undefined, undefined]])
    )


@pytest.mark.parametrize("item", ["bla", "something_long"])
def test_generate_update_uniform_unicode(item):
    entity = get_entity_with_initialized_attributes(2)
    entity.str_attr[0] = item
    undefined = entity.str_attr.data_type.undefined
    assert np.array_equal(
        entity.str_attr.generate_update([1, 1])["data"], np.array([item, undefined])
    )


def test_generate_update_without_mask():
    entity = get_entity_with_initialized_attributes(2)
    entity.attr[0] = 42
    assert np.array_equal(entity.attr.generate_update(None)["data"], np.array([42]))


def test_generate_update_csr_numeric():
    entity = get_entity_with_initialized_attributes(2)
    entity.csr_attr.update((np.array([42]), np.array([0, 1])), np.array([0]))
    undefined = entity.csr_attr.data_type.undefined
    update = entity.csr_attr.generate_update([1, 1])

    assert np.array_equal(update["data"], np.array([42, undefined]))
    assert np.array_equal(update["indptr"], np.array([0, 1, 2]))


@pytest.mark.parametrize("item", ["bla", "something_long"])
def test_generate_update_csr_unicode(item):
    entity = get_entity_with_initialized_attributes(2)
    entity.csr_str_attr.update((np.array([item]), np.array([0, 1])), np.array([0]))
    undefined = entity.csr_str_attr.data_type.undefined
    update = entity.csr_str_attr.generate_update([1, 1])
    assert np.array_equal(update["data"], np.array([item, undefined]))
    assert np.array_equal(update["indptr"], np.array([0, 1, 2]))


def test_generate_csr_update_without_mask():
    entity = get_entity_with_initialized_attributes(2)
    entity.csr_attr.update((np.array([42]), np.array([0, 1])), np.array([0]))
    update = entity.csr_attr.generate_update(None)
    assert np.array_equal(update["data"], np.array([42]))
    assert np.array_equal(update["indptr"], np.array([0, 1]))


def test_generate_csr_update_without_changes():
    entity = get_entity_with_initialized_attributes(2)
    update = entity.csr_attr.generate_update(None)
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
def test_doesnt_overwrite_uniform_attribute_with_undefined(key, value):
    attr = UniformAttribute(TrackedArray([0]), data_type=int_data_type)
    attr[key] = value
    assert not any(attr.is_undefined())


def test_doesnt_change_input_array():
    attr = UniformAttribute(TrackedArray([0, 1]), data_type=int_data_type)
    update = np.array([int_undefined, int_undefined])
    update.flags.writeable = False
    attr[:] = update
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
def test_doesnt_overwrite_uniform_attribute_undefined_string_array(key, value):
    attr = UniformAttribute(TrackedArray(["asdf"]), data_type=str_data_type)
    attr[key] = value
    assert not any(attr.is_undefined())


def test_doesnt_overwrite_csr_attribute_with_undefined():
    attr = create_empty_attribute(data_type=DataType(int, (), True), length=1)
    attr.csr = TrackedCSRArray(np.array([1]), np.array([0, 1]))
    attr.update(TrackedCSRArray([int_undefined], [0, 1]), [0])
    assert not any(attr.is_undefined())


def test_doesnt_overwrite_unicode_csr_attribute_with_undefined():
    attr = create_empty_attribute(data_type=DataType(str, (), True), length=1)
    attr.csr = TrackedCSRArray(np.array(["bla"]), np.array([0, 1]))
    attr.update(TrackedCSRArray(np.array([str_undefined]), [0, 1]), [0])
    assert not any(attr.is_undefined())


def test_generate_csr_update_with_null_changes():
    entity = get_entity_with_initialized_attributes(2)

    undefined = entity.csr_attr.data_type.undefined
    entity.csr_attr.update((np.array([1, 2]), np.array([0, 1, 2])), np.array([0, 1]))
    entity.csr_attr.update((np.array([undefined, 3]), np.array([0, 1, 2])), np.array([0, 1]))
    update = entity.csr_attr.generate_update([1, 1])

    assert np.array_equal(update["data"], np.array([1, 3]))
    assert np.array_equal(update["indptr"], np.array([0, 1, 2]))


def test_generate_csr_update_with_null_changes_differing_row_ptr():
    entity = get_entity_with_initialized_attributes(2)

    undefined = entity.csr_attr.data_type.undefined
    entity.csr_attr.update((np.array([1, 2, 3, 4]), np.array([0, 2, 4])), np.array([0, 1]))
    entity.csr_attr.update((np.array([undefined, 5, 6]), np.array([0, 1, 3])), np.array([0, 1]))
    update = entity.csr_attr.generate_update([1, 1])

    assert np.array_equal(update["data"], np.array([1, 2, 5, 6]))
    assert np.array_equal(update["indptr"], np.array([0, 2, 4]))


def test_generate_csr_update_with_null_changes_float():
    entity = get_entity_with_initialized_attributes(2)

    undefined = entity.csr_float_attr.data_type.undefined
    entity.csr_float_attr.update(
        (np.array([1.0, 2.0, 3.0, 4.0]), np.array([0, 2, 4])), np.array([0, 1])
    )
    entity.csr_float_attr.update(
        (np.array([undefined, 5.0, 6.0]), np.array([0, 1, 3])), np.array([0, 1])
    )
    update = entity.csr_float_attr.generate_update([1, 1])

    assert np.array_equal(update["data"], np.array([1.0, 2.0, 5.0, 6.0]))
    assert np.array_equal(update["indptr"], np.array([0, 2, 4]))


def test_generate_csr_update_with_null_changes_float_with_0s():
    entity = get_entity_with_initialized_attributes(1000)

    undefined = entity.csr_float_attr.data_type.undefined
    entity.csr_float_attr.update(
        (np.zeros(2000, dtype=np.float64), np.arange(0, 2001, 2)), np.arange(0, 1000)
    )
    entity.csr_float_attr.update(
        (np.full(1000, undefined), np.arange(0, 1001)), np.arange(0, 1000)
    )
    update = entity.csr_float_attr.generate_update(np.ones(1000))

    assert np.array_equal(update["data"], np.zeros(2000, dtype=np.float64))
    assert np.array_equal(update["indptr"], np.arange(0, 2001, 2))


def test_generate_csr_update_with_null_changes_float_multidimensional():
    entity = get_entity_with_initialized_attributes(1000)

    undefined = entity.csr_float_multidim_attr.data_type.undefined
    entity.csr_float_multidim_attr.update(
        (np.zeros((2000, 2), dtype=np.float64), np.arange(0, 2001, 2)), np.arange(0, 1000)
    )
    entity.csr_float_multidim_attr.update(
        (np.full((1000, 2), undefined), np.arange(0, 1001)), np.arange(0, 1000)
    )
    update = entity.csr_float_multidim_attr.generate_update(np.ones(1000))

    assert np.array_equal(update["data"], np.zeros((2000, 2), dtype=np.float64))
    assert np.array_equal(update["indptr"], np.arange(0, 2001, 2))


@pytest.mark.parametrize(
    "attr,expected",
    [
        (create_empty_attribute(data_type=DataType(int, (), False), length=1), 1),
        (create_empty_attribute(data_type=DataType(int, (), False), length=2), 2),
        (create_empty_attribute(data_type=DataType(int, (2,), False), length=3), 3),
        (create_empty_attribute(data_type=DataType(int, (2,), True), length=3), 3),
        (create_empty_attribute(data_type=DataType(int, (), True), length=3), 3),
    ],
)
def test_attribute_length(attr, expected):
    assert len(attr) == expected


def test_uniform_attribute_has_tracked_array():
    attr = UniformAttribute([1, 2, 3], data_type=int_data_type)
    assert isinstance(attr.array, TrackedArray)


@pytest.mark.parametrize(
    "attr",
    [
        (create_empty_attribute(data_type=DataType(int, (), False), length=1)),
        (create_empty_attribute(data_type=DataType(int, (), False), length=2)),
        (create_empty_attribute(data_type=DataType(int, (2,), False), length=3)),
        (
            create_empty_attribute(
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
def test_uniform_is_special_returns_false_if_not_set(attr):
    assert np.array_equal(attr.is_special(), np.zeros(attr.array.shape))


@pytest.mark.parametrize(
    "attr",
    [
        (create_empty_attribute(data_type=DataType(int, (), True), length=3)),
        (create_empty_attribute(data_type=DataType(int, (2,), True), length=3)),
    ],
)
def test_csr_is_special_returns_false_if_not_set(attr):
    assert np.array_equal(attr.is_special(), np.zeros(attr.csr.data.shape))


def test_is_undefined_csr():
    attr = CSRAttribute(
        {
            "data": np.array([1, 2, 3], dtype=int),
            "row_ptr": np.array([0, 2, 3, 3], dtype=int),
        },
        data_type=DataType(int, (), True),
    )
    assert np.array_equal(attr.is_undefined(), [False, False, False])


def test_initialize_attribute_with_string_data():
    attr = UniformAttribute(["some_long_string"], data_type=DataType(str, (), False))
    assert np.array_equal(attr.array, ["some_long_string"])


def test_grow_uniform_attribute():
    data_type = DataType(int, (), False)
    attr = UniformAttribute([1, 2, 3], data_type=data_type)
    attr.resize(4)
    assert np.array_equal(attr.array, [1, 2, 3, data_type.undefined])


def test_grow_uniform_attribute_keeps_changes():
    data_type = DataType(int, (), False)
    attr = UniformAttribute([1, 2, 3], data_type=data_type)
    attr[0] = 2
    attr.resize(4)
    assert np.array_equal(attr.array, [2, 2, 3, data_type.undefined])
    assert np.array_equal(attr.changed, [True, False, False, False])


def test_grow_uniform_attribute_keeps_unicode_length():
    data_type = DataType(str, (), False)
    attr = UniformAttribute(["some_long_string"], data_type=data_type)
    attr.resize(2)
    assert np.array_equal(attr.array, ["some_long_string", data_type.undefined])


def test_grow_csr_attribute():
    data_type = DataType(int, (), True)
    attr = CSRAttribute(([[1], [], [2]]), data_type=data_type)
    attr.resize(5)

    assert np.array_equal(attr.csr.data, [1, 2, data_type.undefined, data_type.undefined])
    assert np.array_equal(attr.csr.row_ptr, [0, 1, 1, 2, 3, 4])


class TestEnum:
    @pytest.fixture
    def enum_name(self):
        return "my_enum"

    @pytest.fixture
    def enum_values(self):
        return None

    @pytest.fixture
    def attribute(self, enum_name, enum_values):
        options = AttributeOptions(enum_name=enum_name, enum_values=enum_values)
        return UniformAttribute(None, DataType(float), options=options)

    def test_no_enum_when_no_values_given(self, attribute: UniformAttribute):
        assert attribute.get_enumeration() is None

    @pytest.mark.parametrize("enum_values", (["a", "b"],))
    def test_can_query_enum_class(self, attribute: UniformAttribute):
        enum = attribute.get_enumeration()
        assert enum.a == 0
        assert enum.b == 1
