from __future__ import annotations

import abc
import dataclasses
import dataclasses as dc
import functools
import typing as t

import numpy as np

from .arrays import TrackedArrayType, TrackedCSRArray, TrackedArray
from .csr_helpers import generate_update, remove_undefined_csr, isclose
from .data_format import is_undefined_uniform, is_undefined_csr
from .index import Index
from ..types import UniformPropertyData, CSRPropertyData, NumpyPropertyData
from .unicode_helpers import determine_new_unicode_dtype
from ..core.schema import (
    PropertySpec,
    DataType,
    DEFAULT_ROWPTR_KEY,
    has_rowptr_key,
    get_rowptr,
    infer_data_type_from_array,
    get_undefined,
)

if t.TYPE_CHECKING:
    from .entity_group import EntityGroup

# Base property pub/sub flags
# These are used internally when checking for attributes, model developers should use the combined
# flags below such as INIT, SUB, OPT and PUB
INITIALIZE = 1
SUBSCRIBE = 1 << 1
REQUIRED = 1 << 2
PUBLISH = 1 << 3

# Property pub/sub flags
INIT = SUBSCRIBE | INITIALIZE | REQUIRED  # This property is required for initialization
SUB = SUBSCRIBE | REQUIRED  # This property is required to start calculating updates
OPT = SUBSCRIBE  # The model is interested in this property, but it's optional
PUB = PUBLISH  # The model publishes this property

# todo: do we want this?
#  IMMUTABLE = 1 << 4  # the model doesn't support it when this property changes once set


def flag_info(flag: int):
    return FlagInfo(
        (flag & INITIALIZE) == INITIALIZE,
        (flag & SUBSCRIBE) == SUBSCRIBE,
        (flag & REQUIRED) == REQUIRED,
        (flag & PUBLISH) == PUBLISH,
    )


@dataclasses.dataclass
class FlagInfo:
    initialize: bool
    subscribe: bool
    required: bool
    publish: bool


class PropertyField:
    def __init__(self, spec: PropertySpec, flags: int = 0, rtol=1e-5, atol=1e-8):
        """
        flags: one or more boolean flags of `INIT`, `SUB`, `OPT`, `PUB`, eg: `SUB|OPT`
        """
        self.spec = spec
        self.flags = flags
        self.rtol = rtol
        self.atol = atol

    def __get__(
        self, instance: t.Optional[EntityGroup], owner
    ) -> t.Union[PropertyField, UniformProperty, CSRProperty]:
        if instance is None:
            return self
        return instance.get_property(self.spec.key)

    def __set__(self, instance: EntityGroup, value):
        raise TypeError("PropertyField is read only")

    @property
    def full_name(self):
        return self.spec.full_name

    @property
    def key(self):
        return self.spec.key


field = PropertyField

T = t.TypeVar("T", bool, int, float, str)


@dc.dataclass
class PropertyOptions(t.Generic[T]):
    special: t.Optional[T] = None
    enum_name: t.Optional[str] = None
    enum: t.Optional[t.List[str]] = None


class Property(abc.ABC):
    def __init__(
        self,
        data,
        data_type: DataType,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
        options: t.Optional[PropertyOptions] = None,
        index: t.Optional[Index] = None,
    ):
        self._data = data
        self.data_type = data_type
        self.flags = flags
        self.rtol = rtol
        self.atol = atol
        self.index = index
        self.options = options or PropertyOptions()
        self._is_initialized = False

    def initialize(self, length):
        if self.has_data():
            raise ValueError("Already initialized")
        self._data = get_undefined_array(self.data_type, length, self.rtol, self.atol)

    def is_initialized(self):
        if self._is_initialized:
            return True
        self._is_initialized = self.has_data() and not np.any(self.is_undefined())
        return self._is_initialized

    def has_data(self):
        return self._data is not None

    def has_data_or_raise(self):
        if not self.has_data():
            raise ValueError("Uninitialized array")

    def has_changes(self) -> bool:
        return np.any(self.changed)

    @property
    def changed(self):
        self.has_data_or_raise()

        # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be reduced
        # to a result array of shape (10,) by reducing over axes (1,2)
        reduction_axes = tuple(range(1, len(self._data.changed.shape)))
        return np.maximum.reduce(self._data.changed, axis=reduction_axes)

    def resize(self, new_size: int):
        curr_size = len(self)
        if new_size < curr_size:
            raise ValueError("Can only increase size of attribute array, not decrease it")
        if new_size == curr_size:
            return
        if not self.has_data():
            self.initialize(new_size)
        self._do_resize(new_size)

    @abc.abstractmethod
    def __len__(self):
        pass

    @abc.abstractmethod
    def slice(self, item):
        pass

    @abc.abstractmethod
    def _do_resize(self, new_size: int):
        pass

    @abc.abstractmethod
    def is_special(self):
        pass

    @abc.abstractmethod
    def is_undefined(self):
        pass

    @abc.abstractmethod
    def to_dict(self):
        pass

    @abc.abstractmethod
    def reset(self):
        pass


