from __future__ import annotations

import datetime
import enum
import typing as t
import uuid

import numpy as np
from movici_data_core import domain_model
from movici_data_core.domain_model import DatasetFormat
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
    type_annotation_map = {uuid.UUID: GUID, datetime.datetime: TZDateTime, tuple: JSONTuple}


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
    STRICT_MODELS: Mapped[bool] = mapped_column(default=False)
    STRICT_MODEL_CONFIGS: Mapped[bool] = mapped_column(default=False)

    default_workspace_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("workspace.id", ondelete="RESTRICT")
    )
    default_workspace: Mapped[Workspace | None] = relationship()


class Workspace(Base):
    __tablename__ = "workspace"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(unique=True)
    display_name: Mapped[str]
    datasets: Mapped[list[Dataset]] = relationship(back_populates="workspace")
    scenarios: Mapped[list[Scenario]] = relationship(back_populates="workspace")

    def to_domain(self):
        return domain_model.Workspace(id=self.id, name=self.name, display_name=self.display_name)


class DatasetType(Base):
    __tablename__ = "dataset_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str]
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

    name: Mapped[str]
    display_name: Mapped[str]

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
            espg_code=self.epsg_code,
            bounding_box=self.bounding_box,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class EntityType(Base):
    MAX_NAME_LENGTH = 50
    __tablename__ = "entity_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH))

    def to_domain(self):
        return domain_model.EntityType(name=self.name, id=self.id)


class AttributeType(Base):
    MAX_NAME_LENGTH = 100
    MAX_UNIT_LENGTH = 20
    __tablename__ = "attribute_type"
    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    name: Mapped[str] = mapped_column(String(MAX_NAME_LENGTH), unique=True)
    has_rowptr: Mapped[bool]
    unit_type: Mapped[AttributeDataType]
    unit_shape: Mapped[tuple[int, ...]] = mapped_column(JSONTuple)
    unit: Mapped[str] = mapped_column(String(MAX_UNIT_LENGTH))
    description: Mapped[str]

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
        )


class NumpyArray(Base):
    __tablename__ = "numpy_array"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    dtype: Mapped[str] = mapped_column(String(20))
    shape: Mapped[tuple] = mapped_column(JSON)
    data: Mapped[bytes]

    @classmethod
    def from_array(cls, arr: np.ndarray) -> NumpyArray:
        """Create NumpyArray record from numpy array.

        :param arr: NumPy array to store
        :return: NumpyArray instance
        """
        return cls(dtype=arr.dtype.str, shape=arr.shape, data=arr.tobytes())

    def to_array(self) -> np.ndarray:
        """Reconstruct numpy array from stored data.

        :return: Reconstructed NumPy array
        """
        return np.frombuffer(self.data, dtype=self.dtype).reshape(self.shape)


class Attribute(Base):
    __tablename__ = "attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    entity_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("entity_type.id", ondelete="RESTRICT")
    )
    attribute_type_id: Mapped[uuid.UUID] = mapped_column(
        ForeignKey("attribute_type.id", ondelete="RESTRICT")
    )
    data_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("numpy_array.id", ondelete="RESTRICT"))
    rowptr_id: Mapped[uuid.UUID | None] = mapped_column(
        ForeignKey("numpy_array.id", ondelete="RESTRICT")
    )

    min_val: Mapped[float | None]
    max_val: Mapped[float | None]

    entity_type: Mapped[EntityType] = relationship()
    attribute_type: Mapped[AttributeType] = relationship()
    data: Mapped[NumpyArray] = relationship(foreign_keys=[data_id])
    rowptr: Mapped[NumpyArray | None] = relationship(foreign_keys=[rowptr_id])


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


