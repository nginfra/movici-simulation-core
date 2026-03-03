"""SQLite Schema for Intermediate Simulation Data Storage.

This schema provides efficient storage for simulation updates with:

* Numpy array storage with dtype preservation
* CSR sparse array support via indptr
* Time-series update tracking
* Entity-attribute data model
"""

from __future__ import annotations

import contextlib
import enum
import json
import typing as t
from pathlib import Path
from threading import Lock

import numpy as np
import orjson
from sqlalchemy import (
    Column,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    LargeBinary,
    String,
    UniqueConstraint,
    create_engine,
    text,
)
from sqlalchemy.orm import declarative_base, relationship, sessionmaker

Base = declarative_base()


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


_CURRENT_SCHEMA_VERSION = "v1"


class Metadata(Base):
    __tablename__ = "metadata"

    id = Column(Integer, primary_key=True, autoincrement=True)
    version = Column(String(16), nullable=False)


class NumpyArray(Base):
    """Store numpy arrays efficiently as binary data with metadata.

    Supports both regular and sparse (CSR) array storage.
    """

    __tablename__ = "numpy_array"

    id = Column(Integer, primary_key=True, autoincrement=True)
    dtype = Column(String(20), nullable=False)
    shape = Column(String, nullable=False)  # JSON string: "[100, 5]"
    data = Column(LargeBinary, nullable=False)

    @classmethod
    def from_array(cls, arr: np.ndarray) -> NumpyArray:
        """Create NumpyArray record from numpy array.

        :param arr: NumPy array to store
        :return: NumpyArray instance
        """
        return cls(dtype=arr.dtype.str, shape=json.dumps(list(arr.shape)), data=arr.tobytes())

    def to_array(self) -> np.ndarray:
        """Reconstruct numpy array from stored data.

        :return: Reconstructed NumPy array
        """
        shape = tuple(json.loads(self.shape))
        return np.frombuffer(self.data, dtype=self.dtype).reshape(shape)


