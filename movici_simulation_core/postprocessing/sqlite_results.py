"""SQLite-based simulation results reader.

Provides a SimulationResults-compatible interface for reading simulation
results from SQLite databases created by the SQLite storage backend.
"""

from __future__ import annotations

import typing as t
from pathlib import Path

from movici_simulation_core.core import AttributeSpec, EntityInitDataFormat
from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.postprocessing.results import ResultDataset
from movici_simulation_core.types import FileType


class SQLiteSimulationResults:
    """Read simulation results from SQLite database.

    Provides the same interface as SimulationResults but reads from a SQLite
    database instead of individual JSON files. Compatible with movici-viewer.

    Example::

        >>> results = SQLiteSimulationResults(
        ...     database_path=Path("simulation.db"),
        ...     init_data_dir=Path("init_data"),
        ... )
        >>> dataset = results.get_dataset("transport_network")
    """

    def __init__(
        self,
        database_path: Path,
        init_data_dir: Path,
        attributes: t.Union[AttributeSchema, t.Sequence[AttributeSpec]] = (),
        timeline_info: TimelineInfo = None,
    ):
        """Initialize SQLite results reader.

        :param database_path: Path to SQLite database file
        :param init_data_dir: Directory containing initial dataset JSON files
        :param attributes: Schema for attributes (optional)
        :param timeline_info: Timeline information (optional)
        """
        from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

        self.db_path = Path(database_path)
        self.init_data_dir = Path(init_data_dir)
        self.schema = (
            attributes if isinstance(attributes, AttributeSchema) else AttributeSchema(attributes)
        )
        self.data_reader = EntityInitDataFormat(self.schema)
        self.timeline_info = timeline_info

        # Initialize database connection
        self.db = SimulationDatabase(self.db_path)

        # Build init data index
        self.datasets: t.Dict[str, Path] = self._build_init_data_index()

    def get_dataset(self, name: str) -> ResultDataset:
        """Get a dataset with its initial state and all updates.

        :param name: Dataset name
        :return: ResultDataset with initial data and updates
        :raises ValueError: If dataset not found
        """
        # Load initial data from JSON file
        if not (file := self.datasets.get(name)):
            raise ValueError(f"Dataset {name} not found")

        init_data = self.data_reader.loads(file.read_bytes(), FileType.JSON)

        # Load updates from SQLite database
        updates_from_db = self.db.get_dataset_updates(name)

        # Format updates for ResultDataset
        # SQLite returns:
        #   [{"timestamp": int, "iteration": int, "entity_group": {"attr": {...}}}, ...]
        # ResultDataset expects:
        #   [{"timestamp": int, "iteration": int, "dataset": {"entity_group": {...}}}, ...]
        formatted_updates = []
        for update in updates_from_db:
            timestamp = update["timestamp"]
            iteration = update["iteration"]

            # Extract entity groups (everything except timestamp/iteration)
            entity_groups = {
                k: v for k, v in update.items() if k not in ["timestamp", "iteration"]
            }

            # Wrap in dataset name
            formatted_update = {
                "timestamp": timestamp,
                "iteration": iteration,
                name: entity_groups,  # Wrap entity groups under dataset name
            }
            formatted_updates.append(formatted_update)

        return ResultDataset(init_data, formatted_updates, timeline_info=self.timeline_info)

    def _build_init_data_index(self) -> t.Dict[str, Path]:
        """Build index of initial data files.

        :return: Dictionary mapping dataset names to file paths
        """
        return {file.stem: file for file in self.init_data_dir.glob("*.json")}

    def use(self, plugin):
        """Register a plugin with the schema.

        :param plugin: Plugin to register
        """
        self.schema.use(plugin)

    def get_datasets(self) -> t.List[str]:
        """Get list of all available datasets.

        :return: List of dataset names
        """
        # Get datasets from init_data directory
        return list(self.datasets.keys())

    def get_timestamps(self, dataset_name: str) -> t.List[int]:
        """Get all timestamps for a dataset.

        :param dataset_name: Name of the dataset
        :return: List of timestamps in ascending order
        """
        return self.db.get_timestamps(dataset_name)

    def close(self):
        """Close database connection."""
        if hasattr(self, "db"):
            self.db.close()

    def __enter__(self):
        """Context manager entry.

        :return: Self
        """
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit.

        :param exc_type: Exception type
        :param exc_val: Exception value
        :param exc_tb: Exception traceback
        """
        self.close()


def detect_results_format(updates_path: Path) -> t.Literal["sqlite", "json"]:
    """Detect whether results are stored in SQLite or JSON format.

    :param updates_path: Path to updates directory or database file
    :return: "sqlite" if SQLite database found, "json" otherwise
    """
    # Check if updates_path is a directory with a database file
    if updates_path.is_dir():
        db_path = updates_path / "simulation_results.db"
        if db_path.exists() and db_path.is_file():
            return "sqlite"

    # Check if updates_path itself is a database file
    if updates_path.is_file() and updates_path.suffix == ".db":
        return "sqlite"

    # Check parent directory for database
    if updates_path.is_dir():
        parent_db = updates_path.parent / "simulation_results.db"
        if parent_db.exists():
            return "sqlite"

    # Default to JSON
    return "json"


def get_simulation_results(
    init_data_dir: Path,
    updates_path: Path,
    attributes: t.Union[AttributeSchema, t.Sequence[AttributeSpec]] = (),
    timeline_info: TimelineInfo = None,
    update_pattern: str = r"t(?P<timestamp>\d+)_(?P<iteration>\d+)_(?P<dataset>\w+)\.json",
):
    """Factory function to get appropriate SimulationResults instance.

    Automatically detects whether results are in SQLite or JSON format
    and returns the appropriate reader.

    :param init_data_dir: Directory containing initial dataset JSON files
    :param updates_path: Path to updates directory or SQLite database
    :param attributes: Schema for attributes (optional)
    :param timeline_info: Timeline information (optional)
    :param update_pattern: Regex pattern for JSON files (only used if JSON format detected)
    :return: SQLiteSimulationResults or SimulationResults depending on detected format
    """
    from movici_simulation_core.postprocessing.results import SimulationResults

    format_type = detect_results_format(updates_path)

    if format_type == "sqlite":
        # Determine database path
        if updates_path.is_file() and updates_path.suffix == ".db":
            db_path = updates_path
        elif updates_path.is_dir():
            db_path = updates_path / "simulation_results.db"
            if not db_path.exists():
                db_path = updates_path.parent / "simulation_results.db"
        else:
            db_path = updates_path.parent / "simulation_results.db"

        return SQLiteSimulationResults(
            database_path=db_path,
            init_data_dir=init_data_dir,
            attributes=attributes,
            timeline_info=timeline_info,
        )
    else:
        # JSON format
        return SimulationResults(
            init_data_dir=init_data_dir,
            updates_dir=updates_path,
            update_pattern=update_pattern,
            attributes=attributes,
            timeline_info=timeline_info,
        )