class UniformProperty(Property):
    """
    The underlying data can be accessed through the `UniformProperty().array` attribute. When
    updating data using indexing ("[]") notation, it is recommended to use
    `UniformProperty()[index]=value`. When dealing with string (ie. unicode) arrays, this feature
    will make sure that the array itemsize will grow if trying to add strings that are larger than
    the  current itemsize.
    """

    def __init__(
        self,
        data,
        data_type: DataType,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
        options: t.Optional[PropertyOptions] = None,
        index: t.Optional[Index] = None,
    ):
        if data is not None:
            data = ensure_uniform_data(data, data_type=data_type)
        super().__init__(data, data_type, flags, rtol, atol, options, index)

    @property
    def array(self) -> TrackedArray:
        return self._data

    @array.setter
    def array(self, value):
        value = ensure_uniform_data(value)
        self._data = value

    def slice(self, item):
        return self.array[item]

    def __len__(self):
        if self.array is not None:
            return self.array.shape[0]
        return 0

    def __getitem__(self, item):
        return self.slice(item)

    def __setitem__(self, key, value):
        self._set_item(key, value, process_undefined=False)

    def update(
        self,
        value: t.Union[np.ndarray, UniformPropertyData],
        indices: np.ndarray,
        process_undefined=False,
    ):
        value = ensure_uniform_data(value)
        self._set_item(indices, value, process_undefined)

    def _set_item(self, key, value, process_undefined):
        if not process_undefined:
            if not np.isscalar(value):
                value = self.strip_undefined(key, value)
            elif self.data_type.is_undefined(value):
                return

        if dtype := determine_new_unicode_dtype(self.array, value):
            self.array = self.array.astype(dtype)
        self.array[key] = value

    def strip_undefined(self, key, value):
        value = np.array(value, copy=True)
        undefs = self.data_type.is_undefined(value)
        if np.any(undefs):
            current = self.array[key]
            value[undefs] = current[undefs]
        return value

    def _do_resize(self, new_size: int):
        curr_size = len(self)
        new_arr = get_undefined_array(
            self.data_type, new_size, self.rtol, self.atol, override_dtype=self._data.dtype
        )
        new_arr[:curr_size] = self._data
        if self._data._curr is not None:
            new_arr._curr[:curr_size] = self._data._curr
        self._data = new_arr

    def is_undefined(self):
        self.has_data_or_raise()
        return is_undefined_uniform(self.array, self.data_type)

    def is_special(self):
        self.has_data_or_raise()
        if self.options.special is None:
            return np.zeros_like(self.array, dtype=bool)
        return np.isclose(
            self.array,
            self.options.special,
            rtol=self.array.rtol,
            atol=self.array.atol,
            equal_nan=self.array.equal_nan,
        )

    def generate_update(self, mask=None):
        """
        :param mask: a boolean array signifying which indices should be returned. If there are no
        changes for a specific index, its value should be `self.data_type.undefined`
        :return:
        """
        if mask is None:
            data = self.array[self.array.changed]
        else:
            mask = np.array(mask, dtype=bool)
            data = self.array.copy()
            data[~self.array.changed] = self.data_type.undefined
            data = data[mask]

        return {"data": data}

    def to_dict(self):
        return {"data": self.array.copy()}

    def reset(self):
        self.array.reset()


