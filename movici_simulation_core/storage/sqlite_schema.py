"""SQLite Schema for Intermediate Simulation Data Storage.

This schema provides efficient storage for simulation updates with:

* Numpy array storage with dtype preservation
* CSR sparse array support via indptr
* Time-series update tracking
* Entity-attribute data model
"""

from __future__ import annotations

import json
import typing as t
from pathlib import Path
from threading import Lock

import numpy as np
from sqlalchemy import (
    Column,
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


class SimulationDatabase:
    """High-level interface for storing and retrieving simulation data.

    Thread-safe for concurrent writes from multiple workers.
    """

    def __init__(self, db_path: t.Union[str, Path]):
        """Initialize database connection.

        :param db_path: Path to SQLite database file (use ":memory:" for in-memory)
        """
        self.db_path = str(db_path)
        self.engine = create_engine(
            f"sqlite:///{self.db_path}",
            echo=False,
            connect_args={
                "check_same_thread": False,  # Allow multi-threading
                "timeout": 30.0,  # Wait up to 30s for locks
            },
        )

        # Enable WAL mode for better concurrency
        with self.engine.connect() as conn:
            conn.execute(text("PRAGMA journal_mode=WAL"))
            conn.execute(text("PRAGMA synchronous=NORMAL"))
            conn.execute(text("PRAGMA foreign_keys=ON"))
            conn.commit()

        # Create tables
        Base.metadata.create_all(self.engine)

        # Session factory
        self.Session = sessionmaker(bind=self.engine)

        # Lock for thread-safe writes
        self._write_lock = Lock()

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

                {
                    "entity_group_name": {
                        "attribute_name": {"data": [...], "row_ptr": [...]}
                    }
                }

        :param origin: Optional model identifier
        :return: Update ID
        """
        with self._write_lock:
            with self.Session() as session:
                # Create update record
                update = Update(
                    timestamp=timestamp,
                    iteration=iteration,
                    dataset_name=dataset_name,
                    origin=origin,
                )
                session.add(update)
                session.flush()  # Get update.id

                # Process each entity group
                for entity_group, attributes in entity_data.items():
                    for attr_name, attr_data in attributes.items():
                        # Store main data array
                        data_array = np.asarray(attr_data["data"])
                        numpy_data = NumpyArray.from_array(data_array)
                        session.add(numpy_data)
                        session.flush()

                        # Store indptr if CSR
                        indptr_id = None
                        if "row_ptr" in attr_data or "indptr" in attr_data:
                            indptr_key = "row_ptr" if "row_ptr" in attr_data else "indptr"
                            indptr_array = np.asarray(attr_data[indptr_key])
                            numpy_indptr = NumpyArray.from_array(indptr_array)
                            session.add(numpy_indptr)
                            session.flush()
                            indptr_id = numpy_indptr.id

                        # Create attribute data record
                        attr_data_record = AttributeData(
                            entity_group=entity_group,
                            attribute_name=attr_name,
                            data_id=numpy_data.id,
                            indptr_id=indptr_id,
                        )
                        session.add(attr_data_record)
                        session.flush()

                        # Link to update
                        update_attr = UpdateAttribute(
                            update_id=update.id, attribute_data_id=attr_data_record.id
                        )
                        session.add(update_attr)

                session.commit()
                return update.id

    def get_dataset_updates(self, dataset_name: str) -> t.List[dict]:
        """Retrieve all updates for a dataset in chronological order.

        :param dataset_name: Name of the dataset
        :return: List of updates in movici format
        """
        with self.Session() as session:
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

                # Reconstruct update data
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
        with self.Session() as session:
            result = session.query(Update.dataset_name).distinct().all()
            return [row[0] for row in result]

    def get_timestamps(self, dataset_name: str) -> t.List[int]:
        """Get all timestamps for a dataset.

        :param dataset_name: Name of the dataset
        :return: List of timestamps in ascending order
        """
        with self.Session() as session:
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
        with self.Session() as session:
            query = session.query(Update)
            if dataset_name:
                query = query.filter(Update.dataset_name == dataset_name)
            return query.count()

    def close(self):
        """Close database connections."""
        self.engine.dispose()
