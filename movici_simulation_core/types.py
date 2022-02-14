import enum
import typing as t

import numpy as np

Timestamp = int
NextTime = t.Optional[int]
RawUpdateData = t.Optional[bytes]
RawResult = t.Tuple[RawUpdateData, NextTime]
UpdateData = t.Optional[dict]
Result = t.Tuple[UpdateData, NextTime]


class UniformAttributeData(t.TypedDict):
    data: np.ndarray


class CSRAttributeData(t.TypedDict, total=False):
    data: np.ndarray
    ind_ptr: t.Optional[np.ndarray]
    indptr: t.Optional[np.ndarray]
    row_ptr: t.Optional[np.ndarray]


NumpyAttributeData = t.Union[UniformAttributeData, CSRAttributeData]
ComponentData = t.Dict[str, NumpyAttributeData]
EntityData = t.Dict[str, t.Union[NumpyAttributeData, ComponentData]]
DatasetData = t.Dict[str, EntityData]
# TODO: PropertyIdentifier is deprecated
PropertyIdentifier = t.Tuple[t.Optional[str], str]
AttributeIdentifier = PropertyIdentifier
ValueType = t.Union[int, float, bool, str]


class DataMask(t.TypedDict):
    pub: t.Optional[dict]
    sub: t.Optional[dict]


class FileType(enum.Enum):
    JSON = (".json",)
    MSGPACK = (".msgpack",)
    CSV = (".csv",)
    NETCDF = (".nc",)
    OTHER = ()

    @classmethod
    def from_extension(cls, ext):
        for member in cls.__members__.values():
            if ext.lower() in member.value:
                return member
        return cls.OTHER
