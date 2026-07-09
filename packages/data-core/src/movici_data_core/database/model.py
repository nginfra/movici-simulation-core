from __future__ import annotations

import datetime
import enum
import re
import typing as t
import uuid

import numpy as np
from sqlalchemy import JSON, ForeignKey, String, Text, UniqueConstraint, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from movici_data_core import domain_model
from movici_data_core.domain_model import (
    BoundingBox,
    DatasetFormat,
    ScenarioStatus,
    SimulationInfo,
)
from movici_data_core.exceptions import MoviciValidationError
from movici_simulation_core.core import DataType
from movici_simulation_core.validate import MoviciDataRefInfo

from .db_types import GUID, JSONTuple, RegexMatchingString, TZDateTime

T_dom = t.TypeVar("T_dom", covariant=True)
snake_case_pattern = re.compile(r"[a-z_][a-z0-9_.]*")


class NamedResource(t.Protocol[T_dom]):
    id: Mapped[uuid.UUID]
    name: Mapped[str]

    @classmethod
    def validate_field_lengths(cls, payload: dict[str, t.Any]) -> None: ...
    def to_domain(self) -> T_dom: ...


def to_domain_or_none(obj: NamedResource[T_dom] | None) -> T_dom | None:
    return obj.to_domain() if obj is not None else None


class Base(DeclarativeBase):
    type_annotation_map = {
        uuid.UUID: GUID,
        datetime.datetime: TZDateTime,
        tuple: JSONTuple,
        dict: JSON,
    }

    @classmethod
    def validate_field_lengths(cls, payload: dict[str, t.Any]):
        all_columns = cls.__table__.columns
        string_columns = {
            k: v
            for k, v in all_columns.items()
            if isinstance(v.type, (String, RegexMatchingString))
        }
        keys = payload.keys() & string_columns.keys()
        too_long = {
            key
            for key in keys
            if (max_len := t.cast(String, string_columns[key].type).length) is not None
            and isinstance(payload[key], str)
            and max_len < len(payload[key])
        }
        if too_long:
            raise MoviciValidationError(
                {path: ["length exceeds maximum length"] for path in too_long}
            )


class DatabaseMode(enum.Enum):
    """Mode in which this database (file) runs.

    - ``SINGLE_SCENARIO``: This database contains a single scenario including init data and
      possibly updates
    - ``SINGLE_WORKSPACE``: This database may contain multiple scenarios but all scenarios belong
      to a single workspace
    - ``MULTIPLE_WORKSPACES``: This database may contain multiple workspace, each containing their
      own scenarios, datasets and simulation results
    """

    SINGLE_SCENARIO = "single_scenario"
    SINGLE_WORKSPACE = "single_workspace"
    MULTIPLE_WORKSPACES = "multiple_workspaces"


class AttributeDataType(enum.Enum):
    BOOL = "bool"
    INT = "int"
    FLOAT = "float"
    STR = "str"


DEFAULT_SCHEMA_VERSION = "v1"
DEFAULT_WORKSPACE_NAME = "__default__"
DEFAULT_SCENARIO_NAME = "default_scenario"


DEFAULT_NAME_MAX_LENGTH = 50
DEFAULT_DISPLAY_NAME_MAX_LENGTH = 50

ATTRIBUTE_NAME_MAX_LENGTH = 100
ATTRIBUTE_DESCRIPTION_MAX_LENGTH = 255
ATTRIBUTE_UNIT_MAX_LENGTH = 20
ATTRIBUTE_ENUM_NAME_MAX_LENGTH = 20

DATASET_TYPE_MIMETYPE_MAX_LENGTH = 50

SCENARIO_DESCRIPTION_MAX_LENGTH = 500


class Metadata(Base):
    """A table that should contain a single entry with the schema version of this database. Future
    iterations of the data-core may use this version to determine compatibility or migrate data
    from one version to another
    """

    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(64))


