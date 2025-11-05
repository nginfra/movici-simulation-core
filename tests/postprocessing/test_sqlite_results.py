"""Tests for SQLite simulation results reader."""

import numpy as np
import pytest

from movici_simulation_core.postprocessing.sqlite_results import (
    SQLiteSimulationResults,
    detect_results_format,
    get_simulation_results,
)
from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

# Skip tests if sqlalchemy not available
pytest.importorskip("sqlalchemy")


@pytest.fixture
def init_data_dir(tmp_path):
    """Create init data directory with sample data"""
    init_dir = tmp_path / "init_data"
    init_dir.mkdir()

    # Create sample init data
    init_data = {
        "transport_network": {
            "road_segments": {
                "id": [1, 2, 3],
                "length": [100.0, 200.0, 150.0],
            }
        }
    }

    init_file = init_dir / "transport_network.json"
    import orjson as json

    init_file.write_bytes(json.dumps(init_data))

    return init_dir


@pytest.fixture
def db_with_updates(tmp_path, global_schema):
    """Create SQLite database with sample updates"""
    db_path = tmp_path / "simulation_results.db"
    db = SimulationDatabase(db_path)

    # Add update at t=0
    db.store_update(
        timestamp=0,
        iteration=0,
        dataset_name="transport_network",
        entity_data={
            "road_segments": {
                "id": {"data": [1, 2, 3]},
                "speed": {"data": [50.0, 60.0, 40.0]},
            }
        },
    )

    # Add update at t=10
    db.store_update(
        timestamp=10,
        iteration=0,
        dataset_name="transport_network",
        entity_data={
            "road_segments": {
                "id": {"data": [1, 2, 3]},
                "speed": {"data": [45.0, 55.0, 35.0]},
            }
        },
    )

    return db_path


# ============================================================================
# SQLiteSimulationResults Tests
# ============================================================================


def test_sqlite_results_init(db_with_updates, init_data_dir):
    """Test SQLiteSimulationResults initialization"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    assert results.db_path == db_with_updates
    assert results.init_data_dir == init_data_dir
    assert "transport_network" in results.datasets


def test_sqlite_results_get_dataset(db_with_updates, init_data_dir):
    """Test getting a dataset from SQLite results"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    dataset = results.get_dataset("transport_network")

    # Check dataset metadata
    assert dataset.name == "transport_network"

    # Check state has initial data
    assert "transport_network" in dataset.state.to_dict()


def test_sqlite_results_get_dataset_not_found(db_with_updates, init_data_dir):
    """Test error when dataset not found"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    with pytest.raises(ValueError, match="Dataset nonexistent not found"):
        results.get_dataset("nonexistent")


def test_sqlite_results_get_datasets(db_with_updates, init_data_dir):
    """Test getting list of datasets"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    datasets = results.get_datasets()
    assert "transport_network" in datasets


def test_sqlite_results_get_timestamps(db_with_updates, init_data_dir):
    """Test getting timestamps for a dataset"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    timestamps = results.get_timestamps("transport_network")
    assert timestamps == [0, 10]


def test_sqlite_results_context_manager(db_with_updates, init_data_dir):
    """Test using SQLiteSimulationResults as context manager"""
    with SQLiteSimulationResults(
        database_path=db_with_updates, init_data_dir=init_data_dir
    ) as results:
        dataset = results.get_dataset("transport_network")
        assert dataset.name == "transport_network"


def test_sqlite_results_updates_applied(db_with_updates, init_data_dir):
    """Test that updates are properly applied to dataset state"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    dataset = results.get_dataset("transport_network")

    # Move to timestamp 0
    dataset.state.move_to(0)
    state_t0 = dataset.state.to_dict()
    speeds_t0 = state_t0["transport_network"]["road_segments"]["speed"]["data"]
    np.testing.assert_array_equal(speeds_t0, [50.0, 60.0, 40.0])

    # Move to timestamp 10
    dataset.state.move_to(10)
    state_t10 = dataset.state.to_dict()
    speeds_t10 = state_t10["transport_network"]["road_segments"]["speed"]["data"]
    np.testing.assert_array_equal(speeds_t10, [45.0, 55.0, 35.0])


def test_sqlite_results_with_schema(db_with_updates, init_data_dir, global_schema):
    """Test SQLiteSimulationResults with schema"""
    results = SQLiteSimulationResults(
        database_path=db_with_updates, init_data_dir=init_data_dir, attributes=global_schema
    )

    dataset = results.get_dataset("transport_network")
    assert dataset is not None


# ============================================================================
# Format Detection Tests
# ============================================================================


def test_detect_sqlite_format_with_db_file(tmp_path):
    """Test detecting SQLite format when database file exists"""
    db_path = tmp_path / "simulation_results.db"
    db_path.touch()

    assert detect_results_format(db_path) == "sqlite"


def test_detect_sqlite_format_in_directory(tmp_path):
    """Test detecting SQLite format when database is in directory"""
    updates_dir = tmp_path / "updates"
    updates_dir.mkdir()
    db_path = updates_dir / "simulation_results.db"
    db_path.touch()

    assert detect_results_format(updates_dir) == "sqlite"


