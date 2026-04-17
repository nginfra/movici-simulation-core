from __future__ import annotations

import datetime
import enum
import typing as t
import uuid

import numpy as np
from movici_data_core import domain_model
from movici_data_core.domain_model import DatasetFormat, ScenarioStatus
from sqlalchemy import (
    JSON,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship

from movici_simulation_core.core import DataType

from .db_types import GUID, JSONTuple, TZDateTime

T_dom = t.TypeVar("T_dom", covariant=True)


class NamedResource(t.Protocol[T_dom]):
    id: Mapped[uuid.UUID]
    name: Mapped[str]

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
ATTRIBUTE_UNIT_MAX_LENGTH = 20
ATTRIBUTE_ENUM_NAME_MAX_LENGTH = 20


class Metadata(Base):
    __tablename__ = "metadata"

    id: Mapped[int] = mapped_column(primary_key=True)
    version: Mapped[str] = mapped_column(String(64))


class Options(Base):
    __tablename__ = "options"
    id: Mapped[int] = mapped_column(primary_key=True)
    mode: Mapped[DatabaseMode]

    STRICT_DATASET_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_ENTITY_TYPES: Mapped[bool] = mapped_column(default=False)
    STRICT_ATTRIBUTES: Mapped[bool] = mapped_column(default=False)
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
    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH), unique=True)
    display_name: Mapped[str] = mapped_column(String(DEFAULT_DISPLAY_NAME_MAX_LENGTH))
    datasets: Mapped[list[Dataset]] = relationship(back_populates="workspace")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="workspace")

    def to_domain(self):
        return domain_model.Workspace(id=self.id, name=self.name, display_name=self.display_name)


class DatasetType(Base):
    __tablename__ = "dataset_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH), unique=True)
    format: Mapped[DatasetFormat]
    mimetype: Mapped[str | None]

    def to_domain(self):
        return domain_model.DatasetType(
            id=self.id, name=self.name, format=self.format, mimetype=self.mimetype
        )


class Dataset(Base):
    __tablename__ = "dataset"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    workspace: Mapped[Workspace] = relationship(back_populates="datasets")

    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH))
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

    def to_domain(self) -> domain_model.Dataset:
        return domain_model.Dataset(
            id=self.id,
            name=self.name,
            display_name=self.display_name,
            dataset_type=self.dataset_type.to_domain(),
            workspace=self.workspace.to_domain(),
            general=self.general,
            epsg_code=self.epsg_code,
            bounding_box=self.bounding_box,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class EntityType(Base):
    __tablename__ = "entity_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH), unique=True)

    def to_domain(self):
        return domain_model.EntityType(name=self.name, id=self.id)


class AttributeType(Base):
    __tablename__ = "attribute_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(ATTRIBUTE_NAME_MAX_LENGTH), unique=True)
    has_rowptr: Mapped[bool]
    unit_type: Mapped[AttributeDataType]
    unit_shape: Mapped[tuple[int, ...]] = mapped_column(JSONTuple)
    unit: Mapped[str] = mapped_column(String(ATTRIBUTE_UNIT_MAX_LENGTH))
    description: Mapped[str]
    enum_name: Mapped[str | None] = mapped_column(String(ATTRIBUTE_ENUM_NAME_MAX_LENGTH))

    @property
    def data_type(self):
        py_type = {
            AttributeDataType.BOOL: bool,
            AttributeDataType.INT: int,
            AttributeDataType.FLOAT: float,
            AttributeDataType.STR: str,
        }[self.unit_type]
        return DataType(py_type, unit_shape=self.unit_shape, csr=self.has_rowptr)

    def to_domain(self):
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
    compresion: Mapped[str | None]


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
    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH), unique=True)
    jsonschema: Mapped[dict] = mapped_column(JSON)

    def to_domain(self):
        return domain_model.ModelType(id=self.id, name=self.name, jsonschema=self.jsonschema)