class Update(Base):
    """Represents a simulation update at a specific timestamp and iteration."""

    __tablename__ = "update"
    __table_args__ = (
        UniqueConstraint("timestamp", "iteration", "dataset_name", name="uq_update"),
        Index("idx_update_time", "timestamp", "iteration"),
        Index("idx_update_dataset", "dataset_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    timestamp = Column(Integer, nullable=False)
    iteration = Column(Integer, nullable=False)
    dataset_name = Column(String, nullable=False)
    origin = Column(String)  # Optional: model that produced this update

    # Relationships
    attributes = relationship(
        "AttributeData", secondary="update_attribute", back_populates="updates"
    )


class AttributeData(Base):
    """Stores entity attribute data with support for both uniform and CSR sparse arrays."""

    __tablename__ = "attribute_data"
    __table_args__ = (
        Index("idx_attr_entity_group", "entity_group"),
        Index("idx_attr_name", "attribute_name"),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    entity_group = Column(String, nullable=False)
    attribute_name = Column(String, nullable=False)

    # Foreign keys to numpy arrays
    data_id = Column(Integer, ForeignKey("numpy_array.id", ondelete="CASCADE"), nullable=False)
    indptr_id = Column(Integer, ForeignKey("numpy_array.id", ondelete="CASCADE"))

    # Optional metadata for optimization
    min_val = Column(Float)
    max_val = Column(Float)

    # Relationships
    data = relationship("NumpyArray", foreign_keys=[data_id])
    indptr = relationship("NumpyArray", foreign_keys=[indptr_id])
    updates = relationship("Update", secondary="update_attribute", back_populates="attributes")
    initial_datasets = relationship(
        "InitialDataset", secondary="initial_dataset_attribute", back_populates="attributes"
    )

    @property
    def is_sparse(self) -> bool:
        """Check if this attribute uses CSR sparse representation.

        :return: True if sparse, False otherwise
        """
        return self.indptr_id is not None

    def get_data(self) -> dict:
        """Get attribute data in movici format.

        :return: Dictionary with 'data' key and optionally 'row_ptr' for sparse arrays
        """
        result = {"data": self.data.to_array()}
        if self.is_sparse:
            result["row_ptr"] = self.indptr.to_array()
        return result


class UpdateAttribute(Base):
    """Junction table linking updates to their attribute data."""

    __tablename__ = "update_attribute"
    __table_args__ = (UniqueConstraint("update_id", "attribute_data_id", name="uq_update_attr"),)

    update_id = Column(Integer, ForeignKey("update.id", ondelete="CASCADE"), primary_key=True)
    attribute_data_id = Column(
        Integer, ForeignKey("attribute_data.id", ondelete="CASCADE"), primary_key=True
    )

    update = relationship("Update", overlaps="attributes,updates")
    attribute_data = relationship("AttributeData", overlaps="attributes,updates")


class InitialDatasetAttribute(Base):
    """Junction table linking initial datasets (entity_based format) to their attribute data."""

    __tablename__ = "initial_dataset_attribute"
    __table_args__ = (
        UniqueConstraint(
            "initial_dataset_id", "attribute_data_id", name="uq_initial_dataset_attr"
        ),
    )

    initial_dataset_id = Column(
        Integer, ForeignKey("initial_dataset.id", ondelete="CASCADE"), primary_key=True
    )
    attribute_data_id = Column(
        Integer, ForeignKey("attribute_data.id", ondelete="CASCADE"), primary_key=True
    )

    initial_dataset = relationship("InitialDataset", overlaps="attributes,initial_datasets")
    attribute_data = relationship("AttributeData", overlaps="attributes,initial_datasets")


class InitialDataset(Base):
    """Stores initial dataset snapshots for self-contained database archives.

    This allows the database to be a complete simulation record without
    requiring separate init_data directory.

    Supports three storage formats:

    * ``ENTITY_BASED``: Destructured into entity groups and attributes (references AttributeData)
    * ``UNSTRUCTURED``: JSON blob, loadable but not queryable by attribute
    * ``BINARY``: Raw binary blob, passed transparently to consumers
    """

    __tablename__ = "initial_dataset"
    __table_args__ = (Index("idx_initial_dataset_name", "dataset_name"),)

    id = Column(Integer, primary_key=True, autoincrement=True)
    dataset_name = Column(String, unique=True, nullable=False)
    format = Column(Enum(DatasetFormat), nullable=False)
    data = Column(LargeBinary)

    attributes = relationship(
        "AttributeData", secondary="initial_dataset_attribute", back_populates="initial_datasets"
    )


class SimulationDatabase:
    """High-level interface for storing and retrieving simulation data.

    Thread-safe for concurrent writes from multiple workers.
    """

    def __init__(self, db_path: t.Union[str, Path]):
        """Initialize database connection.

        :param db_path: Path to SQLite database file (use ":memory:" for in-memory)
        """
        self.db_path = db_path
        self.engine = create_engine(
            f"sqlite:///{self.db_path!s}",
            echo=False,
            connect_args={
                "timeout": 30.0,  # Wait up to 30s for locks
            },
        )

        self._Session = sessionmaker(bind=self.engine)
        self._write_lock = Lock()

    @contextlib.contextmanager
    def get_session(self):
        session = self._Session()
        try:
            yield session
        except:
            session.rollback()
            raise
        finally:
            session.close()

    def __enter__(self):
        return self

    def __exit__(self, *_, **__):
        self.close()

    def initialize(self):
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

        Base.metadata.create_all(self.engine)
        self.ensure_metadata()

    def ensure_metadata(self):
        with self.get_session() as session:
            metadata = session.query(Metadata).first()
            if not metadata:
                session.add(Metadata(version=_CURRENT_SCHEMA_VERSION))
                session.commit()

    def get_metadata(self):
        with self.get_session() as session:
            return session.query(Metadata).one()

    def store_update(
        self,
        timestamp: int,
        iteration: int,
        dataset_name: str,
        entity_data: dict,
        origin: t.Optional[str] = None,
    ) -> int:
        """Store a simulation update.

        :param timestamp: Simulation timestamp
        :param iteration: Iteration number at this timestamp
        :param dataset_name: Name of the dataset
        :param entity_data: Update data in movici format::

                {"entity_group_name": {"attribute_name": {"data": [...], "row_ptr": [...]}}}

        :param origin: Optional model identifier
        :return: Update ID
        """
        with self._write_lock:
            with self.get_session() as session:
                update = Update(
                    timestamp=timestamp,
                    iteration=iteration,
                    dataset_name=dataset_name,
                    origin=origin,
                )
                session.add(update)

                for entity_group, attributes in entity_data.items():
                    for attr_name, attr_data in attributes.items():
                        data_array = np.asarray(attr_data["data"])
                        numpy_data = NumpyArray.from_array(data_array)
                        session.add(numpy_data)

                        numpy_indptr = None
                        if "row_ptr" in attr_data or "indptr" in attr_data:
                            indptr_key = "row_ptr" if "row_ptr" in attr_data else "indptr"
                            indptr_array = np.asarray(attr_data[indptr_key])
                            numpy_indptr = NumpyArray.from_array(indptr_array)
                            session.add(numpy_indptr)

                        attr_data_record = AttributeData(
                            entity_group=entity_group,
                            attribute_name=attr_name,
                            data=numpy_data,
                            indptr=numpy_indptr,
                        )
                        session.add(attr_data_record)

                        update_attr = UpdateAttribute(
                            update=update, attribute_data=attr_data_record
                        )
                        session.add(update_attr)

                session.commit()
                return update.id

    def get_dataset_updates(self, dataset_name: str) -> t.List[dict]:
        """Retrieve all updates for a dataset in chronological order.

        :param dataset_name: Name of the dataset
        :return: List of updates in movici format
        """
        with self.get_session() as session:
            updates = (
                session.query(Update)
                .filter(Update.dataset_name == dataset_name)
                .order_by(Update.timestamp, Update.iteration)
                .all()
            )

            result = []
            for update in updates:
                update_dict = {
                    "timestamp": update.timestamp,
                    "iteration": update.iteration,
                }

                data = {}
                for attr in update.attributes:
                    if attr.entity_group not in data:
                        data[attr.entity_group] = {}
                    data[attr.entity_group][attr.attribute_name] = attr.get_data()

                update_dict.update(data)
                result.append(update_dict)

            return result

    def get_datasets(self) -> t.List[str]:
        """Get list of all dataset names in database.

        :return: List of dataset names
        """
        with self.get_session() as session:
            result = session.query(Update.dataset_name).distinct().all()
            return [row[0] for row in result]

    def get_timestamps(self, dataset_name: str) -> t.List[int]:
        """Get all timestamps for a dataset.

        :param dataset_name: Name of the dataset
        :return: List of timestamps in ascending order
        """
        with self.get_session() as session:
            result = (
                session.query(Update.timestamp)
                .filter(Update.dataset_name == dataset_name)
                .distinct()
                .order_by(Update.timestamp)
                .all()
            )
            return [row[0] for row in result]

    def get_update_count(self, dataset_name: t.Optional[str] = None) -> int:
        """Get total number of updates (optionally filtered by dataset).

        :param dataset_name: Optional dataset name to filter by
        :return: Number of updates
        """
        with self.get_session() as session:
            query = session.query(Update)
            if dataset_name:
                query = query.filter(Update.dataset_name == dataset_name)
            return query.count()

    def store_initial_dataset(
        self,
        dataset_name: str,
        dataset_data: t.Union[dict, bytes],
        format: DatasetFormat = DatasetFormat.UNSTRUCTURED,
    ) -> int:
        """Store initial dataset snapshot in database.

        This allows the database to be self-contained without requiring
        separate init_data directory.

        :param dataset_name: Name of the dataset
        :param dataset_data: Dataset data - ``dict`` for JSON formats, ``bytes`` for binary
        :param format: Storage format (``entity_based``, ``unstructured``, or ``binary``)
        :return: Initial dataset ID
        """
        with self._write_lock:
            with self.get_session() as session:
                initial_dataset = InitialDataset(dataset_name=dataset_name, format=format)
                session.add(initial_dataset)

                if format == DatasetFormat.ENTITY_BASED:
                    for entity_group, attributes in dataset_data.items():
                        if not isinstance(attributes, dict):
                            continue
                        for attr_name, attr_data in attributes.items():
                            data_array = np.asarray(attr_data["data"])
                            numpy_data = NumpyArray.from_array(data_array)
                            session.add(numpy_data)

                            numpy_indptr = None
                            if "row_ptr" in attr_data or "indptr" in attr_data:
                                indptr_key = "row_ptr" if "row_ptr" in attr_data else "indptr"
                                indptr_array = np.asarray(attr_data[indptr_key])
                                numpy_indptr = NumpyArray.from_array(indptr_array)
                                session.add(numpy_indptr)

                            attr_data_record = AttributeData(
                                entity_group=entity_group,
                                attribute_name=attr_name,
                                data=numpy_data,
                                indptr=numpy_indptr,
                            )
                            session.add(attr_data_record)

                            initial_dataset_attr = InitialDatasetAttribute(
                                initial_dataset=initial_dataset, attribute_data=attr_data_record
                            )
                            session.add(initial_dataset_attr)

                elif format == DatasetFormat.UNSTRUCTURED:
                    initial_dataset.data = orjson.dumps(dataset_data)

                elif format == DatasetFormat.BINARY:
                    if not isinstance(dataset_data, bytes):
                        raise TypeError("Binary format requires bytes data")
                    initial_dataset.data = dataset_data

                session.commit()
                return initial_dataset.id

    def get_initial_dataset(self, dataset_name: str) -> t.Optional[t.Union[dict, bytes]]:
        """Retrieve initial dataset from database.

        :param dataset_name: Name of the dataset
        :return: Dataset data (``dict`` for JSON formats, ``bytes`` for binary), or ``None`` if
            not found
        """
        with self.get_session() as session:
            initial_dataset = (
                session.query(InitialDataset)
                .filter(InitialDataset.dataset_name == dataset_name)
                .first()
            )
            if not initial_dataset:
                return None

            if initial_dataset.format == DatasetFormat.ENTITY_BASED:
                data = {}
                for attr in initial_dataset.attributes:
                    if attr.entity_group not in data:
                        data[attr.entity_group] = {}
                    data[attr.entity_group][attr.attribute_name] = attr.get_data()
                return data

            elif initial_dataset.format == DatasetFormat.UNSTRUCTURED:
                return orjson.loads(initial_dataset.data)

            elif initial_dataset.format == DatasetFormat.BINARY:
                return initial_dataset.data

            return None

    def get_all_initial_datasets(self) -> t.Dict[str, t.Union[dict, bytes]]:
        """Retrieve all initial datasets from database.

        :return: Dictionary mapping dataset names to their data
        """
        with self.get_session() as session:
            initial_datasets = session.query(InitialDataset).all()
            result = {}
            for dataset in initial_datasets:
                result[dataset.dataset_name] = self.get_initial_dataset(dataset.dataset_name)
            return result

    def has_initial_datasets(self) -> bool:
        """Check if database contains any initial datasets.

        :return: True if initial datasets are stored, False otherwise
        """
        with self.get_session() as session:
            return session.query(InitialDataset).count() > 0

    def close(self):
        """Close database connections."""
        self.engine.dispose()
