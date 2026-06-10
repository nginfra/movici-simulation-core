from __future__ import annotations

import enum
import typing as t

import numpy as np

if t.TYPE_CHECKING:
    from movici_simulation_core import AttributeSchema

Timestamp = int
NextTime = t.Optional[int]
RawUpdateData = t.Optional[bytes]
RawResult = t.Tuple[RawUpdateData, NextTime]
UpdateData = t.Optional[dict]
Result = t.Tuple[UpdateData, NextTime]


class UniformAttributeData(t.TypedDict):
    data: np.ndarray


class CSRAttributeData(UniformAttributeData, total=False):
    ind_ptr: np.ndarray
    indptr: np.ndarray
    row_ptr: np.ndarray


NumpyAttributeData = t.Union[UniformAttributeData, CSRAttributeData]
EntityData = t.Dict[str, NumpyAttributeData]
DatasetData = t.Dict[str, EntityData]

ValueType = t.Union[int, float, bool, str]


class DataMask(t.TypedDict):
    pub: t.Optional[dict]
    sub: t.Optional[dict]


class FileType(enum.Enum):
    JSON = (".json",)
    MSGPACK = (".msgpack",)
    CSV = (".csv",)
    NETCDF = (".nc",)
    OTHER = (".dat",)

    @property
    def default_extension(self):
        return self.value[0]

    @classmethod
    def from_extension(cls, ext):
        for member in cls.__members__.values():
            if ext.lower() in member.value:
                return member
        return cls.OTHER


class ExternalSerializationStrategy:
    def with_schema(self, schema: AttributeSchema) -> ExternalSerializationStrategy:
        raise NotImplementedError

    def dumps(
        self, data: dict, filetype: FileType, non_data_dict_keys: t.Sequence[str] | None = None
    ) -> bytes:
        raise NotImplementedError

    def loads(
        self, raw_data: bytes, type: FileType, non_data_dict_keys: t.Sequence[str] | None = None
    ) -> dict:
        raise NotImplementedError

    def supported_file_types(self) -> t.Sequence[FileType]:
        raise NotImplementedError

    def supported_file_type_or_raise(self, filetype: FileType):
        if filetype not in self.supported_file_types():
            raise TypeError(f"Unsupported file type '{type}'")


T = t.TypeVar("T", bytes, dict)


class InternalSerializationStrategy(t.Protocol[T]):
    def dumps(self, data: dict) -> T:
        raise NotImplementedError

    def loads(self, raw_data: T) -> dict:
        raise NotImplementedError