class Scenario(Base):
    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    workspace: Mapped[Workspace] = relationship(back_populates="scenarios")

    name: Mapped[str]
    display_name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    status: Mapped[ScenarioStatus]

    simulation_info: Mapped[dict] = mapped_column(JSON)

    epsg_code: Mapped[int]

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
            simulation_info=self.simulation_info,
            epsg_code=self.epsg_code,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ScenarioDataset(Base):
    __tablename__ = "scenario_dataset"
    __table_args__ = (UniqueConstraint("scenario_id", "sequence"),)
    scenario_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("scenario.id", ondelete="CASCADE"), primary_key=True
    )
    dataset_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("dataset.id", ondelete="RESTRICT"), primary_key=True
    )
    sequence: Mapped[int] = mapped_column()
    scenario: Mapped[Scenario] = relationship(Scenario, back_populates="datasets")
    dataset: Mapped[Dataset] = relationship(Dataset)


class ScenarioModel(Base):
    __tablename__ = "scenario_model"
    __table_args__ = (
        UniqueConstraint("scenario_id", "sequence"),
        UniqueConstraint("scenario_id", "name"),
    )
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH))
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario.id", ondelete="CASCADE"))
    model_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("model_type.id", ondelete="RESTRICT")
    )
    sequence: Mapped[int]
    config: Mapped[dict]
    references: Mapped[list[ScenarioModelReference]] = relationship()

    model_type: Mapped[ModelType] = relationship()


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
    model_name: Mapped[str] = mapped_column(String(DEFAULT_NAME_MAX_LENGTH))

    timestamp: Mapped[int]
    iteration: Mapped[int]
    created_at: Mapped[datetime.datetime] = mapped_column(default=func.now())

    scenario: Mapped[Scenario] = relationship()
    dataset: Mapped[Dataset] = relationship()
    model_type: Mapped[ModelType] = relationship()

    def to_domain(self):
        return domain_model.Update(
            id=self.id,
            dataset=domain_model.ScenarioDataset(
                self.dataset.name, self.dataset.dataset_type.name, id=self.dataset_id
            ),
            model_name=self.model_name,
            model_type=self.model_type.name,
            timestamp=self.timestamp,
            iteration=self.iteration,
        )


class UpdateAttribute(Base):
    __tablename__ = "update_attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("update.id", ondelete="CASCADE"))
    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))

    update: Mapped[Update] = relationship()
    attribute: Mapped[Attribute] = relationship()


