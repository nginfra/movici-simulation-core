.. include:: ../include/glossary.rst
.. include:: ../include/code.rst

Storage
=======

By default, a [Simulation] doesn't persist any of the results. This must be explicitly enabled by
adding a ``DataCollector`` model to the [Scenario]. When adding a data collector, the simulation
results are by default stored as files in the ``Settings.storage_dir`` directory. However, it 
is also possible to store the results in a :ref:`SQLite database <sqlite-storage>`. This can be
done by setting ``Settings.storage`` to ``"sqlite"``


.. _sqlite-storage:

SQLite storage
--------------

In order to enable sqlite storage, you must first install the required dependencies by installing
the correct package extras::

    pip install movici-simulation-core[sqlite]



Usage
#####


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

This creates a simulation results database in  ``./results``. The file has a ``simulation_results``
prefix and contains a timestamp when the simulation was run.

Option 2: Model Configuration
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    sim.add_model("data_collector", {
        "gather_filter": "*",
        "database_path": "./results/my_simulation.db"  # Explicit path
    })

This will store the results in the specified database file. 

.. warning:: if the database already exists, this will overwrite any data inside this file


Querying Results
################

Using SimulationDatabase API
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

    # Open database
    with SimulationDatabase("simulation.db") as db:

      # Get all datasets
      datasets = db.get_datasets()
      print(datasets) # ['transport_network', 'water_network', ...]

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

.. note:: This example assumes an existing simulation.db file

Direct SQL Queries (Advanced)
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from sqlalchemy import create_engine

    engine = create_engine('sqlite:///simulation.db')

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

.. note:: This example assumes an existing simulation.db file

Migration from JSON
###################

Migrating Existing Results
^^^^^^^^^^^^^^^^^^^^^^^^^^

.. code-block:: python

    from pathlib import Path
    from movici_simulation_core.postprocessing.results import SimulationResults
    from movici_simulation_core.storage.sqlite_schema import SimulationDatabase

    # Load JSON results
    json_results = SimulationResults(
        init_data_dir=Path("./init_data"),
        updates_dir=Path("./updates")
    )


    # Create SQLite database
    db = SimulationDatabase("./new_results/migrated.db")

    # Migrate
    for dataset_name in json_results.datasets.keys():
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


.. note::
   This example assumes exising initial datasets in the ``./init_data`` directory, and simulation
   results (as json files) in the ``./updates/`` directory

Examples
########

See ``examples/sqlite_storage_example.py`` for more examples

