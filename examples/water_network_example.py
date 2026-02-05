"""Example: Water Network Simulation using WNTR

This example demonstrates how to use the WNTR integration for water network
simulation. It shows two approaches:

1. Movici Simulation framework - for integration with other Movici models
2. Tape file factors - using TapePlayerModel to drive time-varying
   demand_factor and head_factor through the Movici Simulation framework

The water network is a simple example with:
- 3 junctions with demands
- 1 reservoir as water source
- 3 pipes connecting the network

.. note::
   Controls (time-based or conditional) are handled externally by the
   Movici Rules Model, not internally by this simulation model.
"""

import json
from pathlib import Path
from tempfile import mkdtemp

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.models import (
    DataCollectorModel,
    DrinkingWaterModel,
    TapePlayerModel,
)
from movici_simulation_core.models.drinking_water.attributes import (
    DrinkingWaterNetworkAttributes,
)
from movici_simulation_core.simulation import Simulation


def create_simple_water_network_data():
    """Create a simple water network in Movici JSON format.

    Network topology::

        R1 (reservoir) --P1--> J1 --P2--> J2 --P3--> J3

    Where:

    - R1: Reservoir with base head = 100m
    - J1, J2, J3: Junctions with varying elevations and demands
    - P1, P2, P3: Pipes connecting the network
    """
    return {
        "name": "simple_water_network",
        "display_name": "Simple Water Network",
        "type": "water_network",
        "version": 4,
        "general": {
            "hydraulic": {
                "headloss": "H-W",
                "viscosity": 1.0,
                "specific_gravity": 1.0,
            }
        },
        "data": {
            "water_junction_entities": {
                "id": [1, 2, 3],
                "geometry.x": [100.0, 200.0, 300.0],
                "geometry.y": [100.0, 100.0, 100.0],
                "geometry.z": [50.0, 45.0, 40.0],
                "drinking_water.base_demand": [0.01, 0.02, 0.015],
            },
            "water_reservoir_entities": {
                "id": [10],
                "geometry.x": [0.0],
                "geometry.y": [100.0],
                "drinking_water.base_head": [100.0],
            },
            "water_pipe_entities": {
                "id": [101, 102, 103],
                "topology.from_node_id": [10, 1, 2],
                "topology.to_node_id": [1, 2, 3],
                "shape.diameter": [0.3, 0.25, 0.2],
                "shape.length": [100.0, 100.0, 100.0],
                "drinking_water.roughness": [100.0, 100.0, 100.0],
            },
        },
    }


