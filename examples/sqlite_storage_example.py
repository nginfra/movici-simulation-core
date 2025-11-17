"""
Example demonstrating SQLite storage for DataCollector model.

This example shows how to configure and use SQLite storage instead of
individual JSON files for storing simulation intermediate data.
"""

import time
from pathlib import Path

from movici_simulation_core.postprocessing.results import SimulationResults
from movici_simulation_core.settings import Settings
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.storage.sqlite_schema import SimulationDatabase


def example_sqlite_storage():
    """
    Example: Using SQLite storage with DataCollector
    """
    # Define paths
    data_dir = Path("./simulation_data")
    results_dir = Path("./simulation_results")
    results_dir.mkdir(exist_ok=True)

    # Create simulation with SQLite storage
    settings = Settings(
        storage="sqlite",  # Use SQLite instead of "disk" (JSON files)
        storage_dir=results_dir,
    )

    sim = Simulation(data_dir=data_dir, settings=settings)

    # Add data collector with SQLite configuration
    sim.add_model(
        "data_collector",
        {
            "gather_filter": "*",  # Collect all updates
            "aggregate_updates": False,  # Store each update separately
            # Option 1: Specify explicit database path
            "database_path": str(results_dir / "simulation.db"),
            # Option 2: Use storage_dir (creates simulation_results.db)
            # "storage_dir": str(results_dir),
        },
    )

    # Add other models...
    # sim.add_model("some_model", {...})

    # Run simulation
    sim.run()

    # Results are now in SQLite database instead of JSON files!
    print(f"Results stored in: {results_dir / 'simulation.db'}")


def example_querying_results():
    """
    Example: Querying results from SQLite database
    """
    # Open the database
    db = SimulationDatabase("./simulation_results/simulation.db")

    # Get all datasets
    datasets = db.get_datasets()
    print(f"Datasets: {datasets}")

    # Get timestamps for a dataset
    if datasets:
        dataset_name = datasets[0]
        timestamps = db.get_timestamps(dataset_name)
        print(f"Timestamps for {dataset_name}: {timestamps}")

        # Get all updates for a dataset
        updates = db.get_dataset_updates(dataset_name)
        print(f"Number of updates: {len(updates)}")

        # Inspect first update
        if updates:
            first_update = updates[0]
            print(f"First update timestamp: {first_update['timestamp']}")
            print(f"First update iteration: {first_update['iteration']}")
            print(f"Entity groups: {list(first_update.keys())}")


def example_migration_json_to_sqlite():
    """
    Example: Migrating existing JSON results to SQLite
    """
    # Load existing JSON results
    json_dir = Path("./results_json")
    json_results = SimulationResults(
        init_data_dir=json_dir / "init", updates_dir=json_dir / "updates"
    )

    # Create SQLite database
    db = SimulationDatabase("./results_sqlite/migrated.db")

    # Migrate each dataset
    for dataset_name in json_results.get_datasets():
        dataset = json_results.get_dataset(dataset_name)

        # Store each update
        for update in dataset.updates:
            # Extract entity data (exclude timestamp/iteration)
            entity_data = {k: v for k, v in update.items() if k not in ["timestamp", "iteration"]}

            db.store_update(
                timestamp=update["timestamp"],
                iteration=update["iteration"],
                dataset_name=dataset_name,
                entity_data=entity_data,
            )

    print(f"Migration complete. Total updates: {db.get_update_count()}")


def example_performance_comparison():
    """
    Example: Demonstrating performance benefits
    """
    # === SQLite Performance ===
    db = SimulationDatabase(":memory:")  # In-memory for speed

    # Write 1000 updates
    start = time.time()
    for i in range(1000):
        db.store_update(
            timestamp=i,
            iteration=0,
            dataset_name="dataset",
            entity_data={"entities": {"id": {"data": list(range(100))}}},
        )
    write_time = time.time() - start
    print(f"SQLite: Wrote 1000 updates in {write_time:.2f}s")

    # Read all updates
    start = time.time()
    updates = db.get_dataset_updates("dataset")
    read_time = time.time() - start
    print(f"SQLite: Read {len(updates)} updates in {read_time:.3f}s")

    # Query specific timestamps
    start = time.time()
    timestamps = db.get_timestamps("dataset")
    query_time = time.time() - start
    print(f"SQLite: Queried {len(timestamps)} timestamps in {query_time:.3f}s")

    # JSON would require:
    # - Write: 1000 individual file writes (slower)
    # - Read: glob + 1000 file reads + JSON parsing (much slower)
    # - Query: glob + regex matching (slower)


if __name__ == "__main__":
    print("=" * 60)
    print("SQLite Storage Examples")
    print("=" * 60)

    print("\n1. Performance Comparison:")
    print("-" * 60)
    example_performance_comparison()

    print("\n2. Configuration Comparison:")
    print("-" * 60)
    example_comparison_json_vs_sqlite()

    print("\n" + "=" * 60)
    print("To run a full simulation:")
    print("  - Use example_sqlite_storage()")
    print("To query results:")
    print("  - Use example_querying_results()")
    print("To migrate existing data:")
    print("  - Use example_migration_json_to_sqlite()")
    print("=" * 60)
