"""Tests for SQLite storage strategy."""

from unittest.mock import Mock

import numpy as np
import pytest

from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.schema import AttributeSpec, DataType
from movici_simulation_core.models.data_collector.data_collector import DataCollector, UpdateInfo
from movici_simulation_core.settings import Settings
from movici_simulation_core.storage.sqlite_schema import SimulationDatabase
from movici_simulation_core.storage.sqlite_strategy import SQLiteStorageStrategy
from movici_simulation_core.testing.model_tester import ModelTester


@pytest.fixture
def storage_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("storage")


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_simulation.db"


@pytest.fixture
def model_config_sqlite(db_path):
    return {
        "gather_filter": None,
        "database_path": str(db_path),
    }


@pytest.fixture
def settings_sqlite(tmp_path):
    return Settings(storage="sqlite", storage_dir=tmp_path)


@pytest.fixture
def model_sqlite(model_config_sqlite):
    return DataCollector(model_config_sqlite)


@pytest.fixture
def logger():
    return Mock()


@pytest.fixture
def additional_attributes():
    return [
        AttributeSpec("id", DataType(int)),
        AttributeSpec("attr", DataType(int)),
    ]


@pytest.fixture()
def run_updates(global_schema, settings_sqlite):
    def _run(model, updates):
        tester = ModelTester(model, settings_sqlite, schema=global_schema)
        tester.initialize()
        for timestamp, data in updates:
            tester.update(timestamp, data)
        tester.close()

    return _run


# ============================================================================
# Strategy Selection Tests
# ============================================================================


def test_picks_sqlite_strategy(model_sqlite, logger, settings_sqlite):
    """Test that SQLite strategy is selected when storage='sqlite'"""
    strategy = model_sqlite.get_storage_strategy(settings_sqlite, logger)
    assert isinstance(strategy, SQLiteStorageStrategy)


def test_sqlite_strategy_choose_with_database_path(db_path, logger):
    """Test SQLiteStorageStrategy.choose with explicit database_path"""
    model_config = {"database_path": str(db_path)}
    settings = Settings(storage="sqlite")

    strategy = SQLiteStorageStrategy.choose(model_config, settings, logger)

    assert isinstance(strategy, SQLiteStorageStrategy)
    assert strategy.database_path == db_path


def test_sqlite_strategy_choose_with_storage_dir(tmp_path, logger):
    """Test SQLiteStorageStrategy.choose falls back to storage_dir"""
    model_config = {"storage_dir": str(tmp_path)}
    settings = Settings(storage="sqlite")

    strategy = SQLiteStorageStrategy.choose(model_config, settings, logger)

    assert isinstance(strategy, SQLiteStorageStrategy)
    # Check that database is in the correct directory with timestamped name
    assert strategy.database_path.parent == tmp_path
    assert strategy.database_path.name.startswith("simulation_results_")
    assert strategy.database_path.suffix == ".db"


def test_sqlite_strategy_choose_raises_without_paths(logger):
    """Test that choose() raises ValueError without any path configuration"""
    model_config = {}
    settings = Settings(storage="sqlite")

    with pytest.raises(ValueError, match="No database_path or storage_dir"):
        SQLiteStorageStrategy.choose(model_config, settings, logger)


# ============================================================================
# Database Storage Tests
# ============================================================================


def test_sqlite_storage_creates_database(db_path, global_schema):
    """Test that SQLite storage creates database file"""
    strategy = SQLiteStorageStrategy(db_path)
    strategy.initialize()

    assert db_path.exists()
    assert db_path.is_file()


def test_sqlite_storage_stores_update(db_path, global_schema):
    """Test storing a single update in SQLite"""
    strategy = SQLiteStorageStrategy(db_path)
    strategy.initialize()

    upd = {"dataset": {"entity_group": {"id": [1, 2, 3], "attr": [10, 20, 30]}}}
    info = UpdateInfo(
        name="dataset",
        timestamp=1,
        iteration=2,
        data=EntityInitDataFormat(schema=global_schema).load_json(upd)["dataset"],
    )

    strategy.store(info)

    # Verify data was stored
    db = SimulationDatabase(db_path)
    updates = db.get_dataset_updates("dataset")
    assert len(updates) == 1
    assert updates[0]["timestamp"] == 1
    assert updates[0]["iteration"] == 2


