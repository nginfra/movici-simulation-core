from __future__ import annotations

import dataclasses
import typing as t

import numpy as np

from movici_simulation_core.core.plugins import Extensible, Plugin
from movici_simulation_core.types import PropertyIdentifier
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray


class AttributeSchema(Extensible):
    def __init__(self, attributes: t.Optional[t.Iterable[PropertySpec]] = None):
        self.attributes: t.Dict[PropertyIdentifier, PropertySpec] = {}
        attributes = attributes or ()
        for attr in attributes:
            self.add_attribute(attr)

    def __getitem__(self, item):
        return self.attributes[item]

    def get(self, key, default=None):
        return self.attributes.get(key, default)

    def get_spec(
        self,
        identifier: PropertyIdentifier,
        default_data_type: t.Union[DataType, t.Callable[[], DataType], None],
        cache=False,
    ):
        if spec := self.get(tuple(identifier)):
            return spec
        if default_data_type is None:
            return None
        component, name = identifier
        data_type = default_data_type() if callable(default_data_type) else default_data_type
        spec = PropertySpec(name=name, component=component, data_type=data_type)
        if cache:
            self.add_attribute(spec)
        return spec

    def add_attributes(self, attributes: t.Iterable[PropertySpec]):
        for attr in attributes:
            self.add_attribute(attr)

    def add_attribute(self, attr: PropertySpec):
        if current := self.get(attr.key):
            if current.data_type != attr.data_type:
                raise TypeError(
                    f"Duplicate registration of attribute '{attr.full_name}':\n"
                    f"Data type {attr.data_type} is incompatible with "
                    f"data type {current.data_type}"
                )
            if current.enum_name != attr.enum_name:
                raise TypeError(
                    f"Duplicate registration of attribute '{attr.full_name}':\n"
                    f"Enum name {attr.enum_name} does not match with "
                    f"enum name {current.enum_name}"
                )
        self.attributes[attr.key] = attr

    def __len__(self):
        return len(self.attributes)

    def __bool__(self):
        # always return True, even when len() == 0
        return True

    def __iter__(self):
        return iter(self.attributes.values())

    def use(self, plugin):
        plugin.install(self)

    def register_attributes(self, attributes: t.Iterable[PropertySpec]):
        self.add_attributes(attributes)

    def add_from_namespace(self, ns):
        try:
            self.add_attributes(
                attr for attr in vars(ns).values() if isinstance(attr, PropertySpec)
            )

        except TypeError as e:
            raise TypeError("Could not read from namespace") from e


def attribute_plugin_from_dict(d: dict):
    class AttributePlugin(Plugin):
        @classmethod
        def install(cls, obj: Extensible):
            obj.register_attributes(attributes_from_dict(d))

    return AttributePlugin


def attributes_from_dict(d: dict):
    return filter(lambda i: isinstance(i, PropertySpec), d.values())


@dataclasses.dataclass(frozen=True)
class PropertySpec:
    name: str
    data_type: DataType = dataclasses.field(compare=False)
    component: t.Optional[str] = None
    enum_name: t.Optional[str] = dataclasses.field(default=None, compare=False)

    @property
    def full_name(self):
        return propstring(self.name, self.component)

    @property
    def key(self) -> PropertyIdentifier:
        return (self.component, self.name)


T = t.TypeVar("T", bool, int, float, str)


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


@dataclasses.dataclass(frozen=True)
class DataType(t.Generic[T]):
    py_type: t.Type[T]
    unit_shape: t.Tuple[int, ...] = ()
    csr: bool = False

    @property
    def undefined(self):
        return UNDEFINED[self.py_type]

    @property
    def np_type(self):
        return NP_TYPES[self.py_type]

    def is_undefined(self, val):
        undefined = self.undefined
        result = val == undefined
        if not isinstance(undefined, str) and np.isnan(undefined):
            return result | np.isnan(val)
        return result


def propstring(property_name: str, component: t.Optional[str] = None):
    return f"{component}/{property_name}" if component else property_name


ALL_ROWPTR_KEYS = {"row_ptr", "ind_ptr", "indptr"}
DEFAULT_ROWPTR_KEY = "indptr"


def has_rowptr_key(d: dict):
    return bool(d.keys() & ALL_ROWPTR_KEYS)


def get_rowptr(d: dict):
    try:
        return d[next(iter(d.keys() & ALL_ROWPTR_KEYS))]
    except StopIteration:
        return None


def infer_data_type_from_array(attr_data: t.Union[dict, np.ndarray, TrackedCSRArray]):
    pytypes = {"i": int, "f": float, "U": str, "b": bool}
    if isinstance(attr_data, dict):
        data = attr_data["data"]
        is_csr = has_rowptr_key(attr_data)
    elif isinstance(attr_data, TrackedCSRArray):
        data = attr_data
        is_csr = True
    else:
        data = attr_data
        is_csr = False
    return DataType(
        pytypes[data.dtype.kind],
        data.shape[1:],
        is_csr,
    )