def example_simulation_framework():
    """Example using the Movici Simulation() framework.

    This approach uses the full Movici simulation framework to run the
    water network model, allowing integration with other Movici models
    and data collection.
    """
    print("\n" + "=" * 60)
    print("Water Network Simulation - Movici Simulation() Framework")
    print("=" * 60)

    # Create temporary directories
    input_dir = mkdtemp(prefix="movici-water-input-")
    output_dir = mkdtemp(prefix="movici-water-output-")

    # Save the water network dataset
    dataset = create_simple_water_network_data()
    dataset_path = Path(input_dir) / "simple_water_network.json"
    dataset_path.write_text(json.dumps(dataset, indent=2))

    print(f"\nInput directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # Create and configure the simulation
    sim = Simulation(data_dir=input_dir, storage_dir=output_dir)

    # Register water network attributes using the plugin system
    sim.use(DrinkingWaterNetworkAttributes)

    # Add the water network simulation model
    # Solver options go in the model config under "options".
    # Data options (headloss, viscosity, etc.) go in the dataset's
    # general section (see create_simple_water_network_data above).
    sim.add_model(
        "water_network",
        DrinkingWaterModel(
            {
                "dataset": "simple_water_network",
                "options": {
                    "hydraulic_timestep": 3600,
                    "hydraulic": {
                        "trials": 200,
                        "accuracy": 0.001,
                    },
                },
            }
        ),
    )

    # Add data collector to save results
    sim.add_model("data_collector", DataCollectorModel({}))

    # Run the simulation
    print("\nRunning simulation...")
    sim.run()

    print(f"\nSimulation completed! Results stored in: {output_dir}")

    # Read and display results
    results_dir = Path(output_dir)
    results_files = list(results_dir.glob("*.json"))
    if results_files:
        print("\nOutput files:")
        for f in results_files:
            print(f"  - {f.name}")


def example_save_movici_dataset():
    """Example of saving a water network dataset in Movici format.

    This dataset can be loaded by movici-viewer for visualization.
    """
    print("\n" + "=" * 60)
    print("Save Movici Dataset Example")
    print("=" * 60)

    # Create and save the water network dataset
    dataset = create_simple_water_network_data()
    output_dir = mkdtemp(prefix="movici-water-")
    dataset_path = Path(output_dir) / "simple_water_network.json"
    dataset_path.write_text(json.dumps(dataset, indent=2))

    print(f"\nDataset saved to: {dataset_path}")
    print("\nTo visualize with movici-viewer:")
    print("  1. Create a scenario file referencing this dataset")
    print(f"  2. Run: movici-viewer {output_dir}")
    print("\nDataset structure:")
    print(f"  - Name: {dataset['name']}")
    print(f"  - Type: {dataset['type']}")
    for group_name, group_data in dataset["data"].items():
        num_entities = len(group_data.get("id", []))
        print(f"  - {group_name}: {num_entities} entities")


def create_demand_tapefile():
    """Create a tape file that varies demand_factor and head_factor over time.

    The tape file targets the ``simple_water_network`` dataset and updates:

    - ``drinking_water.demand_factor`` on junctions (ids 1, 2, 3)
    - ``drinking_water.head_factor`` on the reservoir (id 10)

    Timeline (3 timesteps at 1-hour intervals)::

        t=0s:    demand_factor=1.0  head_factor=1.0  (normal operation)
        t=3600s: demand_factor=1.5  head_factor=0.95 (morning peak)
        t=7200s: demand_factor=0.5  head_factor=1.0  (low demand)
    """
    return {
        "name": "water_patterns",
        "type": "tabular",
        "format": "unstructured",
        "data": {
            "tabular_data_name": "simple_water_network",
            "time_series": [0, 3600, 7200],
            "data_series": [
                # t=0s: normal operation
                {
                    "water_junction_entities": {
                        "id": [1, 2, 3],
                        "drinking_water.demand_factor": [1.0, 1.0, 1.0],
                    },
                    "water_reservoir_entities": {
                        "id": [10],
                        "drinking_water.head_factor": [1.0],
                    },
                },
                # t=3600s: morning peak — demand up, head dips
                {
                    "water_junction_entities": {
                        "id": [1, 2, 3],
                        "drinking_water.demand_factor": [1.5, 1.5, 1.5],
                    },
                    "water_reservoir_entities": {
                        "id": [10],
                        "drinking_water.head_factor": [0.95],
                    },
                },
                # t=7200s: low demand period — demand down, head recovers
                {
                    "water_junction_entities": {
                        "id": [1, 2, 3],
                        "drinking_water.demand_factor": [0.5, 0.5, 0.5],
                    },
                    "water_reservoir_entities": {
                        "id": [10],
                        "drinking_water.head_factor": [1.0],
                    },
                },
            ],
        },
    }


def example_tape_file_factors():
    """Example using TapePlayerModel to drive time-varying demand and head.

    This approach uses the Movici Simulation framework with two models
    working together:

    1. **TapePlayerModel** — reads a tape file (tabular dataset) and publishes
       ``demand_factor`` and ``head_factor`` updates at scheduled timestamps
    2. **DrinkingWaterModel** — re-runs hydraulics whenever these
       factors change

    The tape file updates ``drinking_water.demand_factor`` on junctions and
    ``drinking_water.head_factor`` on the reservoir. The water network model
    multiplies these factors with the base values::

        effective_demand = base_demand * demand_factor
        effective_head = base_head * head_factor

    No additional attributes are needed — ``demand_factor`` and ``head_factor``
    already exist as optional attributes on junctions and reservoirs.
    """
    print("\n" + "=" * 60)
    print("Water Network Simulation - Tape File Patterns")
    print("=" * 60)

    # Create temporary directories
    input_dir = mkdtemp(prefix="movici-water-tape-input-")
    output_dir = mkdtemp(prefix="movici-water-tape-output-")

    # Save the water network dataset
    dataset = create_simple_water_network_data()
    dataset_path = Path(input_dir) / "simple_water_network.json"
    dataset_path.write_text(json.dumps(dataset, indent=2))

    # Save the tape file (tabular dataset with time-varying factors)
    tapefile = create_demand_tapefile()
    tapefile_path = Path(input_dir) / "water_patterns.json"
    tapefile_path.write_text(json.dumps(tapefile, indent=2))

    print(f"\nInput directory: {input_dir}")
    print(f"Output directory: {output_dir}")
    print("\nTape file schedule:")
    print("  t=0s:    demand_factor=1.0  head_factor=1.0  (normal)")
    print("  t=3600s: demand_factor=1.5  head_factor=0.95 (peak)")
    print("  t=7200s: demand_factor=0.5  head_factor=1.0  (low)")

    # Create and configure the simulation
    sim = Simulation(data_dir=input_dir, storage_dir=output_dir)
    sim.use(DrinkingWaterNetworkAttributes)

    # TapePlayerModel reads the tape file and publishes demand_factor
    # and head_factor updates at scheduled timestamps.
    sim.add_model(
        "tape_player",
        TapePlayerModel({"tabular": ["water_patterns"]}),
    )

    # DrinkingWaterModel picks up factor changes and re-runs
    # hydraulics. The model multiplies base_demand * demand_factor and
    # base_head * head_factor internally.
    sim.add_model(
        "water_network",
        DrinkingWaterModel(
            {
                "dataset": "simple_water_network",
                "options": {
                    "hydraulic_timestep": 3600,
                },
            }
        ),
    )

    # DataCollectorModel saves results at each timestep
    sim.add_model("data_collector", DataCollectorModel({}))

    # Set timeline: 2 hours, time_scale=1 (1 timestamp unit = 1 second)
    sim.set_timeline_info(TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200))

    # Run the simulation
    print("\nRunning simulation with tape-driven patterns...")
    sim.run()

    print(f"\nSimulation completed! Results stored in: {output_dir}")

    # List output files
    results_dir = Path(output_dir)
    results_files = sorted(results_dir.glob("*.json"))
    if results_files:
        print("\nOutput files:")
        for f in results_files:
            print(f"  - {f.name}")


def main():
    """Run water network examples."""
    print("\n" + "=" * 60)
    print("WNTR Water Network Simulation Examples")
    print("=" * 60)

    # Run the Simulation() framework example
    example_simulation_framework()

    # Run the tape file + Simulation framework example
    example_tape_file_factors()

    # Save a Movici dataset for visualization
    example_save_movici_dataset()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
