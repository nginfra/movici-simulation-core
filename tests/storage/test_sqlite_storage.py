import pytest

from movici_simulation_core.storage.sqlite_schema import Metadata, SimulationDatabase


@pytest.fixture
def db_path(tmp_path):
    return tmp_path / "test_simulation.db"


@pytest.fixture
def db(db_path):
    db = SimulationDatabase(db_path)
    db.initialize()
    return db


def test_database_version(db: SimulationDatabase):
    assert db.get_metadata().version == "v1"


def test_only_one_metadata_entry(db: SimulationDatabase):
    db.ensure_metadata()
    with db.get_session() as session:
        assert len(session.query(Metadata).all()) == 1


# ============================================================================
# Database Query Tests
# ============================================================================


def test_get_datasets(db):
    """Test getting list of datasets"""
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})

    datasets = db.get_datasets()
    assert set(datasets) == {"dataset_a", "dataset_b"}


def test_get_timestamps(db):
    """Test getting timestamps for a dataset"""
    db.store_update(0, 0, "dataset", {"entities": {"id": {"data": [1]}}})
    db.store_update(10, 0, "dataset", {"entities": {"id": {"data": [2]}}})
    db.store_update(20, 0, "dataset", {"entities": {"id": {"data": [3]}}})

    timestamps = db.get_timestamps("dataset")
    assert timestamps == [0, 10, 20]


def test_get_update_count_all(db):
    """Test getting total update count"""
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})
    db.store_update(1, 0, "dataset_a", {"entities": {"id": {"data": [3]}}})

    assert db.get_update_count() == 3


def test_get_update_count_by_dataset(db):
    """Test getting update count for specific dataset"""
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})
    db.store_update(0, 0, "dataset_b", {"entities": {"id": {"data": [2]}}})
    db.store_update(1, 0, "dataset_a", {"entities": {"id": {"data": [3]}}})

    assert db.get_update_count("dataset_a") == 2
    assert db.get_update_count("dataset_b") == 1


def test_updates_ordered_by_time(db):
    """Test that updates are returned in chronological order"""

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


def test_concurrent_writes(db):
    """Test that concurrent writes are handled safely"""
    from concurrent.futures import ThreadPoolExecutor

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


def test_empty_database(db):
    """Test querying empty database"""

    assert db.get_datasets() == []
    assert db.get_update_count() == 0
    assert db.get_dataset_updates("nonexistent") == []


def test_nonexistent_dataset(db):
    """Test querying nonexistent dataset"""
    db.store_update(0, 0, "dataset_a", {"entities": {"id": {"data": [1]}}})

    assert db.get_dataset_updates("dataset_b") == []
    assert db.get_timestamps("dataset_b") == []