class Scenario(Base):
    __tablename__ = "scenario"
    __table_args__ = (UniqueConstraint("workspace_id", "name"),)

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    workspace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("workspace.id", ondelete="CASCADE"))
    workspace: Mapped[Workspace] = relationship(back_populates="scenarios")

    name: Mapped[str]
    display_name: Mapped[str]
    description: Mapped[str] = mapped_column(Text)
    simulation_info: Mapped[dict] = mapped_column(JSON)

    epsg_code: Mapped[int]
    bounding_box: Mapped[tuple[float, float, float, float]] = mapped_column(JSONTuple(length=4))

    created_at: Mapped[datetime.datetime] = mapped_column(default=func.now())
    updated_at: Mapped[datetime.datetime] = mapped_column(default=func.now(), onupdate=func.now())

    datasets: Mapped[Dataset] = relationship()

    def to_domain(self) -> domain_model.Scenario:
        return domain_model.Scenario(
            id=self.id,
            workspace=self.workspace.to_domain(),
            name=self.name,
            display_name=self.display_name,
            description=self.description,
            simulation_info=self.simulation_info,
            epsg_code=self.epsg_code,
            bounding_box=self.bounding_box,
            created_at=self.created_at,
            updated_at=self.updated_at,
        )


class ScenarioDataset(Base):
    __tablename__ = "scenario_dataset"
    scenario_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("scenario.id"), primary_key=True)
    dataset_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("dataset.id"), primary_key=True)
    scenario: Mapped[Scenario] = relationship(Scenario, back_populates="datasets")
    dataset: Mapped[Scenario] = relationship(Dataset, back_populates="scenarios")


class Update(Base):
    __tablename__ = "update"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)


class UpdateAttribute(Base):
    __tablename__ = "update_attribute"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    update_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("update.id", ondelete="CASCADE"))
    attribute_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("attribute.id", ondelete="CASCADE"))

    update: Mapped[Update] = relationship()
    attribute: Mapped[Attribute] = relationship()


