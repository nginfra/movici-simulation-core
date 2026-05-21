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
    UNKNOWN = "unknown"


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
    scenario_count: int | None = None
    dataset_count: int | None = None


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


class BoundingBox(t.NamedTuple):
    """Representation of a bounding box, if any of the components are ``None``, the bounding box
    is considered incomplete and reduces to ``None``
    """

    min_x: float | None
    min_y: float | None
    max_x: float | None
    max_y: float | None

    @classmethod
    def empty(cls) -> BoundingBox:
        """Return an empty BoundingBox (all fields set to None) that can be use as a basis for
        generating a bounding box from multiple datasets/updates
        """
        return BoundingBox(None, None, None, None)

    def as_tuple_or_none(self):
        if self.min_x is None or self.min_y is None or self.max_x is None or self.max_y is None:
            return None
        return self


@dataclasses.dataclass
class SimulationInfo:
    """A class to hold information about the time settings of the scenario. In a simulation, time
    progresses in discrete intervals, each with a time step of ``time_scale`` seconds. The total
    duration of the simulation is ``duration`` discrete intervals. The simulation starts at the
    discrete time step ``start_time``. For purposes of calculating the absolute (wall clock) time
    in the simulation, at ``t=start_time``, the absolute time has a unix timestamp
    ``reference``

    :param duration: the duration of the scenario in discrete time steps
    :param reference: the unix timestamp inside the simulation at ``t=0``
    :param time_scale: the size of a single discrete timestep in seconds. Default: ``1``
    :param start_time: the discrete time step to start the simulation at, usually ``t=0``.
      default: ``0``
    :param mode: must be set to ``"time_oriented". Default ``"time_oriented"``
    """

    duration: int
    reference: float
    time_scale: float = 1
    start_time: int = 0
    mode: t.Literal["time_oriented"] = "time_oriented"

    @classmethod
    def default(cls):
        return cls(reference=0, duration=1)


@dataclasses.dataclass
class Scenario:
    name: str
    display_name: str
    description: str

    epsg_code: int
    bounding_box: BoundingBox = dataclasses.field(default_factory=BoundingBox.empty)
    simulation_info: SimulationInfo = dataclasses.field(default_factory=SimulationInfo.default)
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
    created_at: datetime.datetime | None = None
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