class CSRProperty(Property):
    def __init__(
        self,
        data,
        data_type: DataType,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
        options: t.Optional[PropertyOptions] = None,
        index: t.Optional[Index] = None,
    ):
        if data is not None:
            data = ensure_csr_data(data, data_type=data_type)
        super().__init__(data, data_type, flags, rtol, atol, options, index)

    @property
    def csr(self) -> TrackedCSRArray:
        return self._data

    @csr.setter
    def csr(self, value):
        self._data = ensure_csr_data(value)

    def __len__(self):
        if self.csr is not None:
            return len(self.csr.row_ptr) - 1
        return 0

    def slice(self, item):
        return self.csr.slice(item)

    def update(
        self,
        value: t.Union[CSRPropertyData, TrackedCSRArray, t.Tuple[np.ndarray, np.ndarray]],
        indices: np.ndarray,
        process_undefined=False,
    ):
        value = ensure_csr_data(value)
        if not process_undefined:
            value, indices = self.strip_undefined(value, indices)
        if len(indices) == 0:
            return
        if dtype := determine_new_unicode_dtype(self.csr.data, value.data):
            self.csr = self.csr.astype(dtype)
        self.csr.update(value, indices)

    def strip_undefined(
        self, value: TrackedCSRArray, indices: np.ndarray
    ) -> t.Tuple[TrackedCSRArray, np.ndarray]:

        is_undefined = isclose(value.data, self.data_type.undefined, equal_nan=True)
        if len(is_undefined.shape) > 1:
            num_undefined = np.sum(np.all(is_undefined, axis=-1))
            new_data_shape = (value.data.shape[0] - num_undefined, *value.data.shape[1:])
        else:
            num_undefined = np.sum(is_undefined)
            new_data_shape = (value.data.shape[0] - num_undefined,)

        if num_undefined == 0:
            return value, indices

        new_data, new_row_ptr, new_indices = remove_undefined_csr(
            value.data,
            value.row_ptr,
            np.array(indices),
            self.data_type.undefined,
            num_undefined,
            new_data_shape,
        )

        return TrackedCSRArray(new_data, new_row_ptr), new_indices

    def _do_resize(self, new_size: int):
        curr_size = len(self)
        curr_arr = self._data
        new_rowptr = np.concatenate(
            (curr_arr.row_ptr, np.arange(new_size - curr_size) + (1 + self._data.row_ptr[-1]))
        )
        new_data = np.concatenate(
            (
                curr_arr.data,
                np.full(
                    (new_size - curr_size, *self.data_type.unit_shape),
                    fill_value=self.data_type.undefined,
                    dtype=self.data_type.np_type,
                ),
            )
        )
        if curr_arr.changed is None:
            new_changed = None
        else:
            new_changed = np.concatenate(
                (
                    curr_arr.changed,
                    np.zeros((new_size - curr_size,), dtype=bool),
                )
            )

        self._data = TrackedCSRArray(
            new_data,
            new_rowptr,
            rtol=curr_arr.rtol,
            atol=curr_arr.atol,
            equal_nan=curr_arr.equal_nan,
        )
        self._data.changed = new_changed

    def is_undefined(self):
        self.has_data_or_raise()
        return is_undefined_csr(self.csr, self.data_type)

    def is_special(self):
        self.has_data_or_raise()
        if self.options.special is None:
            return np.zeros_like(self.csr.data, dtype=bool)
        return np.isclose(
            self.csr.data,
            self.options.special,
            rtol=self.csr.rtol,
            atol=self.csr.atol,
            equal_nan=self.csr.equal_nan,
        )

    def generate_update(self, mask=None):
        """
        :param mask: a boolean array signifying which indices should be returned. If there are no
        changes for a specific index, its value will be `self.data_type.undefined`
        :return:
        """
        if dtype := determine_new_unicode_dtype(
            self.csr.data, np.array([self.data_type.undefined])
        ):
            self.csr = self.csr.astype(dtype)

        if mask is None:
            data = self.csr.slice(self.csr.changed)
            arr, row_ptr = data.data, data.row_ptr
        else:
            mask = np.array(mask, dtype=bool)
            arr, row_ptr = generate_update(
                self.csr.data,
                self.csr.row_ptr,
                mask=mask,
                changed=self.csr.changed,
                undefined=self.data_type.undefined,
            )

        return {"data": arr, DEFAULT_ROWPTR_KEY: row_ptr}

    def to_dict(self):
        return {
            "data": self.csr.data.copy(),
            DEFAULT_ROWPTR_KEY: self.csr.row_ptr.copy(),
        }

    def reset(self):
        self.csr.reset()


PropertyObject = t.Union[UniformProperty, CSRProperty]


