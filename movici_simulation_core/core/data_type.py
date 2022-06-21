import dataclasses
import typing as t

import numpy as np

T = t.TypeVar("T", bool, int, float, str)


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


def get_undefined(dtype):
    return {
        **UNDEFINED,
        **{np_type: UNDEFINED[py_type] for py_type, np_type in NP_TYPES.items()},
    }.get(dtype)