class Options(Base):
    """A table that should contain a single entry with a database's options. It contains the
    database mode (see :class:`DatabaseMode`) and the various ``STRICT_`` options:

    - ``STRICT_DATASET_TYPES``: when set, datasets may only be added to this database if their
      dataset_type exists. If unset, a dataset type will be created with format
      ``DatasetFormat.ENTITY_BASED`` if a dataset is about to be added with a non-exsiting type
    - ``STRICT_ENTITY_TYPES``: when set, an entity type must exist before data for an entity group
      of that type can be added in either a dataset or an update. When unset, an entity type will
      be created when adding data for an entity group of a non-existing type
    - ``STRICT_ATTRIBUTE_TYPES``: when set, an attribute type must exist before an entity group
      can contain data for that attribute. When unset, an attribute type will be created with an
      inferred data type when storing attribute data for that type.
    - ``STRICT_MODEL_TYPES``: when set, a model type must exist before a scenario can be added that
      uses a model of that type. When unset, a model type will be created when adding a scenario
      that uses a model of that type. It will be created with a pass-all schema so that any config
      is allowed, but this also means that no references to datasets, entity groups or attributes
      can be made in the model config
    - ``STRICT_SCENARIO_DATASETS``: when set, every dataset in a scenario config ``"dataset"``
      section must exist before the scenario config may be added. When unset, any a stub for every
      dataset that does not exist will be added when adding a scenario config

    Furthermore, the options singleton contains a reference to the default scenario and/or default
    workspace if they exist (determined by the database mode mode)
    """

    __tablename__ = "options"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[DatabaseMode]

    STRICT_DATASET_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_ENTITY_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_ATTRIBUTE_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_MODEL_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_SCENARIO_DATASETS: Mapped[bool] = mapped_column(default=False)

    default_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="RESTRICT")
    )
    default_scenario_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("scenario.id", ondelete="RESTRICT")
    )
    default_workspace: Mapped[Workspace | None] = relationship()
    default_scenario: Mapped[Scenario | None] = relationship()


class Workspace(Base):
    __tablename__ = "workspace"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH),
        unique=True,
    )
    display_name: Mapped[str] = mapped_column(String(DEFAULT_DISPLAY_NAME_MAX_LENGTH))
    datasets: Mapped[list[Dataset]] = relationship(back_populates="workspace")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="workspace")

    def to_domain(self) -> domain_model.Workspace:
        return domain_model.Workspace(id=self.id, name=self.name, display_name=self.display_name)


class DatasetType(Base):
    __tablename__ = "dataset_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH),
        unique=True,
    )
    format: Mapped[DatasetFormat]
    mimetype: Mapped[str | None] = mapped_column(String(DATASET_TYPE_MIMETYPE_MAX_LENGTH))

    def to_domain(self) -> domain_model.DatasetType:
        return domain_model.DatasetType(
            id=self.id, name=self.name, format=self.format, mimetype=self.mimetype
        )


class Dataset(Base):
    __tablename__ = "dataset"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    workspace: Mapped[Workspace] = relationship(back_populates="datasets")

    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH)
    )
    display_name: Mapped[str] = mapped_column(String(DEFAULT_DISPLAY_NAME_MAX_LENGTH))

    dataset_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset_type.id", ondelete="RESTRICT")
    )
    dataset_type: Mapped[DatasetType] = relationship(DatasetType)

    general: Mapped[dict | None] = mapped_column(JSON)
    epsg_code: Mapped[int | None]
    bounding_box: Mapped[tuple[float, float, float, float] | None] = mapped_column(
        JSONTuple(length=4)
    )

    created_at: Mapped[datetime.datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(default=func.now(), onupdate=func.now())

    def to_domain(
        self, has_raw_data: bool = False, has_attributes: bool = False
    ) -> domain_model.Dataset:
        return domain_model.Dataset(
            id=self.id,
            name=self.name,
            display_name=self.display_name,
            dataset_type=self.dataset_type.to_domain(),
            workspace=self.workspace.to_domain(),
            general=self.general,
            epsg_code=self.epsg_code,
            bounding_box=BoundingBox.from_tuple_or_none(self.bounding_box),
            created_at=self.created_at,
            updated_at=self.updated_at,
            has_data=has_raw_data or has_attributes,
        )


class EntityType(Base):
    __tablename__ = "entity_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH),
        unique=True,
    )

    def to_domain(self) -> domain_model.EntityType:
        return domain_model.EntityType(name=self.name, id=self.id)


