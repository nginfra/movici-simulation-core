SQLite Storage for Intermediate Simulation Data
================================================

Overview
--------

This implementation adds SQLite database support as an alternative to JSON file storage for the ``DataCollector`` model. Instead of creating thousands of individual JSON files, all intermediate simulation data is stored in a single SQLite database with efficient indexing and querying capabilities.

Features
--------

* **Single File Storage** - One ``.db`` file instead of thousands of JSON files
* **Faster Writes** - WAL mode with concurrent worker support
* **Faster Reads** - Indexed queries vs file scanning
* **Smaller Storage** - Binary numpy array storage
* **Thread-Safe** - Built-in locking for concurrent writes
* **CSR Sparse Array Support** - First-class support via ``indptr`` column
* **Backward Compatible** - JSON storage still available and default
* **Zero External Services** - No database server needed

Installation
------------

The SQLite storage requires SQLAlchemy::

    pip install sqlalchemy

Or if using Poetry::

    poetry add sqlalchemy

Usage
-----

Basic Configuration
~~~~~~~~~~~~~~~~~~~

Option 1: Settings-based (Recommended)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from movici_simulation_core.simulation import Simulation
    from movici_simulation_core.settings import Settings

    settings = Settings(
        storage="sqlite",           # Enable SQLite storage
        storage_dir="./results"     # Directory for database file
    )

    sim = Simulation(data_dir="./data", settings=settings)

    sim.add_model("data_collector", {
        "gather_filter": "*",
        "aggregate_updates": False
    })

This creates: ``./results/simulation_results.db``

Option 2: Model Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    sim.add_model("data_collector", {
        "gather_filter": "*",
        "database_path": "./results/my_simulation.db"  # Explicit path
    })

Configuration Options
~~~~~~~~~~~~~~~~~~~~~

+-------------------+--------+---------------------------------------------------------------+
| Option            | Type   | Description                                                   |
+===================+========+===============================================================+
| database_path     | string | Full path to SQLite database file                             |
+-------------------+--------+---------------------------------------------------------------+
| storage_dir       | string | Directory for database (creates ``simulation_results.db``)    |
+-------------------+--------+---------------------------------------------------------------+
| gather_filter     | object | Subscribe filter for data collection                          |
|                   | /null  |                                                               |
|                   | /"*"   |                                                               |
+-------------------+--------+---------------------------------------------------------------+
| aggregate_updates | bool   | Batch updates per timestamp                                   |
+-------------------+--------+---------------------------------------------------------------+

**Priority**: ``database_path`` > ``storage_dir`` (model config) > ``storage_dir`` (settings)

Switching from JSON to SQLite
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

**Before (JSON):**

.. code-block:: python

    settings = Settings(storage="disk")
    model_config = {"storage_dir": "./results"}

**After (SQLite):**

.. code-block:: python

    settings = Settings(storage="sqlite")
    model_config = {"database_path": "./results/simulation.db"}

Querying Results
----------------

Using SimulationDatabase API
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

    # Open database
    db = SimulationDatabase("./results/simulation.db")

    # Get all datasets
    datasets = db.get_datasets()
    # ['transport_network', 'water_network', ...]

    # Get timestamps for a dataset
    timestamps = db.get_timestamps('transport_network')
    # [0, 10, 20, 30, ...]

    # Get all updates for a dataset (in chronological order)
    updates = db.get_dataset_updates('transport_network')
    # [
    #   {
    #     'timestamp': 0,
    #     'iteration': 0,
    #     'road_segments': {
    #       'id': {'data': array([1, 2, 3])},
    #       'speed': {'data': array([50.0, 60.0, 40.0])}
    #     }
    #   },
    #   ...
    # ]

    # Get statistics
    total_updates = db.get_update_count()
    dataset_updates = db.get_update_count('transport_network')

Direct SQL Queries (Advanced)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from sqlalchemy import create_engine

    engine = create_engine('sqlite:///./results/simulation.db')

    with engine.connect() as conn:
        # Get all timestamps
        result = conn.execute(
            "SELECT DISTINCT timestamp FROM update ORDER BY timestamp"
        )
        timestamps = [row[0] for row in result]

        # Count updates per dataset
        result = conn.execute("""
            SELECT dataset_name, COUNT(*)
            FROM update
            GROUP BY dataset_name
        """)
        for dataset, count in result:
            print(f"{dataset}: {count} updates")

