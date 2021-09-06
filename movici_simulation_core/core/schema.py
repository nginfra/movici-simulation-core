from __future__ import annotations
import dataclasses
import typing as t
import numpy as np

from movici_simulation_core.types import PropertyIdentifier


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


@dataclasses.dataclass
class DataType(t.Generic[T]):
    py_type: t.Type[T]
    unit_shape: t.Tuple[int, ...]
    csr: bool

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
    return d[next(iter(d.keys() & ALL_ROWPTR_KEYS))]


def infer_data_type_from_array(attr_data: dict):
    pytypes = {"i": int, "f": float, "U": str, "b": bool}
    data = attr_data["data"]
    return DataType(
        pytypes[attr_data["data"].dtype.kind],
        data.shape[1:],
        has_rowptr_key(attr_data),
    )