def test_detect_sqlite_format_in_parent(tmp_path):
    """Test detecting SQLite format when database is in parent directory"""
    updates_dir = tmp_path / "scenario" / "updates"
    updates_dir.mkdir(parents=True)
    db_path = tmp_path / "scenario" / "simulation_results.db"
    db_path.touch()

    assert detect_results_format(updates_dir) == "sqlite"


def test_detect_json_format(tmp_path):
    """Test detecting JSON format when no database exists"""
    updates_dir = tmp_path / "updates"
    updates_dir.mkdir()

    # Create some JSON files
    (updates_dir / "t0_0_dataset.json").touch()
    (updates_dir / "t1_0_dataset.json").touch()

    assert detect_results_format(updates_dir) == "json"


def test_detect_json_format_empty_dir(tmp_path):
    """Test detecting JSON format for empty directory"""
    updates_dir = tmp_path / "updates"
    updates_dir.mkdir()

    assert detect_results_format(updates_dir) == "json"


# ============================================================================
# Factory Function Tests
# ============================================================================


def test_get_simulation_results_sqlite(db_with_updates, init_data_dir):
    """Test factory returns SQLiteSimulationResults for SQLite format"""
    results = get_simulation_results(
        init_data_dir=init_data_dir, updates_path=db_with_updates.parent
    )

    assert isinstance(results, SQLiteSimulationResults)
    dataset = results.get_dataset("transport_network")
    assert dataset.name == "transport_network"


def test_get_simulation_results_json(tmp_path, init_data_dir):
    """Test factory returns SimulationResults for JSON format"""
    from movici_simulation_core.postprocessing.results import SimulationResults

    updates_dir = tmp_path / "updates"
    updates_dir.mkdir()

    results = get_simulation_results(init_data_dir=init_data_dir, updates_path=updates_dir)

    assert isinstance(results, SimulationResults)


def test_get_simulation_results_with_db_file(db_with_updates, init_data_dir):
    """Test factory with direct database file path"""
    results = get_simulation_results(init_data_dir=init_data_dir, updates_path=db_with_updates)

    assert isinstance(results, SQLiteSimulationResults)
    dataset = results.get_dataset("transport_network")
    assert dataset.name == "transport_network"


# ============================================================================
# Integration Tests
# ============================================================================


def test_sqlite_results_multiple_datasets(tmp_path, init_data_dir):
    """Test SQLite results with multiple datasets"""
    db_path = tmp_path / "simulation_results.db"
    db = SimulationDatabase(db_path)

    # Add init data for second dataset
    init_data_2 = {"water_network": {"pipes": {"id": [10, 20], "diameter": [0.5, 0.8]}}}
    import orjson as json

    (init_data_dir / "water_network.json").write_bytes(json.dumps(init_data_2))

    # Add updates for both datasets
    db.store_update(
        timestamp=0,
        iteration=0,
        dataset_name="transport_network",
        entity_data={"road_segments": {"id": {"data": [1, 2]}, "speed": {"data": [50.0, 60.0]}}},
    )

    db.store_update(
        timestamp=0,
        iteration=1,
        dataset_name="water_network",
        entity_data={"pipes": {"id": {"data": [10, 20]}, "flow": {"data": [10.0, 15.0]}}},
    )

    # Create results
    results = SQLiteSimulationResults(database_path=db_path, init_data_dir=init_data_dir)

    # Check both datasets
    datasets = results.get_datasets()
    assert "transport_network" in datasets
    assert "water_network" in datasets

    # Get both datasets
    ds1 = results.get_dataset("transport_network")
    ds2 = results.get_dataset("water_network")

    assert ds1.name == "transport_network"
    assert ds2.name == "water_network"


def test_sqlite_results_backwards_compatible_interface(db_with_updates, init_data_dir):
    """Test that SQLiteSimulationResults has same interface as SimulationResults"""
    sqlite_results = SQLiteSimulationResults(
        database_path=db_with_updates, init_data_dir=init_data_dir
    )

    # Check interface matches
    assert hasattr(sqlite_results, "get_dataset")
    assert hasattr(sqlite_results, "use")

    # Test get_dataset works same way
    dataset = sqlite_results.get_dataset("transport_network")
    assert hasattr(dataset, "state")
    assert hasattr(dataset, "metadata")
    assert hasattr(dataset, "slice")


def test_sqlite_results_timeline_progression(db_with_updates, init_data_dir):
    """Test that timeline progression works correctly"""
    results = SQLiteSimulationResults(database_path=db_with_updates, init_data_dir=init_data_dir)

    dataset = results.get_dataset("transport_network")
    timestamps = dataset.state.get_timestamps("transport_network")

    # Should have 0 and 10 from database updates
    # Note: -1 is the internal initial state, not stored in database
    assert 0 in timestamps
    assert 10 in timestamps

    # Move through timeline
    dataset.state.move_to(0)  # First update
    state_0 = dataset.state.to_dict()
    assert "transport_network" in state_0

    dataset.state.move_to(10)  # Second update
    state_10 = dataset.state.to_dict()
    assert "transport_network" in state_10

    dataset.state.move_to(0)  # Back to first update

    # Verify reversibility works
    state = dataset.state.to_dict()
    assert "transport_network" in state