# class SimulationDatabase:
#     """High-level interface for storing and retrieving simulation data.
#
#     Thread-safe for concurrent writes from multiple workers.
#     """
#
#     def __init__(self, db_path: t.Union[str, Path]):
#         """Initialize database connection.
#
#         :param db_path: Path to SQLite database file (use ":memory:" for in-memory)
#         """
#         self.db_path = db_path
#         self.engine = create_engine(
#             f"sqlite:///{self.db_path!s}",
#             echo=False,
#             connect_args={
#                 "timeout": 30.0,  # Wait up to 30s for locks
#             },
#         )
#
#         self._Session = sessionmaker(bind=self.engine)
#         self._write_lock = Lock()
#
#     @contextlib.contextmanager
#     def get_session(self):
#         session = self._Session()
#         try:
#             yield session
#         except:
#             session.rollback()
#             raise
#         finally:
#             session.close()
#
#     def __enter__(self):
#         return self
#
#     def __exit__(self, *_, **__):
#         self.close()
#
#     def initialize(self):
#         with self.engine.connect() as conn:
#             conn.execute(text("PRAGMA foreign_keys=ON"))
#             conn.commit()
#
#         Base.metadata.create_all(self.engine)
#         self.ensure_metadata()
#
#     def ensure_metadata(self):
#         with self.get_session() as session:
#             metadata = session.query(Metadata).first()
#             if not metadata:
#                 session.add(Metadata(version=_CURRENT_SCHEMA_VERSION))
#                 session.commit()
#
#     def get_metadata(self):
#         with self.get_session() as session:
#             return session.query(Metadata).one()
#
#     def store_update(
#         self,
#         timestamp: int,
#         iteration: int,
#         dataset_name: str,
#         entity_data: dict,
#         origin: t.Optional[str] = None,
#     ) -> int:
#         """Store a simulation update.
#
#         :param timestamp: Simulation timestamp
#         :param iteration: Iteration number at this timestamp
#         :param dataset_name: Name of the dataset
#         :param entity_data: Update data in movici format::
#
#                 {"entity_group_name": {"attribute_name": {"data": [...], "row_ptr": [...]}}}
#
#         :param origin: Optional model identifier
#         :return: Update ID
#         """
#         with self._write_lock:
#             with self.get_session() as session:
#                 update = Update(
#                     timestamp=timestamp,
#                     iteration=iteration,
#                     dataset_name=dataset_name,
#                     origin=origin,
#                 )
#                 session.add(update)
#
#                 for entity_group, attributes in entity_data.items():
#                     for attr_name, attr_data in attributes.items():
#                         data_array = np.asarray(attr_data["data"])
#                         numpy_data = NumpyArray.from_array(data_array)
#                         session.add(numpy_data)
#
#                         numpy_indptr = None
#                         if "row_ptr" in attr_data or "indptr" in attr_data:
#                             indptr_key = "row_ptr" if "row_ptr" in attr_data else "indptr"
#                             indptr_array = np.asarray(attr_data[indptr_key])
#                             numpy_indptr = NumpyArray.from_array(indptr_array)
#                             session.add(numpy_indptr)
#
#                         attr_data_record = AttributeData(
#                             entity_group=entity_group,
#                             attribute_name=attr_name,
#                             data=numpy_data,
#                             indptr=numpy_indptr,
#                         )
#                         session.add(attr_data_record)
#
#                         update_attr = UpdateAttribute(
#                             update=update, attribute_data=attr_data_record
#                         )
#                         session.add(update_attr)
#
#                 session.commit()
#                 return update.id
#
#     def get_dataset_updates(self, dataset_name: str) -> t.List[dict]:
#         """Retrieve all updates for a dataset in chronological order.
#
#         :param dataset_name: Name of the dataset
#         :return: List of updates in movici format
#         """
#         with self.get_session() as session:
#             updates = (
#                 session.query(Update)
#                 .filter(Update.dataset_name == dataset_name)
#                 .order_by(Update.timestamp, Update.iteration)
#                 .all()
#             )
#
#             result = []
#             for update in updates:
#                 update_dict = {
#                     "timestamp": update.timestamp,
#                     "iteration": update.iteration,
#                 }
#
#                 data = {}
#                 for attr in update.attributes:
#                     if attr.entity_group not in data:
#                         data[attr.entity_group] = {}
#                     data[attr.entity_group][attr.attribute_name] = attr.get_data()
#
#                 update_dict.update(data)
#                 result.append(update_dict)
#
#             return result
#
#     def get_datasets(self) -> t.List[str]:
#         """Get list of all dataset names in database.
#
#         :return: List of dataset names
#         """
#         with self.get_session() as session:
#             result = session.query(Update.dataset_name).distinct().all()
#             return [row[0] for row in result]
#
#     def get_timestamps(self, dataset_name: str) -> t.List[int]:
#         """Get all timestamps for a dataset.
#
#         :param dataset_name: Name of the dataset
#         :return: List of timestamps in ascending order
#         """
#         with self.get_session() as session:
#             result = (
#                 session.query(Update.timestamp)
#                 .filter(Update.dataset_name == dataset_name)
#                 .distinct()
#                 .order_by(Update.timestamp)
#                 .all()
#             )
#             return [row[0] for row in result]
#
#     def get_update_count(self, dataset_name: t.Optional[str] = None) -> int:
#         """Get total number of updates (optionally filtered by dataset).
#
#         :param dataset_name: Optional dataset name to filter by
#         :return: Number of updates
#         """
#         with self.get_session() as session:
#             query = session.query(Update)
#             if dataset_name:
#                 query = query.filter(Update.dataset_name == dataset_name)
#             return query.count()
#
#     def store_initial_dataset(
#         self,
#         dataset_name: str,
#         dataset_data: t.Union[dict, bytes],
#         format: DatasetFormat = DatasetFormat.UNSTRUCTURED,
#     ) -> int:
#         """Store initial dataset snapshot in database.
#
#         This allows the database to be self-contained without requiring
#         separate init_data directory.
#
#         :param dataset_name: Name of the dataset
#         :param dataset_data: Dataset data - ``dict`` for JSON formats, ``bytes`` for binary
#         :param format: Storage format (``entity_based``, ``unstructured``, or ``binary``)
#         :return: Initial dataset ID
#         """
#         with self._write_lock:
#             with self.get_session() as session:
#                 initial_dataset = InitialDataset(dataset_name=dataset_name, format=format)
#                 session.add(initial_dataset)
#
#                 if format == DatasetFormat.ENTITY_BASED:
#                     for entity_group, attributes in dataset_data.items():
#                         if not isinstance(attributes, dict):
#                             continue
#                         for attr_name, attr_data in attributes.items():
#                             data_array = np.asarray(attr_data["data"])
#                             numpy_data = NumpyArray.from_array(data_array)
#                             session.add(numpy_data)
#
#                             numpy_indptr = None
#                             if "row_ptr" in attr_data or "indptr" in attr_data:
#                                 indptr_key = "row_ptr" if "row_ptr" in attr_data else "indptr"
#                                 indptr_array = np.asarray(attr_data[indptr_key])
#                                 numpy_indptr = NumpyArray.from_array(indptr_array)
#                                 session.add(numpy_indptr)
#
#                             attr_data_record = AttributeData(
#                                 entity_group=entity_group,
#                                 attribute_name=attr_name,
#                                 data=numpy_data,
#                                 indptr=numpy_indptr,
#                             )
#                             session.add(attr_data_record)
#
#                             initial_dataset_attr = InitialDatasetAttribute(
#                                 initial_dataset=initial_dataset, attribute_data=attr_data_record
#                             )
#                             session.add(initial_dataset_attr)
#
#                 elif format == DatasetFormat.UNSTRUCTURED:
#                     initial_dataset.data = orjson.dumps(dataset_data)
#
#                 elif format == DatasetFormat.BINARY:
#                     if not isinstance(dataset_data, bytes):
#                         raise TypeError("Binary format requires bytes data")
#                     initial_dataset.data = dataset_data
#
#                 session.commit()
#                 return initial_dataset.id
#
#     def get_initial_dataset(self, dataset_name: str) -> t.Optional[t.Union[dict, bytes]]:
#         """Retrieve initial dataset from database.
#
#         :param dataset_name: Name of the dataset
#         :return: Dataset data (``dict`` for JSON formats, ``bytes`` for binary), or ``None`` if
#             not found
#         """
#         with self.get_session() as session:
#             initial_dataset = (
#                 session.query(InitialDataset)
#                 .filter(InitialDataset.dataset_name == dataset_name)
#                 .first()
#             )
#             if not initial_dataset:
#                 return None
#
#             if initial_dataset.format == DatasetFormat.ENTITY_BASED:
#                 data = {}
#                 for attr in initial_dataset.attributes:
#                     if attr.entity_group not in data:
#                         data[attr.entity_group] = {}
#                     data[attr.entity_group][attr.attribute_name] = attr.get_data()
#                 return data
#
#             elif initial_dataset.format == DatasetFormat.UNSTRUCTURED:
#                 return orjson.loads(initial_dataset.data)
#
#             elif initial_dataset.format == DatasetFormat.BINARY:
#                 return initial_dataset.data
#
#             return None
#
#     def get_all_initial_datasets(self) -> t.Dict[str, t.Union[dict, bytes]]:
#         """Retrieve all initial datasets from database.
#
#         :return: Dictionary mapping dataset names to their data
#         """
#         with self.get_session() as session:
#             initial_datasets = session.query(InitialDataset).all()
#             result = {}
#             for dataset in initial_datasets:
#                 result[dataset.dataset_name] = self.get_initial_dataset(dataset.dataset_name)
#             return result
#
#     def has_initial_datasets(self) -> bool:
#         """Check if database contains any initial datasets.
#
#         :return: True if initial datasets are stored, False otherwise
#         """
#         with self.get_session() as session:
#             return session.query(InitialDataset).count() > 0
#
#     def close(self):
#         """Close database connections."""
#         self.engine.dispose()