class AttributeType(Base):
    __tablename__ = "attribute_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=ATTRIBUTE_NAME_MAX_LENGTH),
        unique=True,
    )
    has_rowptr: Mapped[bool]
    unit_type: Mapped[AttributeDataType]
    unit_shape: Mapped[tuple[int, ...]] = mapped_column(JSONTuple)
    unit: Mapped[str] = mapped_column(String(ATTRIBUTE_UNIT_MAX_LENGTH))
    description: Mapped[str] = mapped_column(String(ATTRIBUTE_DESCRIPTION_MAX_LENGTH))
    enum_name: Mapped[str | None] = mapped_column(
        RegexMatchingString(pattern=r"[a-z][a-z_]*", length=ATTRIBUTE_ENUM_NAME_MAX_LENGTH)
    )

    @property
    def data_type(self):
        py_type = {
            AttributeDataType.BOOL: bool,
            AttributeDataType.INT: int,
            AttributeDataType.FLOAT: float,
            AttributeDataType.STR: str,
        }[self.unit_type]
        return DataType(py_type, unit_shape=self.unit_shape, csr=self.has_rowptr)

    def to_domain(self) -> domain_model.AttributeType:
        return domain_model.AttributeType(
            id=self.id,
            name=self.name,
            data_type=self.data_type,
            unit=self.unit,
            description=self.description,
            enum_name=self.enum_name,
        )


class DataArray(Base):
    __tablename__ = "data_array"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dtype: Mapped[str] = mapped_column(String(20))
    shape: Mapped[tuple] = mapped_column(JSON)
    data: Mapped[bytes]

    min_val: Mapped[float | None]
    max_val: Mapped[float | None]

    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))
    attribute: Mapped[Attribute] = relationship(back_populates="data")

    def to_numpy(self) -> np.ndarray:
        """Reconstruct numpy array from stored data.

        :return: Reconstructed NumPy array
        """
        return np.frombuffer(self.data, dtype=self.dtype).reshape(self.shape)


class RowptrArray(Base):
    __tablename__ = "rowptr_array"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    data: Mapped[bytes]

    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))
    attribute: Mapped[Attribute] = relationship(back_populates="rowptr")

    def to_numpy(self) -> np.ndarray:
        """Reconstruct numpy array from stored data.

        :return: Reconstructed NumPy array
        """
        return np.frombuffer(self.data, dtype=int)


class Attribute(Base):
    __tablename__ = "attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_type.id", ondelete="RESTRICT")
    )
    attribute_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_type.id", ondelete="RESTRICT")
    )
    length: Mapped[int]
    entity_type: Mapped[EntityType] = relationship()
    attribute_type: Mapped[AttributeType] = relationship()
    data: Mapped[DataArray] = relationship()
    rowptr: Mapped[RowptrArray | None] = relationship()


class DatasetAttribute(Base):
    __tablename__ = "dataset_attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"))
    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))

    dataset: Mapped[Dataset] = relationship()
    attribute: Mapped[Attribute] = relationship()


class RawData(Base):
    __tablename__ = "raw_data"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset.id", ondelete="CASCADE"))
    encoding: Mapped[str | None]
    compression: Mapped[str | None]


class RawDataChunk(Base):
    __tablename__ = "raw_data_chunk"
    __table_args__ = (UniqueConstraint("raw_data_id", "sequence"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    raw_data_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("raw_data.id", ondelete="CASCADE"))
    sequence: Mapped[int]
    bytes: Mapped[bytes]


class ModelType(Base):
    __tablename__ = "model_type"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH),
        unique=True,
    )
    jsonschema: Mapped[dict] = mapped_column(JSON)

    def to_domain(self) -> domain_model.ModelType:
        return domain_model.ModelType(id=self.id, name=self.name, jsonschema=self.jsonschema)