#
#
# class NumpyArray(Base):
#     """Store numpy arrays efficiently as binary data with metadata.
#
#     Supports both regular and sparse (CSR) array storage.
#     """
#
#     __tablename__ = "numpy_array"
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     dtype = Column(String(20), nullable=False)
#     shape = Column(String, nullable=False)  # JSON string: "[100, 5]"
#     data = Column(LargeBinary, nullable=False)
#
#     @classmethod
#     def from_array(cls, arr: np.ndarray) -> NumpyArray:
#         """Create NumpyArray record from numpy array.
#
#         :param arr: NumPy array to store
#         :return: NumpyArray instance
#         """
#         return cls(dtype=arr.dtype.str, shape=json.dumps(list(arr.shape)), data=arr.tobytes())
#
#     def to_array(self) -> np.ndarray:
#         """Reconstruct numpy array from stored data.
#
#         :return: Reconstructed NumPy array
#         """
#         shape = tuple(json.loads(self.shape))
#         return np.frombuffer(self.data, dtype=self.dtype).reshape(shape)
#
#
# class Update(Base):
#     """Represents a simulation update at a specific timestamp and iteration."""
#
#     __tablename__ = "update"
#     __table_args__ = (
#         UniqueConstraint("timestamp", "iteration", "dataset_name", name="uq_update"),
#         Index("idx_update_time", "timestamp", "iteration"),
#         Index("idx_update_dataset", "dataset_name"),
#     )
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     timestamp = Column(Integer, nullable=False)
#     iteration = Column(Integer, nullable=False)
#     dataset_name = Column(String, nullable=False)
#     origin = Column(String)  # Optional: model that produced this update
#
#     # Relationships
#     attributes = relationship(
#         "AttributeData", secondary="update_attribute", back_populates="updates"
#     )
#
#
# class AttributeData(Base):
#     """Stores entity attribute data with support for both uniform and CSR sparse arrays."""
#
#     __tablename__ = "attribute_data"
#     __table_args__ = (
#         Index("idx_attr_entity_group", "entity_group"),
#         Index("idx_attr_name", "attribute_name"),
#     )
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     entity_group = Column(String, nullable=False)
#     attribute_name = Column(String, nullable=False)
#
#     # Foreign keys to numpy arrays
#     data_id = Column(Integer, ForeignKey("numpy_array.id", ondelete="CASCADE"), nullable=False)
#     indptr_id = Column(Integer, ForeignKey("numpy_array.id", ondelete="CASCADE"))
#
#     # Optional metadata for optimization
#     min_val = Column(Float)
#     max_val = Column(Float)
#
#     # Relationships
#     data = relationship("NumpyArray", foreign_keys=[data_id])
#     indptr = relationship("NumpyArray", foreign_keys=[indptr_id])
#     updates = relationship("Update", secondary="update_attribute", back_populates="attributes")
#     initial_datasets = relationship(
#         "InitialDataset", secondary="initial_dataset_attribute", back_populates="attributes"
#     )
#
#     @property
#     def is_sparse(self) -> bool:
#         """Check if this attribute uses CSR sparse representation.
#
#         :return: True if sparse, False otherwise
#         """
#         return self.indptr_id is not None
#
#     def get_data(self) -> dict:
#         """Get attribute data in movici format.
#
#         :return: Dictionary with 'data' key and optionally 'row_ptr' for sparse arrays
#         """
#         result = {"data": self.data.to_array()}
#         if self.is_sparse:
#             result["row_ptr"] = self.indptr.to_array()
#         return result
#
#
# class UpdateAttribute(Base):
#     """Junction table linking updates to their attribute data."""
#
#     __tablename__ = "update_attribute"
#     __table_args__ = (UniqueConstraint("update_id", "attribute_data_id", name="uq_update_attr"),)
#
#     update_id = Column(Integer, ForeignKey("update.id", ondelete="CASCADE"), primary_key=True)
#     attribute_data_id = Column(
#         Integer, ForeignKey("attribute_data.id", ondelete="CASCADE"), primary_key=True
#     )
#
#     update = relationship("Update", overlaps="attributes,updates")
#     attribute_data = relationship("AttributeData", overlaps="attributes,updates")
#
#
# class InitialDatasetAttribute(Base):
#     """Junction table linking initial datasets (entity_based format) to their attribute data."""
#
#     __tablename__ = "initial_dataset_attribute"
#     __table_args__ = (
#         UniqueConstraint(
#             "initial_dataset_id", "attribute_data_id", name="uq_initial_dataset_attr"
#         ),
#     )
#
#     initial_dataset_id = Column(
#         Integer, ForeignKey("initial_dataset.id", ondelete="CASCADE"), primary_key=True
#     )
#     attribute_data_id = Column(
#         Integer, ForeignKey("attribute_data.id", ondelete="CASCADE"), primary_key=True
#     )
#
#     initial_dataset = relationship("InitialDataset", overlaps="attributes,initial_datasets")
#     attribute_data = relationship("AttributeData", overlaps="attributes,initial_datasets")
#
#
# class InitialDataset(Base):
#     """Stores initial dataset snapshots for self-contained database archives.
#
#     This allows the database to be a complete simulation record without
#     requiring separate init_data directory.
#
#     Supports three storage formats:
#
#     * ``ENTITY_BASED``: Destructured into entity groups and attributes (references AttributeData)
#     * ``UNSTRUCTURED``: JSON blob, loadable but not queryable by attribute
#     * ``BINARY``: Raw binary blob, passed transparently to consumers
#     """
#
#     __tablename__ = "initial_dataset"
#     __table_args__ = (Index("idx_initial_dataset_name", "dataset_name"),)
#
#     id = Column(Integer, primary_key=True, autoincrement=True)
#     dataset_name = Column(String, unique=True, nullable=False)
#     format = Column(Enum(DatasetFormat), nullable=False)
#     data = Column(LargeBinary)
#
#     attributes = relationship(
#         "AttributeData", secondary="initial_dataset_attribute", back_populates="initial_datasets"
#     )
#
#
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
