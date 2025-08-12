import enum
import typing as t

import numpy as np

Timestamp = int
NextTime = t.Optional[int]
RawUpdateData = t.Optional[bytes]
RawResult = tuple[RawUpdateData, NextTime]
UpdateData = t.Optional[dict]
Result = tuple[UpdateData, NextTime]


class UniformAttributeData(t.TypedDict):
    data: np.ndarray


class CSRAttributeData(t.TypedDict, total=False):
    data: np.ndarray
    ind_ptr: np.ndarray | None
    indptr: np.ndarray | None
    row_ptr: np.ndarray | None


NumpyAttributeData = t.Union[UniformAttributeData, CSRAttributeData]
EntityData = dict[str, NumpyAttributeData]
DatasetData = dict[str, EntityData]

ValueType = t.Union[int, float, bool, str]


class DataMask(t.TypedDict):
    pub: dict | None
    sub: dict | None


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


class ExternalSerializationStrategy:
    def __init__(
        self,
        schema,
        non_data_dict_keys: t.Container[str] = ("general",),
        cache_inferred_attributes: bool = False,
    ) -> None:
        self.schema = schema
        self.non_data_dict_keys = non_data_dict_keys
        self.cache_inferred_attributes = cache_inferred_attributes

    def dumps(self, data, type: FileType):
        raise NotImplementedError

    def loads(self, raw_data, type: FileType):
        raise NotImplementedError

    def supported_file_types(self) -> t.Sequence[FileType]:
        raise NotImplementedError

    def supported_file_type_or_raise(self, filetype: FileType):
        if filetype not in self.supported_file_types():
            raise TypeError(f"Unsupported file type '{type}'")


class InternalSerializationStrategy:
    def dumps(self, data):
        raise NotImplementedError

    def loads(self, raw_data):
        raise NotImplementedError