class Scenario(Base):
    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    workspace: Mapped[Workspace] = relationship(back_populates="scenarios")

    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH)
    )
    display_name: Mapped[str] = mapped_column(String(DEFAULT_DISPLAY_NAME_MAX_LENGTH))
    description: Mapped[str] = mapped_column(Text(SCENARIO_DESCRIPTION_MAX_LENGTH))
    status: Mapped[ScenarioStatus]

    simulation_info: Mapped[dict] = mapped_column(JSON)

    epsg_code: Mapped[int | None]

    created_at: Mapped[datetime.datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(default=func.now(), onupdate=func.now())

    datasets: Mapped[list[ScenarioDataset]] = relationship()
    models: Mapped[list[ScenarioModel]] = relationship()

    def to_domain(self) -> domain_model.Scenario:
        return domain_model.Scenario(
            id=self.id,
            workspace=self.workspace.to_domain(),
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            simulation_info=SimulationInfo(**self.simulation_info),
            epsg_code=self.epsg_code,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ScenarioDataset(Base):
    __tablename__ = "scenario_dataset"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence"),
        UniqueConstraint("scenario_id", "dataset_id"),
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenario.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset.id", ondelete="RESTRICT"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column()
    scenario: Mapped[Scenario] = relationship(Scenario, back_populates="datasets")
    dataset: Mapped[Dataset] = relationship(Dataset)

    def to_domain(self):
        return domain_model.ScenarioDataset(
            self.dataset.name, self.dataset.dataset_type.to_domain(), id=self.dataset.id
        )


class ScenarioModel(Base):
    __tablename__ = "scenario_model"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence"),
        UniqueConstraint("scenario_id", "name"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH)
    )
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"))
    model_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_type.id", ondelete="RESTRICT")
    )
    sequence: Mapped[int]
    config: Mapped[dict]
    references: Mapped[list[ScenarioModelReference]] = relationship()

    model_type: Mapped[ModelType] = relationship()

    def to_domain(self):
        return domain_model.ScenarioModel(
            name=self.name,
            type=self.model_type.to_domain(),
            config=self.config,
            references=[ref.to_domain() for ref in self.references],
        ).with_populated_config()


class ScenarioModelReference(Base):
    __tablename__ = "scenario_model_reference"
    __table_args__ = (UniqueConstraint("scenario_model_id", "path"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scenario_model_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenario_model.id", ondelete="CASCADE")
    )
    path: Mapped[str]
    dataset_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("dataset.id", ondelete="RESTRICT")
    )
    entity_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("entity_type.id", ondelete="RESTRICT")
    )
    attribute_type_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("attribute_type.id", ondelete="RESTRICT")
    )
    dataset: Mapped[Dataset] = relationship()
    entity_type: Mapped[EntityType] = relationship()
    attribute_type: Mapped[AttributeType] = relationship()

    def to_domain(self):
        value = None
        if self.dataset is not None:
            value = self.dataset.name
        elif self.entity_type is not None:
            value = self.entity_type.name
        elif self.attribute_type is not None:
            value = self.attribute_type.name

        return MoviciDataRefInfo.from_path_string(self.path, value=value)


class Update(Base):
    __tablename__ = "update"
    __table_args__ = (UniqueConstraint("scenario_id", "timestamp", "iteration"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"))
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset.id", ondelete="RESTRICT"))
    model_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_type.id", ondelete="RESTRICT")
    )

    # For the model name we could link to the associated ScenarioModel. However, any
    # changes to the scenario would recreate all ScenarioModels, which would break this link.
    # Instead, we denormalize model_name and store a copy directly in the Update
    # table
    model_name: Mapped[str] = mapped_column(
        RegexMatchingString(pattern=snake_case_pattern, length=DEFAULT_NAME_MAX_LENGTH)
    )

    timestamp: Mapped[int]
    iteration: Mapped[int]
    bounding_box: Mapped[tuple[float, float, float, float] | None] = mapped_column(
        JSONTuple(length=4), default=None
    )
    created_at: Mapped[datetime.datetime] = mapped_column(default=func.now())

    scenario: Mapped[Scenario] = relationship()
    dataset: Mapped[Dataset] = relationship()
    model_type: Mapped[ModelType] = relationship()

    def to_domain(self) -> domain_model.Update:
        return domain_model.Update(
            id=self.id,
            dataset=domain_model.ScenarioDataset(
                self.dataset.name, self.dataset.dataset_type.to_domain(), id=self.dataset_id
            ),
            model=domain_model.UpdateModel(self.model_name, type=self.model_type.to_domain()),
            timestamp=self.timestamp,
            iteration=self.iteration,
            bounding_box=BoundingBox.from_tuple_or_none(self.bounding_box),
            created_at=self.created_at,
        )


class UpdateAttribute(Base):
    __tablename__ = "update_attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("update.id", ondelete="CASCADE"))
    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))

    update: Mapped[Update] = relationship()
    attribute: Mapped[Attribute] = relationship()
