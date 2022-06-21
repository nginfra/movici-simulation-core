import dataclasses
import typing as t

from .data_type import DataType


@dataclasses.dataclass(frozen=True)
class AttributeSpec:
    name: str
    data_type: DataType = dataclasses.field(compare=False)
    enum_name: t.Optional[str] = dataclasses.field(default=None, compare=False)

    def __post_init__(self):
        if not isinstance(self.data_type, DataType) and self.data_type in (bool, str, float, int):
            # bypass frozen dataclass (we're still in object instantiation, so it's fine)
            object.__setattr__(self, "data_type", DataType(self.data_type))
