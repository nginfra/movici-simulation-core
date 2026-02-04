.. |required| replace:: (**required**)

Data Collector
==============

The data collector model (``"data_collector"``) subscribes to simulation updates
and stores them for later analysis. It supports file-based (JSON) and SQLite
storage backends.

Use cases include:

* Recording simulation results for post-processing
* Debugging model interactions by capturing all updates
* Creating datasets for visualization or analysis tools

How It Works
------------

1. The data collector subscribes to attribute updates from other models
2. When updates are received, they are queued for storage
3. Updates are written using the configured storage strategy
4. If ``aggregate_updates`` is enabled, updates are batched per timestamp

Example Configuration
---------------------

Collect all simulation updates:

.. code-block:: json

    {
        "name": "data_collector",
        "type": "data_collector",
        "gather_filter": "*",
        "aggregate_updates": true
    }

Collect specific datasets:

.. code-block:: json

    {
        "name": "road_data_collector",
        "type": "data_collector",
        "gather_filter": {
            "road_network": null
        }
    }

Storage Strategies
------------------

File Storage
------------

Writes each update as a separate JSON file in the configured directory.
File naming pattern: ``t{timestamp}_{iteration}_{dataset_name}.json``

SQLite Storage
--------------

Stores updates in a SQLite database, which is more efficient for large
simulations with many updates. Requires the ``database_path`` option.

**Priority**: ``database_path`` > ``storage_dir`` (model config) > ``storage_dir`` (settings)

Config Schema Reference
-----------------------

DataCollectorConfig
^^^^^^^^^^^^^^^^^^^

| ``type``: ``object``

``properties``:
  | ``storage``: ``string`` Storage method: ``"file"`` or ``"sqlite"`` (overrides settings)
  | ``storage_dir``: ``string`` Directory for file-based storage (overrides settings)
  | ``database_path``: ``string`` Full path to SQLite database file (for sqlite storage)
  | ``gather_filter``: ``object`` | ``null`` | ``"*"`` Subscribe filter for data collection; use ``"*"`` to collect all updates, or specify dataset/attribute filters
  | ``aggregate_updates``: ``boolean`` Batch updates per timestamp (default: ``false``)