def test_sqlite_storage_stores_sparse_array(db_path, global_schema):
    """Test storing CSR sparse arrays"""
    strategy = SQLiteStorageStrategy(db_path)
    strategy.initialize()

    # Create update with CSR sparse array
    upd = {
        "dataset": {
            "entity_group": {
                "id": [1, 2, 3],
                "sparse_attr": [[10], [20, 30], [40]],  # CSR format with row_ptr
            }
        }
    }
    info = UpdateInfo(
        name="dataset",
        timestamp=0,
        iteration=0,
        data=EntityInitDataFormat(schema=global_schema).load_json(upd)["dataset"],
    )

    strategy.store(info)

    # Verify CSR data was stored correctly
    db = SimulationDatabase(db_path)
    updates = db.get_dataset_updates("dataset")
    assert len(updates) == 1

    sparse_data = updates[0]["entity_group"]["sparse_attr"]
    assert "data" in sparse_data
    assert "row_ptr" in sparse_data
    np.testing.assert_array_equal(sparse_data["data"], [10, 20, 30, 40])
    np.testing.assert_array_equal(sparse_data["row_ptr"], [0, 1, 3, 4])


# ============================================================================
# Integration Tests
# ============================================================================


def test_stores_one_update_sqlite(model_sqlite, db_path, run_updates):
    """Test storing one update through DataCollector"""
    upd = {"some_dataset": {"some_entities": {"id": [1], "attr": [10]}}}
    run_updates(model_sqlite, [(0, upd)])

    # Verify data in database
    db = SimulationDatabase(db_path)
    assert db.get_update_count() == 1

    updates = db.get_dataset_updates("some_dataset")
    assert len(updates) == 1
    assert updates[0]["timestamp"] == 0
    assert updates[0]["iteration"] == 0


def test_stores_multiple_updates_sqlite(model_sqlite, db_path, run_updates):
    """Test storing multiple updates through DataCollector"""
    run_updates(
        model_sqlite,
        [
            (0, {"some_dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
            (0, {"other_dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
        ],
    )

    # Verify data in database
    db = SimulationDatabase(db_path)
    assert db.get_update_count() == 2

    datasets = set(db.get_datasets())
    assert datasets == {"some_dataset", "other_dataset"}


def test_stores_updates_from_multiple_datasets(model_sqlite, db_path, run_updates):
    """Test storing updates for multiple datasets"""
    run_updates(
        model_sqlite,
        [
            (
                0,
                {
                    "dataset_a": {"entities": {"id": [1, 2], "attr": [10, 20]}},
                    "dataset_b": {"entities": {"id": [3, 4], "attr": [30, 40]}},
                },
            )
        ],
    )

    db = SimulationDatabase(db_path)
    assert db.get_update_count() == 2
    assert set(db.get_datasets()) == {"dataset_a", "dataset_b"}


def test_can_aggregate_updates_sqlite(model_sqlite, settings_sqlite, db_path, global_schema):
    """Test aggregating updates when aggregate_updates=True"""
    model_sqlite.config["aggregate_updates"] = True

    tester = ModelTester(model_sqlite, settings_sqlite, schema=global_schema)
    tester.initialize()
    tester.new_time(0)
    tester.update(0, {"dataset": {"some_entities": {"id": [1, 2], "attr": [10, 20]}}})
    tester.update(0, {"dataset": {"some_entities": {"id": [2], "attr": [21]}}})

    # No updates stored yet (waiting for new_time)
    db = SimulationDatabase(db_path)
    assert db.get_update_count() == 0

    tester.new_time(1)
    tester.close()

    # Now updates should be stored and aggregated
    assert db.get_update_count() == 1
    updates = db.get_dataset_updates("dataset")
    assert len(updates) == 1

    # Verify aggregated data
    entity_data = updates[0]["some_entities"]
    np.testing.assert_array_equal(entity_data["id"]["data"], [1, 2])
    np.testing.assert_array_equal(entity_data["attr"]["data"], [10, 21])


def test_only_submits_on_changed_data_sqlite(model_sqlite, run_updates):
    """Test that only changed data triggers storage"""
    model_sqlite.submit = Mock()
    run_updates(
        model_sqlite,
        [
            (0, {"dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
            (0, {"dataset": {"some_entities": {"id": [1], "attr": [10]}}}),
        ],
    )
    # Only one submit because second update has no changes
    assert model_sqlite.submit.call_count == 1


def test_submits_job_per_dataset_sqlite(model_sqlite, run_updates):
    """Test that each dataset gets its own storage job"""
    model_sqlite.submit = Mock()
    run_updates(
        model_sqlite,
        [
            (
                0,
                {
                    "some_dataset": {"some_entities": {"id": [1], "attr": [10]}},
                    "other_dataset": {"some_entities": {"id": [1], "attr": [10]}},
                },
            )
        ],
    )
    assert model_sqlite.submit.call_count == 2


# ============================================================================
# Database Query Tests
# ============================================================================


def test_get_datasets(db_path):
    """Test getting list of datasets"""
    db = SimulationDatabase(db_path)
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})

    datasets = db.get_datasets()
    assert set(datasets) == {"dataset_a", "dataset_b"}


def test_get_timestamps(db_path):
    """Test getting timestamps for a dataset"""
    db = SimulationDatabase(db_path)
    db.store_update(0, 0, "dataset", {"entities": {"id": {"data": [1]}}})
    db.store_update(10, 0, "dataset", {"entities": {"id": {"data": [2]}}})
    db.store_update(20, 0, "dataset", {"entities": {"id": {"data": [3]}}})

    timestamps = db.get_timestamps("dataset")
    assert timestamps == [0, 10, 20]


def test_get_update_count_all(db_path):
    """Test getting total update count"""
    db = SimulationDatabase(db_path)
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})
    db.store_update(1, 0, "dataset_a", {"entities": {"id": {"data": [3]}}})

    assert db.get_update_count() == 3


def test_get_update_count_by_dataset(db_path):
    """Test getting update count for specific dataset"""
    db = SimulationDatabase(db_path)
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})
    db.store_update(1, 0, "dataset_a", {"entities": {"id": {"data": [3]}}})

    assert db.get_update_count("dataset_a") == 2
    assert db.get_update_count("dataset_b") == 1