def get_undefined_array(
    data_type: DataType, length: int, rtol=1e-5, atol=1e-8, override_dtype=None
) -> TrackedArrayType:
    data = np.full(
        (length, *data_type.unit_shape),
        fill_value=data_type.undefined,
        dtype=override_dtype or data_type.np_type,
    )

    if data_type.csr:
        return TrackedCSRArray(
            data=data,
            row_ptr=np.arange(0, length + 1),
            rtol=rtol,
            atol=atol,
            equal_nan=True,
        )
    return TrackedArray(data, rtol=rtol, atol=atol, equal_nan=True)


def create_empty_property(data_type, length=None, rtol=1e-5, atol=1e-8, options=None):
    prop_t = CSRProperty if data_type.csr else UniformProperty
    arr = None if length is None else get_undefined_array(data_type, length, rtol=rtol, atol=atol)
    return prop_t(arr, data_type, rtol=rtol, atol=atol, options=options)


def create_empty_property_for_data(data: NumpyPropertyData, length: int):
    data_type = infer_data_type_from_array(data)
    return create_empty_property(
        data_type,
        length=length,
    )


def ensure_uniform_data(
    value: t.Union[dict, np.ndarray, list], data_type: t.Optional[DataType] = None
) -> TrackedArray:
    if isinstance(value, TrackedArray):
        return value

    if isinstance(value, dict) and "data" in value:
        if has_rowptr_key(value):
            raise TypeError("You're trying assign a CSR array to a uniform array property")
        value = value["data"]

    if isinstance(value, (list, np.ndarray)):
        value = ensure_array(value, data_type)
        return TrackedArray(value)

    raise TypeError(f"Cannot read value of type {type(value)} as valid input")


def ensure_csr_data(
    value: t.Union[dict, TrackedCSRArray, t.Tuple[np.ndarray, np.ndarray], t.List[list]],
    data_type: t.Optional[DataType] = None,
) -> TrackedCSRArray:

    if isinstance(value, TrackedCSRArray):
        return value

    if isinstance(value, list) and (len(value) == 0 or isinstance(value[0], (list, np.ndarray))):
        data, row_ptr = convert_nested_list_to_csr(value, data_type)

    elif isinstance(value, dict):
        if "data" not in value:
            raise TypeError("Cannot read value as valid input: missing 'data' key")
        if not has_rowptr_key(value):
            raise TypeError("Cannot read value as valid input: missing row pointer key")

        data, row_ptr = value["data"], get_rowptr(value)

    elif isinstance(value, tuple) and len(value) == 2:
        data, row_ptr = value

    else:
        raise TypeError(f"Cannot read value of type {type(value)} as valid input")

    data = ensure_array(data, data_type)
    row_ptr = np.asarray(row_ptr, dtype="<i4")
    return TrackedCSRArray(data, row_ptr)


def ensure_array(data: t.Union[list, np.ndarray], data_type: t.Optional[DataType] = None):
    if isinstance(data, list):
        data = np.array(data)

    if data_type is not None and data_type.py_type is not str and data.dtype != data_type.np_type:
        data = data.astype(data_type.np_type)

    if isinstance(data, np.ndarray):
        if data_type is not None and (
            dtype := determine_new_unicode_dtype(data, data_type.undefined)
        ):
            data = np.asanyarray(data, dtype=dtype)
    return data


def convert_nested_list_to_csr(
    nested_list: t.List[t.List[object]], data_type: t.Optional[DataType] = None
):
    indptr = [0]
    data = []
    for entry in nested_list:
        if entry is None:
            entry = [data_type.undefined]
        data.extend(entry)
        indptr.append(len(data))
    return ensure_array(data, data_type), np.array(indptr, dtype="<i4")


def get_property_aggregate(prop: PropertyObject, func: callable) -> t.Optional[bool, int, float]:
    data = prop.array if isinstance(prop, UniformProperty) else prop.csr.data

    if data is None or (undefined := get_undefined(data.dtype)) is None:
        return None
    return get_array_aggregate(np.asarray(data), func, exclude=undefined)


def get_array_aggregate(array, func, exclude=None):
    try:
        if exclude is not None:
            array = array[array != exclude]
        rv = func(array)
        rv = None if np.isnan(rv) else rv
        return rv
    except (TypeError, ValueError):
        # Things like unicode arrays or zero length arrays don't have min/max
        return None


property_min = functools.partial(get_property_aggregate, func=np.nanmin)
property_max = functools.partial(get_property_aggregate, func=np.nanmax)
