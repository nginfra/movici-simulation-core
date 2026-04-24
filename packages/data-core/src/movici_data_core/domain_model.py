from __future__ import annotations

import dataclasses
import datetime
import enum
import pathlib
import typing as t
from uuid import UUID

from movici_simulation_core.core import AttributeSpec, DataType
from movici_simulation_core.validate import MoviciDataRefInfo


class DatasetFormat(str, enum.Enum):
    """Format types for dataset storage.

    Matches the ``format`` field used in the platform:

    * ``ENTITY_BASED``: Entity-oriented JSON data, destructured into numpy arrays
    * ``UNSTRUCTURED``: Unstructured JSON data, stored as blob but JSON-loadable
    * ``BINARY``: Binary data, stored as blob and passed transparently
    """

    ENTITY_BASED = "entity_based"
    UNSTRUCTURED = "unstructured"
    BINARY = "binary"


class ScenarioStatus(str, enum.Enum):
    FAILED = "Failed"
    INVALID = "Invalid"
    READY = "Ready"
    RUNNING = "Running"
    SUCCEEDED = "Succeeded"


AttributeDataType = type[bool | int | float | str]


def utcnow():
    return datetime.datetime.now(tz=datetime.UTC)


@dataclasses.dataclass
class Workspace:
    name: str
    display_name: str
    id: UUID | None = dataclasses.field(compare=False, default=None)
    scenario_count: int = 0
    dataset_count: int = 0


@dataclasses.dataclass
class DatasetType:
    name: str
    format: DatasetFormat
    mimetype: str | None = None
    id: UUID | None = dataclasses.field(compare=False, default=None)


@dataclasses.dataclass
class EntityType:
    name: str
    id: UUID | None = dataclasses.field(compare=False, default=None)


@dataclasses.dataclass
class AttributeType:
    name: str
    data_type: DataType

    id: UUID | None = dataclasses.field(compare=False, default=None)

    unit: str = ""
    description: str = ""
    enum_name: str | None = None

    @classmethod
    def from_attribute_spec(cls, spec: AttributeSpec):
        return cls(name=spec.name, data_type=spec.data_type, enum_name=spec.enum_name)

    def to_attribute_spec(self):
        return AttributeSpec(name=self.name, data_type=self.data_type, enum_name=self.enum_name)


@dataclasses.dataclass
class ModelType:
    name: str
    jsonschema: dict

    id: UUID | None = dataclasses.field(compare=False, default=None)


@dataclasses.dataclass(frozen=True)
class BoundingBox:
    min_x: float | None
    min_y: float | None
    max_x: float | None
    max_y: float | None

    @classmethod
    def empty(cls) -> BoundingBox:
        return BoundingBox(None, None, None, None)

    def as_tuple_or_none(self):
        if any(v is None for v in (self.min_x, self.min_y, self.max_x, self.max_y)):
            return None
        return (self.min_x, self.min_y, self.max_x, self.max_y)


@dataclasses.dataclass
class Scenario:
    name: str
    display_name: str
    description: str

    epsg_code: int
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)
    simulation_info: dict = dataclasses.field(default_factory=dict)
    status: ScenarioStatus = ScenarioStatus.READY

    id: UUID | None = None
    workspace: Workspace | None = None
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None
    models: list[dict] = dataclasses.field(default_factory=list)
    datasets: list[dict] = dataclasses.field(default_factory=list)
    has_updates: bool = False


@dataclasses.dataclass
class ScenarioDataset:
    name: str
    type: str
    id: UUID | None = dataclasses.field(compare=False, default=None)


@dataclasses.dataclass
class ScenarioModel:
    name: str
    type: ModelType
    config: dict = dataclasses.field(default_factory=dict)
    references: list[MoviciDataRefInfo] = dataclasses.field(default_factory=list, compare=False)


DatasetData = dict | bytes | t.BinaryIO | pathlib.Path


@dataclasses.dataclass
class Dataset:
    name: str
    display_name: str
    dataset_type: DatasetType
    id: UUID | None = None
    workspace: Workspace | None = None

    general: dict | None = None
    epsg_code: int | None = None
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)
    created_at: datetime.datetime | None = None
    updated_at: datetime.datetime | None = None

    data: DatasetData | None = None
    has_data: bool = False


@dataclasses.dataclass
class Update:
    dataset: ScenarioDataset
    timestamp: int
    iteration: int

    model_name: str
    model_type: str | None = None

    id: UUID | None = None
    data: DatasetData | None = None


@dataclasses.dataclass
class DatasetSummary:
    general: dict
    epsg_code: int | None
    bounding_box: BoundingBox
    entity_groups: list[EntityGroupSummary]
    count: int


@dataclasses.dataclass
class EntityGroupSummary:
    name: str
    count: int
    attributes: list[AttributeSummary]


T_datatype = t.TypeVar("T_datatype", bool, int, float, str)


@dataclasses.dataclass
class AttributeSummary(t.Generic[T_datatype]):
    name: str
    data_type: DataType[T_datatype]
    description: str
    enum_name: str | None
    unit: str
    min_val: T_datatype | None
    max_val: T_datatype | None
