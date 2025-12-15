"""Example: Water Network Simulation using WNTR

This example demonstrates how to use the WNTR integration for water network
simulation. It shows four approaches:

1. Direct NetworkWrapper usage - for standalone hydraulic simulations
2. Movici Simulation framework - for integration with other Movici models
3. Movici Simulation with controls - time-based control rules
4. Movici Simulation with INP file - load EPANET network files

The water network is a simple example with:
- 3 junctions with demands
- 1 reservoir as water source
- 3 pipes connecting the network
"""

import json
import shutil
from pathlib import Path
from tempfile import mkdtemp

import numpy as np

from movici_simulation_core.integrations.wntr import (
    JunctionCollection,
    NetworkWrapper,
    PipeCollection,
    ReservoirCollection,
)
from movici_simulation_core.models import DataCollectorModel, WaterNetworkSimulationModel
from movici_simulation_core.models.water_network_simulation.attributes import (
    DrinkingWaterNetworkAttributes,
)
from movici_simulation_core.simulation import Simulation


def create_simple_water_network_data():
    """Create a simple water network in Movici JSON format.

    Network topology:
        R1 (reservoir) --P1--> J1 --P2--> J2 --P3--> J3

    Where:
    - R1: Reservoir with head = 100m
    - J1, J2, J3: Junctions with varying elevations and demands
    - P1, P2, P3: Pipes connecting the network
    """
    return {
        "name": "simple_water_network",
        "display_name": "Simple Water Network",
        "type": "water_network",
        "version": 4,
        "data": {
            "water_junction_entities": {
                "id": [1, 2, 3],
                "geometry.x": [100.0, 200.0, 300.0],
                "geometry.y": [100.0, 100.0, 100.0],
                "water.elevation": [50.0, 45.0, 40.0],
                "water.base_demand": [0.01, 0.02, 0.015],
            },
            "water_reservoir_entities": {
                "id": [10],
                "geometry.x": [0.0],
                "geometry.y": [100.0],
                "water.head": [100.0],
            },
            "water_pipe_entities": {
                "id": [101, 102, 103],
                "topology.from_node_id": [10, 1, 2],
                "topology.to_node_id": [1, 2, 3],
                "geometry.linestring_2d": [
                    [[0.0, 100.0], [100.0, 100.0]],
                    [[100.0, 100.0], [200.0, 100.0]],
                    [[200.0, 100.0], [300.0, 100.0]],
                ],
                "water.diameter": [0.3, 0.25, 0.2],
                "water.roughness": [100.0, 100.0, 100.0],
                "water.minor_loss": [0.0, 0.0, 0.0],
                "water.initial_status": [1, 1, 1],
            },
        },
    }