Viewer Compatibility (movici-viewer)
-------------------------------------

Automatic Format Detection
~~~~~~~~~~~~~~~~~~~~~~~~~~

The ``get_simulation_results()`` factory function automatically detects whether results are stored in SQLite or JSON format and returns the appropriate reader:

.. code-block:: python

    from movici_simulation_core.postprocessing import get_simulation_results

    # Automatically detects format (SQLite or JSON)
    results = get_simulation_results(
        init_data_dir=Path("./init_data"),
        updates_path=Path("./scenario/updates")  # Can be directory or .db file
    )

    dataset = results.get_dataset("transport_network")

Updating movici-viewer
~~~~~~~~~~~~~~~~~~~~~~

To add SQLite support to movici-viewer, update the ``DirectorySource.get_results()`` method:

**Before:**

.. code-block:: python

    # movici-viewer/server/movici_viewer/model/model.py
    def get_results(self, scenario: str) -> SimulationResults:
        updates_dir = self.get_updates_path(scenario)
        return SimulationResults(
            init_data_dir=self.init_data_dir,
            updates_dir=updates_dir,
            attributes=self.schema,
        )

**After (with auto-detection):**

.. code-block:: python

    # movici-viewer/server/movici_viewer/model/model.py
    from movici_simulation_core.postprocessing import get_simulation_results

    def get_results(self, scenario: str):
        updates_path = self.get_updates_path(scenario)
        return get_simulation_results(
            init_data_dir=self.init_data_dir,
            updates_path=updates_path,
            attributes=self.schema,
        )

This automatically detects SQLite databases and uses ``SQLiteSimulationResults`` when appropriate, falling back to ``SimulationResults`` for JSON files.

SQLiteSimulationResults API
~~~~~~~~~~~~~~~~~~~~~~~~~~~

``SQLiteSimulationResults`` provides the same interface as ``SimulationResults``:

.. code-block:: python

    from movici_simulation_core.postprocessing import SQLiteSimulationResults

    results = SQLiteSimulationResults(
        database_path=Path("simulation.db"),
        init_data_dir=Path("./init_data"),
    )

    # Same methods as SimulationResults
    dataset = results.get_dataset("transport_network")
    datasets = results.get_datasets()
    timestamps = results.get_timestamps("transport_network")

    # Use with context manager
    with SQLiteSimulationResults(database_path, init_data_dir) as results:
        dataset = results.get_dataset("transport_network")

Backward Compatibility
~~~~~~~~~~~~~~~~~~~~~~

* Existing JSON workflows continue to work unchanged
* Viewer automatically detects SQLite vs JSON format
* No configuration changes required
* Graceful fallback if SQLAlchemy not installed

Database Schema
---------------

Tables
~~~~~~

update
^^^^^^

Stores metadata for each simulation update.

+-------------+-------------+-------------------------------+
| Column      | Type        | Description                   |
+=============+=============+===============================+
| id          | INTEGER PK  | Auto-increment primary key    |
+-------------+-------------+-------------------------------+
| timestamp   | INTEGER     | Simulation timestamp          |
+-------------+-------------+-------------------------------+
| iteration   | INTEGER     | Iteration at this timestamp   |
+-------------+-------------+-------------------------------+
| dataset_name| STRING      | Name of dataset               |
+-------------+-------------+-------------------------------+
| origin      | STRING      | Optional model identifier     |
+-------------+-------------+-------------------------------+

**Indexes**: ``(timestamp, iteration)``, ``dataset_name``

**Unique**: ``(timestamp, iteration, dataset_name)``

attribute_data
^^^^^^^^^^^^^^

Stores entity attribute data (links to numpy arrays).

