import dataclasses
import typing as t

from movici_simulation_core.types import AttributeIdentifier

from .data_type import DataType


@dataclasses.dataclass(frozen=True)
class AttributeSpec:
    name: str
    data_type: DataType = dataclasses.field(compare=False)
    component: t.Optional[str] = None
    enum_name: t.Optional[str] = dataclasses.field(default=None, compare=False)

    def __post_init__(self):
        if not isinstance(self.data_type, DataType) and self.data_type in (bool, str, float, int):
            # bypass frozen dataclass (we're still in object instantiation, so it's fine)
            object.__setattr__(self, "data_type", DataType(self.data_type))

    @property
    def full_name(self):
        return attrstring(self.name, self.component)

    @property
    def key(self) -> AttributeIdentifier:
        return (self.component, self.name)


def attrstring(attribute_name: str, component: t.Optional[str] = None):
    return f"{component}/{attribute_name}" if component else attribute_name