def example_direct_wntr():
    """Example using NetworkWrapper directly with Movici data format.

    This approach builds a WNTR network from Movici-formatted data
    and runs a hydraulic simulation.
    """
    print("=" * 60)
    print("Water Network Simulation - Direct NetworkWrapper")
    print("=" * 60)

    # Get the Movici dataset
    dataset = create_simple_water_network_data()
    data = dataset["data"]

    # Create network wrapper
    network = NetworkWrapper(mode="movici_network")

    # Build junction collection from Movici data
    junction_data = data["water_junction_entities"]
    junctions = JunctionCollection(
        node_names=[f"J{i}" for i in junction_data["id"]],
        elevations=np.array(junction_data["water.elevation"]),
        base_demands=np.array(junction_data["water.base_demand"]),
        coordinates=np.column_stack([junction_data["geometry.x"], junction_data["geometry.y"]]),
    )
    network.add_junctions(junctions)

    # Build reservoir collection
    reservoir_data = data["water_reservoir_entities"]
    reservoirs = ReservoirCollection(
        node_names=[f"R{i}" for i in reservoir_data["id"]],
        heads=np.array(reservoir_data["water.head"]),
        coordinates=np.column_stack([reservoir_data["geometry.x"], reservoir_data["geometry.y"]]),
    )
    network.add_reservoirs(reservoirs)

    # Build pipe collection
    pipe_data = data["water_pipe_entities"]
    # Calculate pipe lengths from geometry
    lengths = []
    for geom in pipe_data["geometry.linestring_2d"]:
        dx = geom[1][0] - geom[0][0]
        dy = geom[1][1] - geom[0][1]
        lengths.append(np.sqrt(dx**2 + dy**2))

    # Map node IDs to names
    node_id_to_name = {}
    for nid in junction_data["id"]:
        node_id_to_name[nid] = f"J{nid}"
    for nid in reservoir_data["id"]:
        node_id_to_name[nid] = f"R{nid}"

    pipes = PipeCollection(
        link_names=[f"P{i}" for i in pipe_data["id"]],
        from_nodes=[node_id_to_name[nid] for nid in pipe_data["topology.from_node_id"]],
        to_nodes=[node_id_to_name[nid] for nid in pipe_data["topology.to_node_id"]],
        lengths=np.array(lengths),
        diameters=np.array(pipe_data["water.diameter"]),
        roughnesses=np.array(pipe_data["water.roughness"]),
        minor_losses=np.array(pipe_data["water.minor_loss"]),
        statuses=["OPEN" if s == 1 else "CLOSED" for s in pipe_data["water.initial_status"]],
    )
    network.add_pipes(pipes)

    # Print network summary
    print("\nNetwork Summary:")
    summary = network.get_network_summary()
    for key, value in summary.items():
        print(f"  {key}: {value}")

    # Run simulation
    print("\nRunning hydraulic simulation...")
    results = network.run_simulation(
        duration=3600,  # 1 hour
        hydraulic_timestep=3600,
    )

    # Display results
    print("\nSimulation Results:")
    print("\nJunctions:")
    print(f"  {'Node':<10} {'Pressure (m)':<15} {'Head (m)':<15} {'Demand (m³/s)':<15}")
    print("  " + "-" * 55)

    for i, name in enumerate(results.node_names):
        if name.startswith("J"):
            pressure = results.node_pressures[i]
            head = results.node_heads[i]
            demand = results.node_demands[i]
            print(f"  {name:<10} {pressure:>14.2f} {head:>14.2f} {demand:>14.6f}")

    print("\nPipes:")
    print(f"  {'Link':<10} {'Flow (m³/s)':<15} {'Velocity (m/s)':<15} {'Headloss (m)':<15}")
    print("  " + "-" * 55)

    for i, name in enumerate(results.link_names):
        if name.startswith("P"):
            flow = results.link_flows[i]
            velocity = results.link_velocities[i]
            headloss = results.link_headlosses[i]
            print(f"  {name:<10} {flow:>14.6f} {velocity:>14.4f} {headloss:>14.4f}")

    print("\nSimulation completed successfully!")
    network.close()


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
    sim.add_model(
        "water_network",
        WaterNetworkSimulationModel(
            {
                "dataset": "simple_water_network",
                "mode": "movici_network",
                "entity_groups": ["junctions", "pipes", "reservoirs"],
                "simulation_duration": 3600,  # 1 hour
                "hydraulic_timestep": 3600,
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


def example_simulation_with_controls():
    """Example using Simulation() with control rules.

    This shows how to configure time-based and conditional controls
    within the Simulation() framework.
    """
    print("\n" + "=" * 60)
    print("Water Network Simulation with Controls")
    print("=" * 60)

    # Create temporary directories
    input_dir = mkdtemp(prefix="movici-water-ctrl-input-")
    output_dir = mkdtemp(prefix="movici-water-ctrl-output-")

    # Save the water network dataset
    dataset = create_simple_water_network_data()
    dataset_path = Path(input_dir) / "simple_water_network.json"
    dataset_path.write_text(json.dumps(dataset, indent=2))

    # Create and configure the simulation with controls
    sim = Simulation(data_dir=input_dir, storage_dir=output_dir)
    sim.use(DrinkingWaterNetworkAttributes)

    # Add the water network simulation model with control rules
    sim.add_model(
        "water_network",
        WaterNetworkSimulationModel(
            {
                "dataset": "simple_water_network",
                "mode": "movici_network",
                "entity_groups": ["junctions", "pipes", "reservoirs"],
                "simulation_duration": 7200,  # 2 hours
                "hydraulic_timestep": 3600,
                # Control rules configuration
                # Note: WNTR names use format 'l{id}' for links, 'n{id}' for nodes
                "control_rules": [
                    {
                        "type": "time",
                        "name": "close_pipe_at_1h",
                        "target": "l103",  # Close pipe with ID 103 after 1 hour
                        "attribute": "status",
                        "value": "CLOSED",
                        "time": 3600,
                        "time_type": "sim_time",
                    }
                ],
            }
        ),
    )

    sim.add_model("data_collector", DataCollectorModel({}))

    print("\nRunning simulation with controls...")
    print("  - Pipe l103 (Movici ID 103) will be closed at t=3600s")
    sim.run()

    print(f"\nSimulation completed! Results stored in: {output_dir}")


def example_simulation_with_inp_file():
    """Example using Simulation() with an EPANET INP file.

    This demonstrates how to load an existing EPANET network file
    and run a hydraulic simulation using the Movici framework.

    The INP file format is the standard format for EPANET models,
    widely used in the water industry. This allows importing existing
    network models directly.
    """
    print("\n" + "=" * 60)
    print("Water Network Simulation - INP File Loading")
    print("=" * 60)

    # Use the example INP file included in the repo
    # In practice, this could be any valid EPANET INP file
    examples_dir = Path(__file__).parent
    inp_file = examples_dir / "simple_water_network.inp"

    if not inp_file.exists():
        print(f"\nINP file not found: {inp_file}")
        print("Skipping INP file example.")
        return

    print(f"\nLoading INP file: {inp_file.name}")

    # Create temporary directories
    input_dir = mkdtemp(prefix="movici-water-inp-input-")
    output_dir = mkdtemp(prefix="movici-water-inp-output-")

    # Copy INP file to input directory (required for init_data_handler)
    shutil.copy(inp_file, Path(input_dir) / inp_file.name)

    print(f"Input directory: {input_dir}")
    print(f"Output directory: {output_dir}")

    # Create and configure the simulation
    sim = Simulation(data_dir=input_dir, storage_dir=output_dir)

    # Register water network attributes
    sim.use(DrinkingWaterNetworkAttributes)

    # Add the water network simulation model in inp_file mode
    sim.add_model(
        "water_network",
        WaterNetworkSimulationModel(
            {
                "mode": "inp_file",
                "inp_file": inp_file.name,  # Reference the INP file
                "dataset": "water_network_from_inp",  # Output dataset name
            }
        ),
    )

    # Add data collector to save results
    sim.add_model("data_collector", DataCollectorModel({}))

    print("\nRunning simulation from INP file...")
    print("  Network contains:")
    print("    - Junctions: J1, J2, J3")
    print("    - Reservoir: R1")
    print("    - Tank: T1")
    print("    - Pipes: P1, P2, P3, P4")
    print("    - Pump: PU1")
    print("  Duration: 24 hours")
    print("  Hydraulic timestep: 1 hour")

    sim.run()

    print(f"\nSimulation completed! Results stored in: {output_dir}")

    # List output files
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


def main():
    """Run water network examples."""
    print("\n" + "=" * 60)
    print("WNTR Water Network Simulation Examples")
    print("=" * 60)

    # Run the direct NetworkWrapper example
    example_direct_wntr()

    # Run the Simulation() framework example
    example_simulation_framework()

    # Run the Simulation() with controls example
    example_simulation_with_controls()

    # Run the Simulation() with INP file example
    example_simulation_with_inp_file()

    # Save a Movici dataset for visualization
    example_save_movici_dataset()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