+----------------+-------------+------------------------------------------------+
| Column         | Type        | Description                                    |
+================+=============+================================================+
| id             | INTEGER PK  | Auto-increment primary key                     |
+----------------+-------------+------------------------------------------------+
| entity_group   | STRING      | Entity group name                              |
+----------------+-------------+------------------------------------------------+
| attribute_name | STRING      | Attribute name                                 |
+----------------+-------------+------------------------------------------------+
| data_id        | INTEGER FK  | Foreign key to numpy_array                     |
+----------------+-------------+------------------------------------------------+
| indptr_id      | INTEGER FK  | Foreign key to numpy_array (for CSR)           |
+----------------+-------------+------------------------------------------------+
| min_val        | FLOAT       | Optional min value                             |
+----------------+-------------+------------------------------------------------+
| max_val        | FLOAT       | Optional max value                             |
+----------------+-------------+------------------------------------------------+

**Indexes**: ``entity_group``, ``attribute_name``

numpy_array
^^^^^^^^^^^

Stores numpy arrays as binary data with metadata.

+--------+-------------+----------------------------------------+
| Column | Type        | Description                            |
+========+=============+========================================+
| id     | INTEGER PK  | Auto-increment primary key             |
+--------+-------------+----------------------------------------+
| dtype  | STRING(20)  | NumPy dtype string (e.g., '<i4')       |
+--------+-------------+----------------------------------------+
| shape  | STRING      | JSON array of dimensions               |
+--------+-------------+----------------------------------------+
| data   | BLOB        | Raw numpy bytes                        |
+--------+-------------+----------------------------------------+

**Example**::

    id: 1
    dtype: '<f8'
    shape: '[100, 5]'
    data: <binary blob>

update_attribute
^^^^^^^^^^^^^^^^

Junction table linking updates to attributes (many-to-many).

+-------------------+-------------+----------------------------------+
| Column            | Type        | Description                      |
+===================+=============+==================================+
| update_id         | INTEGER FK  | Foreign key to update            |
+-------------------+-------------+----------------------------------+
| attribute_data_id | INTEGER FK  | Foreign key to attribute_data    |
+-------------------+-------------+----------------------------------+

Data Format
-----------

Input Format (movici format)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    {
        "entity_group_name": {
            "attribute_name": {
                "data": [1, 2, 3, ...],          # Uniform array
                "row_ptr": [0, 2, 5, ...]        # CSR sparse (optional)
            }
        }
    }

Output Format (reconstructed)
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    {
        "timestamp": 0,
        "iteration": 0,
        "entity_group_name": {
            "attribute_name": {
                "data": np.array([1, 2, 3]),
                "row_ptr": np.array([0, 2, 5])  # If sparse
            }
        }
    }

Configuration for Performance
------------------------------

SQLite is automatically configured with::

    PRAGMA journal_mode=WAL      # Write-Ahead Logging for concurrency
    PRAGMA synchronous=NORMAL    # Fast writes, safe crash recovery
    PRAGMA foreign_keys=ON       # Referential integrity

Migration from JSON
-------------------

Migrating Existing Results
~~~~~~~~~~~~~~~~~~~~~~~~~~

.. code-block:: python

    from pathlib import Path
    from movici_simulation_core.postprocessing.results import SimulationResults
    from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

    # Load JSON results
    json_results = SimulationResults(
        init_data_dir=Path("./old_results/init"),
        updates_dir=Path("./old_results/updates")
    )

    # Create SQLite database
    db = SimulationDatabase("./new_results/migrated.db")

    # Migrate
    for dataset_name in json_results.get_datasets():
        dataset = json_results.get_dataset(dataset_name)

        for update in dataset.updates:
            entity_data = {
                k: v for k, v in update.items()
                if k not in ["timestamp", "iteration"]
            }

            db.store_update(
                timestamp=update["timestamp"],
                iteration=update["iteration"],
                dataset_name=dataset_name,
                entity_data=entity_data
            )

    print(f"Migrated {db.get_update_count()} updates")

Architecture
------------

Design Principles
~~~~~~~~~~~~~~~~~

This implementation follows established patterns for simulation data storage:

1. **NumpyArray Storage** - Stores dtype, shape, and binary data separately
2. **CSR Support** - ``data_id`` + ``indptr_id`` pattern for sparse arrays
3. **Update Tracking** - ``(timestamp, iteration, dataset_name)`` uniqueness
4. **Junction Tables** - Clean many-to-many relationships

Integration with DataCollector
~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~

