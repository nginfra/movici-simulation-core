from __future__ import annotations
import abc
import functools
from dataclasses import dataclass
import typing as t

import numpy as np

from .arrays import TrackedArrayType, TrackedCSRArray, TrackedArray

# Property pub/sub flags
INIT = 1  # This property is required for initialization
SUB = 1 << 1  # This property is required to start calculating updates
OPT = 1 << 2  # The model is interested in this property, but it's optional
PUB = 1 << 3  # The model publishes this property


class PropertyField:
    attr: str = "unbound_property"

    def __init__(
        self,
        name: str,
        component: t.Optional[str],
        dtype: DataType,
        flags: int = 0,
        rtol=1e-5,
        atol=1e-8,
    ):
        """
        property_name: property name
        component: component name or '' or None
        data_type: the datatype coming from the schema
        flags: one or more boolean flags of `INIT`, `SUB`, `OPT`, `PUB`, eg: `SUB|PUB`
        """
        self.property_name = name
        self.component = component
        self.dtype = dtype
        self.array_type: t.Type[TrackedArrayType] = TrackedCSRArray if dtype.csr else TrackedArray
        self.flags = flags
        self.rtol = rtol
        self.atol = atol

    def __get__(self, instance, owner) -> t.Union["PropertyField", UniformProperty, CSRProperty]:
        if instance is None:
            return self
        return self.get_value_for(instance)

    def __set__(self, instance, value):
        if not isinstance(value, Property):
            raise TypeError("Can only set with Property objects or subclasses")
        self.set_value_for(instance, value)

    def __set_name__(self, owner, name):
        self.attr = name

    def get_value_for(self, instance):
        return instance.__dict__.get(self.attr)

    def set_value_for(self, instance, value):
        instance.__dict__[self.attr] = value

    def initialize_for(self, instance, length):
        self.set_value_for(
            instance, create_property(self.dtype, length, rtol=self.rtol, atol=self.atol)
        )

    @property
    def full_name(self):
        return f"{self.component}/{self.property_name}" if self.component else self.property_name


T = t.TypeVar("T", bool, int, float, str)


@dataclass
class PropertySpec(t.Generic[T]):
    special: t.Optional[T] = None
    enum: t.Optional[t.List[str]] = None


@dataclass
class DataType(t.Generic[T]):
    py_type: t.Type[T]
    unit_shape: t.Tuple[int, ...]
    csr: bool

    @property
    def undefined(self):
        return {
            bool: np.iinfo(np.dtype("i1")).min,
            int: np.iinfo(np.dtype("i4")).min,
            float: np.nan,
            str: "_udf_",
        }[self.py_type]

    @property
    def np_type(self):
        return {
            bool: np.dtype("<i1"),
            int: np.dtype("<i4"),
            float: np.dtype("f8"),
            str: np.dtype("<U8"),
        }[self.py_type]


class Property(abc.ABC):
    def __init__(self, data, data_type: DataType, spec: t.Optional[PropertySpec] = None):
        self._data = data
        self.data_type = data_type
        self.spec = spec

    def is_initialized(self):
        return self._data is not None and not np.any(self.is_undefined())

    def has_array_or_raise(self):
        if self._data is None:
            raise ValueError("Uninitialized array")

    @property
    def changed(self):
        self.has_array_or_raise()

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


class UniformProperty(Property):
    """
    The underlying data can be accessed through the `UniformProperty().array` attribute. When
    updating data using indexing ("[]") notation, it is recommended to use
    `UniformProperty()[index]=value`. When dealing with string (ie. unicode) arrays, this feature
    will make sure that the array itemsize will grow if trying to add strings that are larger than
    the  current itemsize.
    """

    @property
    def array(self) -> TrackedArray:
        return self._data

    @array.setter
    def array(self, value):
        if isinstance(value, dict) and "data" in value:
            if value.keys() & {"row_ptr", "indptr", "ind_ptr"}:
                raise TypeError("You're trying assign a CSR array to a uniform array property")
            value = value["data"]

        self._data = TrackedArray(value)

    def __getitem__(self, item):
        return self.array[item]

    def __setitem__(self, key, value):
        if self.array.dtype.type is np.str_:
            if isinstance(value, str) and len(value) > (self.array.dtype.itemsize / 4):
                self.array = self.array.astype(f"<U{len(value)}")
            if (
                isinstance(value, np.ndarray)
                and value.dtype.type is np.str_
                and value.dtype.itemsize > self.array.dtype.itemsize
            ):
                self.array = self.array.astype(value.dtype)
        self.array[key] = value

    def is_undefined(self):
        self.has_array_or_raise()
        undefs = np.isclose(
            self.array,
            self.data_type.undefined,
            rtol=self.array.rtol,
            atol=self.array.atol,
            equal_nan=self.array.equal_nan,
        )

        # reduce over all but the first axis, e.g. an array with shape (10,2,3) should be
        # reduced to a result array of shape (10,) by reducing over axes (1,2). An single
        # entity's property is considered undefined if the item is undefined in all it's dimensions
        reduction_axes = tuple(range(1, len(undefs.shape)))
        return np.minimum.reduce(undefs, axis=reduction_axes)

    def is_special(self):
        self.has_array_or_raise()
        return np.isclose(
            self.array,
            self.spec.special,
            rtol=self.array.rtol,
            atol=self.array.atol,
            equal_nan=self.array.equal_nan,
        )


class CSRProperty(Property):
    @property
    def csr(self) -> TrackedCSRArray:
        return self._data

    @csr.setter
    def csr(self, value):
        if isinstance(value, TrackedCSRArray):
            self._data = value

        if isinstance(value, tuple) and len(value) == 2:
            self._data = TrackedCSRArray(value[0], value[1])

        row_ptr_keys = {"row_ptr", "indptr", "ind_ptr"}
        if isinstance(value, dict) and "data" in value and value.keys() & row_ptr_keys:
            row_ptr = next(iter(value.keys() & row_ptr_keys))
            self._data = TrackedCSRArray(value["data"], value[row_ptr])

        raise TypeError(f"Cannot read value of type {type(value)} as valid input")

    def update(self, updates: "TrackedCSRArray", indices: np.ndarray):
        self.csr.update(updates, indices)

    def is_undefined(self):
        self.has_array_or_raise()
        return self.csr.rows_equal(np.array([self.data_type.undefined]))

    def is_special(self):
        self.has_array_or_raise()
        return np.isclose(
            self.csr.data,
            self.spec.special,
            rtol=self.csr.rtol,
            atol=self.csr.atol,
            equal_nan=self.csr.equal_nan,
        )


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


def define_property(
    name: str,
    component: str,
    dtype: t.Type[t.Union[bool, int, float, str]],
    unit_shape: t.Tuple[int, ...],
    is_csr: bool = False,
) -> t.Callable[[...], PropertyField]:
    return functools.partial(
        PropertyField,
        name=name,
        component=component,
        data_type=DataType(py_type=dtype, unit_shape=unit_shape, csr=is_csr),
    )


def create_property(data_type, length, rtol=1e-5, atol=1e-8, spec=None):
    prop_t = CSRProperty if data_type.csr else UniformProperty

    return prop_t(
        get_undefined_array(data_type, length, rtol=rtol, atol=atol), data_type, spec=spec
    )
