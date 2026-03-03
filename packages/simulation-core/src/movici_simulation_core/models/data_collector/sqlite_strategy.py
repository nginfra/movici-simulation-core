"""SQLite storage strategy for DataCollector model.

This module provides SQLiteStorageStrategy which stores simulation updates
in a SQLite database instead of individual JSON files.
"""

from __future__ import annotations

import itertools
import logging
from datetime import datetime
from pathlib import Path

import orjson

from movici_simulation_core.models.data_collector.strategy import StorageStrategy
from movici_simulation_core.settings import Settings
from movici_simulation_core.storage.sqlite_schema import DatasetFormat, SimulationDatabase


class SQLiteStorageStrategy(StorageStrategy):
    """Storage strategy that persists simulation updates to an SQLite database.

    Features:

    * Thread-safe concurrent writes (uses internal locking)
    * Efficient binary storage of numpy arrays
    * Support for CSR sparse arrays
    * Single database file instead of thousands of JSON files
    * Fast indexed queries by timestamp, iteration, dataset
    """

    def __init__(self, database_path: Path, settings: Settings):
        """Initialize SQLite storage strategy.

        :param database_path: Path to SQLite database file
        :param settings: Global simulation settings (for init_data_dir and scenario_config)
        """
        self.database_path = Path(database_path)
        self.settings = settings
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
        return cls(database_path, settings)

    def initialize(self):
        """Initialize the database.


        Also stores initial datasets from Settings.data_dir for self-contained archives.
        """
        self.database_path.parent.mkdir(parents=True, exist_ok=True)
        self.db = SimulationDatabase(self.database_path)

        self.db.initialize()
        # Store initial datasets in database for self-contained archives
        if self.settings.data_dir:
            self._store_initial_datasets()

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

    def _store_initial_datasets(self):
        """Store initial datasets in database for complete snapshot.

        This makes the database self-contained without requiring separate
        init_data directory.

        Reads dataset list from scenario config and handles different file formats:

        * ``.json`` files: Auto-detect entity_based vs unstructured
        * Other suffixes: Treat as binary data

        :raises FileNotFoundError: If init_data_dir does not exist
        :raises NotADirectoryError: If init_data_dir is not a directory
        """
        init_data_dir = Path(self.settings.data_dir)

        # Error if init_data_dir doesn't exist
        if not init_data_dir.exists():
            raise FileNotFoundError(
                f"init_data_dir does not exist: {init_data_dir}. Cannot store initial datasets."
            )

        if not init_data_dir.is_dir():
            raise NotADirectoryError(f"init_data_dir is not a directory: {init_data_dir}")

        # Get dataset list from scenario config
        datasets = self.settings.datasets or []

        # If no datasets in config, fall back to all files in init_data_dir
        if not datasets:
            # Store all JSON files found
            for json_file in init_data_dir.glob("*.json"):
                dataset_name = json_file.stem
                dataset_data = orjson.loads(json_file.read_bytes())
                # Auto-detect format (default to unstructured for backward compatibility)
                format_type = self._detect_format(dataset_data)
                self.db.store_initial_dataset(dataset_name, dataset_data, format=format_type)
            return

        # Process datasets from scenario config
        for dataset_config in datasets:
            dataset_name = dataset_config.get("name")
            if not dataset_name:
                continue

            # Try to find the file - check for .json first, then any extension
            dataset_path = init_data_dir / f"{dataset_name}.json"

            if not dataset_path.exists():
                # Try without .json extension (could be binary file)
                dataset_path = init_data_dir / dataset_name

            if not dataset_path.exists():
                # Try finding any file that starts with dataset_name
                matching_files = list(init_data_dir.glob(f"{dataset_name}.*"))
                if matching_files:
                    dataset_path = matching_files[0]
                else:
                    continue  # Skip if file not found

            # Determine format based on file extension
            if dataset_path.suffix == ".json":
                # JSON file - load and auto-detect format
                dataset_data = orjson.loads(dataset_path.read_bytes())
                format_type = self._detect_format(dataset_data)
                self.db.store_initial_dataset(dataset_name, dataset_data, format=format_type)
            else:
                # Non-JSON file - treat as binary
                dataset_data = dataset_path.read_bytes()
                self.db.store_initial_dataset(
                    dataset_name, dataset_data, format=DatasetFormat.BINARY
                )

    def _detect_format(self, data: dict) -> DatasetFormat:
        """Auto-detect if JSON data is entity_based or unstructured.

        Entity-based format has structure::

            {
                "entity_group": {
                    "attribute_name": {"data": [...], ...}
                }
            }

        :param data: Parsed JSON data
        :return: Detected format (``ENTITY_BASED`` or ``UNSTRUCTURED``)
        """
        # Check if data looks like entity-based format
        if not isinstance(data, dict):
            return DatasetFormat.UNSTRUCTURED

        # Check if all values are dicts containing attributes with "data" key
        for _entity_group, attributes in data.items():
            if not isinstance(attributes, dict):
                return DatasetFormat.UNSTRUCTURED

            # Check if at least one attribute has "data" key
            for _attr_name, attr_data in attributes.items():
                if isinstance(attr_data, dict) and "data" in attr_data:
                    # Looks like entity-based format
                    return DatasetFormat.ENTITY_BASED

        return DatasetFormat.UNSTRUCTURED

    def close(self):
        """Clean up database connections.

        Called when simulation ends. Ensures all connections are properly closed.
        """
        if self.db:
            self.db.close()
