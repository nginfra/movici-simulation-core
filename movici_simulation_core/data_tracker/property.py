from __future__ import annotations

import abc
import dataclasses as dc
import typing as t

import numpy as np

from .arrays import TrackedArrayType, TrackedCSRArray, TrackedArray
from .csr_helpers import generate_update
from .index import Index
from .types import CSRPropertyData, UniformPropertyData, PropertyIdentifier
from .unicode_helpers import determine_new_unicode_dtype

if t.TYPE_CHECKING:
    from .entity_group import EntityGroup

# Property pub/sub flags
INIT = 1  # This property is required for initialization
SUB = 1 << 1  # This property is required to start calculating updates
OPT = 1 << 2  # The model is interested in this property, but it's optional
PUB = 1 << 3  # The model publishes this property


# todo: do we want this?
#  IMMUTABLE = 1 << 4  # the model doesn't support it when this property changes once set


class PropertyField:
    def __init__(
        self,
        spec: PropertySpec,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
    ):
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


@dc.dataclass(frozen=True)
class PropertySpec:
    name: str
    data_type: DataType = dc.field(compare=False)
    component: t.Optional[str] = None
    enum_name: t.Optional[str] = dc.field(default=None, compare=False)

    @property
    def full_name(self):
        return propstring(self.name, self.component)

    @property
    def key(self) -> PropertyIdentifier:
        return (self.component, self.name)


UNDEFINED = {
    bool: np.iinfo(np.dtype("<i1")).min,
    int: np.iinfo(np.dtype("<i4")).min,
    float: np.nan,
    str: "_udf_",
}

NP_TYPES = {
    bool: np.dtype("<i1"),
    int: np.dtype("<i4"),
    float: np.dtype("f8"),
    str: np.dtype("<U8"),
}


@dc.dataclass
class DataType(t.Generic[T]):
    py_type: t.Type[T]
    unit_shape: t.Tuple[int, ...]
    csr: bool
    enum_name: t.Optional[str] = None

    @property
    def undefined(self):
        return UNDEFINED[self.py_type]

    @property
    def np_type(self):
        return NP_TYPES[self.py_type]


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

    def __len__(self):
        if self.array is not None:
            return self.array.shape[0]
        return 0

    def __getitem__(self, item):
        return self.array[item]

    def __setitem__(self, key, value):
        if np.isscalar(value):
            if value == self.data_type.undefined:
                return
        else:
            value = self._prevent_undefined(key, value)

        if dtype := determine_new_unicode_dtype(self.array, value):
            self.array = self.array.astype(dtype)
        self.array[key] = value

    def _prevent_undefined(self, key, value):
        value = np.array(value, copy=True)
        undefs = _is_undefined(value, self.data_type.undefined)
        if np.any(undefs):
            current = self.array[key]
            value[undefs] = current[undefs]
        return value

    def update(self, value: t.Union[np.ndarray, UniformPropertyData], indices: np.ndarray):
        value = ensure_uniform_data(value)
        self[indices] = value

    def is_undefined(self):
        self.has_data_or_raise()

        undefs = _is_undefined(self.array, self.data_type.undefined)

        # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be
        # reduced to a result array of shape (10,) by reducing over axes (1,2). An single
        # entity's property is considered undefined if the item is undefined in all it's dimensions
        reduction_axes = tuple(range(1, len(undefs.shape)))
        return np.minimum.reduce(undefs, axis=reduction_axes)

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
        return {"data": self.array}

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
            return self.csr.row_ptr[-1]
        return 0

    def update(
        self,
        value: t.Union[CSRPropertyData, TrackedCSRArray, t.Tuple[np.ndarray, np.ndarray]],
        indices: np.ndarray,
    ):
        value = ensure_csr_data(value)
        if dtype := determine_new_unicode_dtype(self.csr.data, value.data):
            self.csr = self.csr.astype(dtype)
        self.csr.update(value, indices, skip_value=self.data_type.undefined)

    def is_undefined(self):
        self.has_data_or_raise()
        return self.csr.rows_equal(np.array([self.data_type.undefined]))

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
        changes for a specific index, its value should be `self.data_type.undefined`
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

        return {"data": arr, "indptr": row_ptr}

    def to_dict(self):
        return {"data": self.csr.data, "indptr": self.csr.row_ptr}

    def reset(self):
        self.csr.reset()


def _is_undefined(a, undefined):
    result = a == undefined
    if not isinstance(undefined, str) and np.isnan(undefined):
        return result | np.isnan(a)
    return result


PropertyObject = t.Union[UniformProperty, CSRProperty]


def get_undefined_array(
    data_type: DataType, length: int, rtol=1e-5, atol=1e-8
) -> TrackedArrayType:
    data = np.full(
        (length, *data_type.unit_shape), fill_value=data_type.undefined, dtype=data_type.np_type
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


def ensure_csr_data(
    value: t.Union[dict, TrackedCSRArray, t.Tuple[np.ndarray, np.ndarray]],
    data_type: t.Optional[DataType] = None,
) -> TrackedCSRArray:
    row_ptr_keys = {"row_ptr", "indptr", "ind_ptr"}

    if isinstance(value, TrackedCSRArray):
        return value

    if isinstance(value, list):
        if not value or isinstance(value[0], list):
            value = convert_nested_list_to_csr(value, data_type.np_type)

    if isinstance(value, tuple) and len(value) == 2:
        value = np.asarray(value[0], dtype=getattr(data_type, "np_type", None)), np.asarray(
            value[1], dtype="<i4"
        )
        return TrackedCSRArray(value[0], value[1])

    if isinstance(value, dict):
        if "data" not in value:
            raise TypeError("Cannot read value as valid input: missing 'data' key")
        if not (value.keys() & row_ptr_keys):
            raise TypeError("Cannot read value as valid input: missing row pointer key")

        row_ptr = next(iter(value.keys() & row_ptr_keys))
        return TrackedCSRArray(value["data"], value[row_ptr])

    raise TypeError(f"Cannot read value of type {type(value)} as valid input")


def convert_nested_list_to_csr(nested_list: t.List[t.List[object]], dtype: np.dtype):
    indptr = [0]
    data = []
    for entry in nested_list:
        data.extend(entry)
        indptr.append(len(data))
    return np.array(data, dtype=dtype), np.array(indptr, dtype="<i4")


def ensure_uniform_data(
    value: t.Union[dict, np.ndarray, list], data_type: t.Optional[DataType] = None
) -> TrackedArray:
    if isinstance(value, TrackedArray):
        return value

    if isinstance(value, (np.ndarray, list)):
        return TrackedArray(np.asanyarray(value, dtype=getattr(data_type, "np_type", None)))

    if isinstance(value, dict) and "data" in value:
        if value.keys() & {"row_ptr", "indptr", "ind_ptr"}:
            raise TypeError("You're trying assign a CSR array to a uniform array property")
        return TrackedArray(value["data"])

    raise TypeError(f"Cannot read value of type {type(value)} as valid input")


def propstring(property_name: str, component: t.Optional[str] = None):
    return f"{component}/{property_name}" if component else property_name
