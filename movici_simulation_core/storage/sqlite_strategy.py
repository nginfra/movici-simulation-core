"""SQLite storage strategy for DataCollector model.

This module provides SQLiteStorageStrategy which stores simulation updates
in an SQLite database instead of individual JSON files.
"""

from __future__ import annotations

import itertools
import logging
from pathlib import Path

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
            # Fall back to storage_dir with .db extension
            storage_dir = model_config.get("storage_dir") or settings.storage_dir
            if storage_dir is None:
                raise ValueError(
                    "No database_path or storage_dir configured for SQLite storage"
                )
            database_path = Path(storage_dir) / "simulation_results.db"

        logger.info(f"Using SQLite database at: {database_path}")
        return cls(database_path)

    def initialize(self):
        """Initialize the database.

        Creates the database file and schema if it doesn't exist.
        If the database already exists, it will be reused (not cleared).
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

    def finalize(self):
        """Clean up database connections.

        Called when simulation ends. Ensures all connections are properly closed.
        """
        if self.db:
            self.db.close()