::

    DataCollector (thread pool with 5 workers)
        ↓
    StorageStrategy.store(UpdateInfo)
        ↓
    SQLiteStorageStrategy
        ↓ (with locking)
    SimulationDatabase.store_update()
        ↓
    SQLAlchemy Session
        ↓
    SQLite Database (WAL mode)

Thread Safety
-------------

Concurrent Writes
~~~~~~~~~~~~~~~~~

The implementation is thread-safe for concurrent writes:

.. code-block:: python

    # Internal locking ensures safety
    with self._write_lock:
        with self.Session() as session:
            # ... store update ...
            session.commit()

Thread Pool Configuration
~~~~~~~~~~~~~~~~~~~~~~~~~

DataCollector uses 5 worker threads by default:

.. code-block:: python

    self.pool = LimitedThreadPoolExecutor(max_workers=5)

SQLite handles this well with:

* WAL mode (Write-Ahead Logging)
* Internal write lock
* 30-second timeout for lock acquisition

Troubleshooting
---------------

SQLite not available
~~~~~~~~~~~~~~~~~~~~

**Error**: ``No module named 'sqlalchemy'``

**Solution**::

    pip install sqlalchemy

Database locked
~~~~~~~~~~~~~~~

**Error**: ``database is locked``

**Causes**:

* Long-running read transaction
* Multiple processes accessing database

**Solutions**:

.. code-block:: python

    # Increase timeout
    engine = create_engine(
        'sqlite:///path.db',
        connect_args={'timeout': 60.0}  # Wait up to 60s
    )

    # Or use WAL mode (already enabled by default)
    PRAGMA journal_mode=WAL

Storage strategy not found
~~~~~~~~~~~~~~~~~~~~~~~~~~

**Error**: ``Unsupported storage method 'sqlite'``

**Causes**:

* SQLAlchemy not installed
* Import error in storage module

**Solution**:

Check if SQLite strategy is registered:

.. code-block:: python

    from movici_simulation_core.models.data_collector.data_collector import DataCollector
    print(DataCollector.strategies.keys())  # Should include 'sqlite'

Examples
--------

See ``examples/sqlite_storage_example.py`` for complete working examples:

* Basic usage
* Querying results
* Migrating from JSON
* Performance comparison

Testing
-------

Run tests::

    # All data collector tests (including SQLite)
    pytest tests/models/data_collector/

    # SQLite tests only
    pytest tests/models/data_collector/test_sqlite_storage.py

    # Specific test
    pytest tests/models/data_collector/test_sqlite_storage.py::test_stores_one_update_sqlite

Implementation Files
--------------------

+-----------------------------------------------------------------------------------+------------------------------------------+
| File                                                                              | Purpose                                  |
+===================================================================================+==========================================+
| ``movici_simulation_core/storage/sqlite_schema.py``                              | Database schema and SimulationDatabase   |
|                                                                                   | API                                      |
+-----------------------------------------------------------------------------------+------------------------------------------+
| ``movici_simulation_core/storage/sqlite_strategy.py``                            | SQLiteStorageStrategy implementation     |
+-----------------------------------------------------------------------------------+------------------------------------------+
| ``movici_simulation_core/models/data_collector/data_collector.py``               | Registration of SQLite strategy          |
+-----------------------------------------------------------------------------------+------------------------------------------+
| ``movici_simulation_core/json_schemas/models/data_collector.json``               | Configuration schema                     |
+-----------------------------------------------------------------------------------+------------------------------------------+
| ``tests/models/data_collector/test_sqlite_storage.py``                           | Integration tests                        |
+-----------------------------------------------------------------------------------+------------------------------------------+
| ``examples/sqlite_storage_example.py``                                           | Usage examples                           |
+-----------------------------------------------------------------------------------+------------------------------------------+

Future Enhancements
-------------------

Potential improvements for future versions:

* Compression for large arrays (zlib/lz4)
* Batch insert optimization (executemany)
* Connection pooling for multi-process scenarios
* Incremental schema migrations (Alembic)
* Read-only query mode for analysis
* Export to Parquet/Arrow for analytics
* Integration with DuckDB for OLAP queries

License
-------

Same as movici-simulation-core.