def test_updates_ordered_by_time(db_path):
    """Test that updates are returned in chronological order"""
    db = SimulationDatabase(db_path)

    # Insert out of order
    db.store_update(10, 0, "dataset", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset", {"entities": {"id": {"data": [2]}}})
    db.store_update(5, 1, "dataset", {"entities": {"id": {"data": [3]}}})
    db.store_update(5, 0, "dataset", {"entities": {"id": {"data": [4]}}})

    updates = db.get_dataset_updates("dataset")

    # Should be sorted by (timestamp, iteration)
    assert updates[0]["timestamp"] == 0
    assert updates[1]["timestamp"] == 5
    assert updates[1]["iteration"] == 0
    assert updates[2]["timestamp"] == 5
    assert updates[2]["iteration"] == 1
    assert updates[3]["timestamp"] == 10


# ============================================================================
# Thread Safety Tests
# ============================================================================


def test_concurrent_writes(db_path):
    """Test that concurrent writes are handled safely"""
    from concurrent.futures import ThreadPoolExecutor

    db = SimulationDatabase(db_path)

    def write_update(i):
        db.store_update(
            timestamp=i,
            iteration=0,
            dataset_name=f"dataset_{i % 3}",
            entity_data={"entities": {"id": {"data": [i]}}},
        )

    # Write 20 updates concurrently
    with ThreadPoolExecutor(max_workers=5) as executor:
        executor.map(write_update, range(20))

    # Verify all updates were stored
    assert db.get_update_count() == 20


# ============================================================================
# Edge Cases
# ============================================================================


def test_empty_database(db_path):
    """Test querying empty database"""
    db = SimulationDatabase(db_path)

    assert db.get_datasets() == []
    assert db.get_update_count() == 0
    assert db.get_dataset_updates("nonexistent") == []


def test_nonexistent_dataset(db_path):
    """Test querying nonexistent dataset"""
    db = SimulationDatabase(db_path)
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})

    assert db.get_dataset_updates("dataset_b") == []
    assert db.get_timestamps("dataset_b") == []


def test_initial_datasets_stored_automatically(tmp_path, logger):
    """Test that initial datasets are automatically stored during DataCollector initialization"""
    import orjson

    # Create init_data directory with test datasets
    init_data_dir = tmp_path / "init_data"
    init_data_dir.mkdir()

    # Create two init datasets
    dataset1 = {"transport_network": {"road_segments": {"id": [1, 2, 3]}}}
    dataset2 = {"water_network": {"pipes": {"id": [10, 20]}}}

    (init_data_dir / "transport_network.json").write_bytes(orjson.dumps(dataset1))
    (init_data_dir / "water_network.json").write_bytes(orjson.dumps(dataset2))

    # Create DataCollector with SQLite storage
    db_path = tmp_path / "simulation.db"
    model_config = {
        "gather_filter": None,
        "database_path": str(db_path),
    }
    settings = Settings(storage="sqlite", init_data_dir=init_data_dir)

    model = DataCollector(model_config)
    model.initialize(settings, logger)

    # Verify initial datasets were stored in database
    db = SimulationDatabase(db_path)
    assert db.has_initial_datasets() is True

    # Verify both datasets are present
    all_datasets = db.get_all_initial_datasets()
    assert "transport_network" in all_datasets
    assert "water_network" in all_datasets

    # Verify content matches
    assert all_datasets["transport_network"] == dataset1
    assert all_datasets["water_network"] == dataset2

    # Verify individual retrieval
    transport_data = db.get_initial_dataset("transport_network")
    assert transport_data == dataset1

    model.close()
