from __future__ import annotations

import dataclasses
import datetime
import enum
import pathlib
import typing as t
from uuid import UUID

from movici_simulation_core.core import AttributeSpec, DataType


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


AttributeDataType = type[bool | int | float | str]


def utcnow():
    return datetime.datetime.now(tz=datetime.UTC)


@dataclasses.dataclass
class Workspace:
    name: str
    display_name: str
    id: UUID | None = dataclasses.field(compare=False, default=None)


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

    @classmethod
    def from_attribute_spec(cls, spec: AttributeSpec):
        return cls(name=spec.name, data_type=spec.data_type)


@dataclasses.dataclass
class ModelType:
    name: str
    jsonschema: dict

    id: UUID | None = dataclasses.field(compare=False, default=None)


DatasetData = dict | bytes | t.BinaryIO | pathlib.Path


@dataclasses.dataclass
class Dataset:
    name: str
    display_name: str
    dataset_type: DatasetType
    id: UUID | None = None
    workspace: Workspace | None = None

    general: dict | None = None
    espg_code: int | None = None
    bounding_box: tuple[float, float, float, float] | None = None  # minx miny maxx maxy
    created_at: datetime.datetime = dataclasses.field(default_factory=utcnow)
    updated_at: datetime.datetime = dataclasses.field(default_factory=utcnow)

    data: DatasetData | None = None


@dataclasses.dataclass
class Scenario:
    name: str
    display_name: str
    description: str

    epsg_code: int
    bounding_box: tuple[float, float, float, float] | None = None  # minx miny maxx maxy
    simulation_info: dict = dataclasses.field(default_factory=dict)

    id: UUID | None = None
    workspace: Workspace | None = None
    created_at: datetime.datetime = dataclasses.field(default_factory=utcnow)
    updated_at: datetime.datetime = dataclasses.field(default_factory=utcnow)
    models: list[dict] = dataclasses.field(default_factory=list)
    datasets: list[dict] = dataclasses.field(default_factory=list)
