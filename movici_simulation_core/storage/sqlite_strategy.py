"""SQLite storage strategy for DataCollector model.

This module provides SQLiteStorageStrategy which stores simulation updates
in an SQLite database instead of individual JSON files.
"""

from __future__ import annotations

import itertools
import logging
from datetime import datetime
from pathlib import Path

import orjson

from movici_simulation_core.settings import Settings
from movici_simulation_core.storage.sqlite_schema import SimulationDatabase


class SQLiteStorageStrategy:
    """Storage strategy that persists simulation updates to an SQLite database.

    Features:

    * Thread-safe concurrent writes (uses internal locking)
    * Efficient binary storage of numpy arrays
    * Support for CSR sparse arrays
    * Single database file instead of thousands of JSON files
    * Fast indexed queries by timestamp, iteration, dataset
    """

    def __init__(self, database_path: Path):
        """Initialize SQLite storage strategy.

        :param database_path: Path to SQLite database file
        """
        self.database_path = Path(database_path)
        self.db = None

    @classmethod
    def choose(
        cls, model_config: dict, settings: Settings, logger: logging.Logger
    ) -> SQLiteStorageStrategy:
        """Factory method to create SQLiteStorageStrategy from configuration.

        :param model_config: DataCollector model configuration
        :param settings: Global simulation settings
        :param logger: Logger instance
        :return: SQLiteStorageStrategy instance
        :raises ValueError: If neither database_path nor storage_dir is configured
        """
        # Check for database_path in model config first
        database_path = model_config.get("database_path")

        if database_path is None:
            # Auto-generate timestamped database path to ensure fresh database for each run
            storage_dir = model_config.get("storage_dir") or settings.storage_dir
            if storage_dir is None:
                raise ValueError("No database_path or storage_dir configured for SQLite storage")

            # Add timestamp to prevent accidental overwrites from multiple runs
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            database_path = Path(storage_dir) / f"simulation_results_{timestamp}.db"
        else:
            # User explicitly specified path - use as-is
            database_path = Path(database_path)

        logger.info(f"Using SQLite database at: {database_path}")
        return cls(database_path)

    def initialize(self):
        """Initialize the database.

        Creates the database file and schema. When using auto-generated paths,
        each simulation run gets a timestamped database to prevent overwrites.
        """
        # Ensure parent directory exists
        self.database_path.parent.mkdir(parents=True, exist_ok=True)

        # Initialize database connection
        self.db = SimulationDatabase(self.database_path)

    def store(self, info):
        """Store a simulation update in the database.

        This method is called from worker threads by the DataCollector's
        thread pool. The underlying SimulationDatabase uses locking to
        ensure thread-safe writes.

        :param info: UpdateInfo instance containing:

            * name: Dataset name
            * timestamp: Simulation timestamp
            * iteration: Iteration number
            * data: Update data dictionary
            * origin: Optional model identifier
        """
        self.db.store_update(
            timestamp=info.timestamp,
            iteration=info.iteration,
            dataset_name=info.name,
            entity_data=info.data,
            origin=info.origin,
        )

    def reset_iterations(self, model):
        """Reset the iteration counter.

        Called when a new timestamp starts to reset iteration numbering.

        :param model: DataCollector instance
        """
        model.iteration = itertools.count()

    def store_initial_datasets(self, init_data_dir: Path):
        """Store initial datasets in database for complete snapshot.

        This makes the database self-contained without requiring separate
        init_data directory. Call this after initialize() and before
        simulation starts.

        :param init_data_dir: Path to directory containing initial dataset JSON files
        """
        init_data_dir = Path(init_data_dir)
        if not init_data_dir.exists():
            return

        # Store each JSON file as an initial dataset
        for json_file in init_data_dir.glob("*.json"):
            dataset_name = json_file.stem
            dataset_data = orjson.loads(json_file.read_bytes())
            self.db.store_initial_dataset(dataset_name, dataset_data)

    def finalize(self):
        """Clean up database connections.

        Called when simulation ends. Ensures all connections are properly closed.
        """
        if self.db:
            self.db.close()
