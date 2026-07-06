from __future__ import annotations

import dataclasses
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


class Priority(enum.IntEnum):
    """Publishing priority for a model. Higher values take ownership when multiple models
    publish the same attribute. Values are conventions, not a closed set; a model developer
    may send an arbitrary integer on a ``RegistrationMessage`` when a use case warrants it.
    """

    REGULAR = 10
    SOLVER_HELPER = 20

    @classmethod
    def label_for(cls, value: int) -> str:
        """Return a human-readable label for a priority value. Falls back to ``UNKNOWN`` for
        values that are not in the named enum so error messages stay informative even when a
        model uses a non-standard priority (see issue #127, comment thread)."""
        try:
            return Priority(value).name
        except ValueError:
            return "UNKNOWN"


@dataclasses.dataclass
class AutoRemap:
    """Return value for Model.remap(). Instructs the ModelConnector to install middleware to
    automatically rename incoming or outgoing updates

    :param pub: rename attribute names in outgoing updates
    :param sub: rename attribute names in incoming updates
    """

    pub: bool
    sub: bool

    @classmethod
    def none(cls):
        return AutoRemap(False, False)

    @classmethod
    def default(cls):
        return AutoRemap(True, True)


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
        schema: AttributeSchema | None = None,
        non_data_dict_keys: t.Container[str] = ("general",),
        cache_inferred_attributes: bool = False,
    ) -> None:
        self.schema = schema
        self.non_data_dict_keys = non_data_dict_keys
        self.cache_inferred_attributes = cache_inferred_attributes

    def set_schema(self, schema: AttributeSchema):
        self.schema = schema

    def dumps(self, data: dict, filetype: FileType) -> bytes:
        raise NotImplementedError

    def loads(self, raw_data: bytes, type: FileType) -> dict:
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
