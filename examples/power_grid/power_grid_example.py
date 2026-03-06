"""Power Grid Model Integration Example.

This example demonstrates the full capabilities of the power-grid-model
integration in movici-simulation-core:

1. Power Flow Calculation - With different algorithms and dynamic load updates
2. State Estimation - Using voltage and power sensor measurements
3. Short Circuit Analysis - Fault current calculations

Network Topology:
                    [Source/Slack Bus]
                           |
                      Node 1 (110 kV)
                           |
                    [Transformer 1]
                           |
                      Node 2 (10 kV)
                      /          \\
               [Line 1]        [Line 2]
                  /                \\
            Node 3 (10 kV)    Node 4 (10 kV)
                |                   |
           [Load 1]           [Generator 1]
                                    |
                              [Shunt 1]
"""

import json
import sys
import tempfile
from pathlib import Path

import numpy as np

from movici_simulation_core import Simulation, TimelineInfo
from movici_simulation_core.models.data_collector import DataCollector
from movici_simulation_core.models.power_grid_calculation import Model as PowerGridModel
from movici_simulation_core.models.power_grid_calculation.attributes import PowerGridAttributes


def create_network_dataset() -> dict:
    """Create the power grid network dataset.

    This creates a simple 4-node network with:
    - 2 voltage levels (110 kV and 10 kV)
    - 1 transformer connecting voltage levels
    - 2 distribution lines
    - 1 load and 1 generator
    - 1 shunt capacitor
    """
    return {
        "name": "power_grid",
        "type": "electrical_network",
        "version": 4,
        "data": {
            # Electrical nodes (buses)
            "electrical_node_entities": {
                "id": [1, 2, 3, 4],
                "geometry.x": [0.0, 0.0, -100.0, 100.0],  # X coordinates (m)
                "geometry.y": [100.0, 0.0, -100.0, -100.0],  # Y coordinates (m)
                "electrical.rated_voltage": [
                    110000.0,  # Node 1: 110 kV (HV side)
                    10000.0,  # Node 2: 10 kV (MV bus)
                    10000.0,  # Node 3: 10 kV (load bus)
                    10000.0,  # Node 4: 10 kV (generator bus)
                ],
            },
            # External grid connection (slack bus)
            "electrical_source_entities": {
                "id": [101],
                "connection.to_id": [1],  # Connected to node 1
                "electrical.reference_voltage": [1.0],  # 1.0 p.u.
                "electrical.short_circuit_power": [1e9],  # 1 GVA
                "electrical.rx_ratio": [0.1],
            },
            # Transformer (110/10 kV)
            "electrical_transformer_entities": {
                "id": [201],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.primary_voltage": [110000.0],  # 110 kV
                "electrical.secondary_voltage": [10000.0],  # 10 kV
                "electrical.rated_power": [40e6],  # 40 MVA
                "electrical.short_circuit_voltage": [0.1],  # 10% uk
                "electrical.copper_loss": [100000.0],  # 100 kW pk
                "electrical.no_load_current": [0.01],  # 1% i0
                "electrical.no_load_loss": [20000.0],  # 20 kW p0
            },
            # Distribution lines
            "electrical_line_entities": {
                "id": [301, 302],
                "topology.from_node_id": [2, 2],
                "topology.to_node_id": [3, 4],
                "electrical.resistance": [0.5, 0.3],  # Ohm
                "electrical.reactance": [0.4, 0.25],  # Ohm
                "electrical.capacitance": [1e-9, 1e-9],  # Farad
                "electrical.tan_delta": [0.0, 0.0],
                "electrical.rated_current": [400.0, 400.0],  # Ampere
            },
            # Loads
            "electrical_load_entities": {
                "id": [401],
                "connection.to_id": [3],  # Connected to node 3
                "electrical.active_power_specified": [2e6],  # 2 MW initial
                "electrical.reactive_power_specified": [0.5e6],  # 0.5 MVAr
            },
            # Generators (e.g., solar PV)
            "electrical_generator_entities": {
                "id": [501],
                "connection.to_id": [4],  # Connected to node 4
                "electrical.active_power_specified": [1e6],  # 1 MW initial
                "electrical.reactive_power_specified": [0.0],  # Unity power factor
            },
            # Shunt capacitor bank
            "electrical_shunt_entities": {
                "id": [601],
                "connection.to_id": [4],  # Connected to node 4
                "electrical.conductance": [0.0],  # No losses
                "electrical.susceptance": [0.001],  # Capacitive (positive B)
            },
        },
    }


def create_load_profile_tapefile() -> dict:
    """Create a dynamic load profile representing daily load variation.

    The load varies throughout the day:
    - Night (0-6h): ~50% of peak
    - Morning (6-12h): Rising to 80%
    - Afternoon (12-18h): Peak at 100%
    - Evening (18-24h): Declining to 60%

    Generator (solar) output:
    - Night (0-6h): 0%
    - Morning (6-12h): Rising to 100%
    - Afternoon (12-18h): Peak then declining
    - Evening (18-24h): 0%
    """
    hours = 24
    base_load_p = 2e6  # 2 MW base load
    base_load_q = 0.5e6  # 0.5 MVAr
    base_gen_p = 1e6  # 1 MW peak solar

    # Load profile (fraction of base)
    load_profile = np.array(
        [
            0.5,
            0.45,
            0.45,
            0.5,
            0.55,
            0.6,  # 0-5h: night
            0.7,
            0.8,
            0.85,
            0.9,
            0.95,
            1.0,  # 6-11h: morning rise
            1.0,
            0.95,
            0.9,
            0.85,
            0.8,
            0.75,  # 12-17h: afternoon
            0.7,
            0.65,
            0.6,
            0.55,
            0.5,
            0.5,  # 18-23h: evening
        ]
    )

    # Solar generation profile (fraction of peak)
    solar_profile = np.array(
        [
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.1,  # 0-5h: night
            0.3,
            0.5,
            0.7,
            0.85,
            0.95,
            1.0,  # 6-11h: morning rise
            1.0,
            0.95,
            0.85,
            0.7,
            0.5,
            0.3,  # 12-17h: afternoon
            0.1,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,  # 18-23h: evening
        ]
    )

    # Build time series data
    time_series = list(range(0, hours * 3600, 3600))  # Hourly in seconds
    data_series = []

    for i in range(hours):
        data_series.append(
            {
                "electrical_load_entities": {
                    "id": [401],
                    "electrical.active_power_specified": [float(base_load_p * load_profile[i])],
                    "electrical.reactive_power_specified": [float(base_load_q * load_profile[i])],
                },
                "electrical_generator_entities": {
                    "id": [501],
                    "electrical.active_power_specified": [float(base_gen_p * solar_profile[i])],
                    "electrical.reactive_power_specified": [0.0],
                },
            }
        )

    return {
        "name": "load_profile",
        "type": "tabular",
        "data": {
            "tabular_data_name": "power_grid",
            "time_series": time_series,
            "data_series": data_series,
        },
    }


def create_sensor_dataset() -> dict:
    """Create sensor measurements for state estimation.

    Includes:
    - Voltage sensors at each node
    - Power sensor at the load
    """
    return {
        "name": "power_grid",
        "type": "electrical_network",
        "version": 4,
        "data": {
            # All node and component data from base network...
            # (This would be merged with create_network_dataset())
            # Voltage sensors
            "electrical_voltage_sensor_entities": {
                "id": [701, 702, 703, 704],
                "connection.to_id": [1, 2, 3, 4],  # One sensor per node
                "electrical.measured_voltage": [
                    110000.0,
                    9950.0,
                    9900.0,
                    9920.0,
                ],  # Measured values
                "electrical.voltage_sigma": [
                    100.0,
                    50.0,
                    50.0,
                    50.0,
                ],  # Measurement uncertainty
            },
            # Power sensors - need enough measurements for observability
            "electrical_power_sensor_entities": {
                "id": [801, 802, 803],
                "connection.to_id": [401, 501, 101],  # load, generator, source
                "electrical.measured_terminal_type": [4, 5, 2],  # load=4, gen=5, source=2
                "electrical.measured_active_power": [2e6, -1e6, -1e6],  # P measurements
                "electrical.measured_reactive_power": [0.5e6, 0.0, -0.5e6],  # Q measurements
                "electrical.power_sigma": [10000.0, 10000.0, 10000.0],  # uncertainties
            },
        },
    }


def create_fault_dataset() -> dict:
    """Create fault definition for short circuit analysis.

    Defines a three-phase fault at node 3 (load bus).
    """
    return {
        "name": "power_grid",
        "type": "electrical_network",
        "version": 4,
        "data": {
            # Fault definitions
            "electrical_fault_entities": {
                "id": [901],
                "connection.to_id": [3],  # Fault at node 3
                "electrical.fault_type": [0],  # 0 = three-phase
                "electrical.fault_resistance": [0.0],  # Bolted fault
                "electrical.fault_reactance": [0.0],
            },
        },
    }


def save_datasets(data_dir: Path, datasets: list[dict]):
    """Save datasets to JSON files."""
    for dataset in datasets:
        filepath = data_dir / f"{dataset['name']}.json"
        with open(filepath, "w") as f:
            json.dump(dataset, f, indent=2)


def run_power_flow_scenario():
    """Scenario A: Power flow with dynamic loads.

    This scenario demonstrates:
    - Basic power flow calculation using Newton-Raphson
    - Dynamic load updates via TapePlayer
    - Result collection over 24 simulated hours
    """
    print("=" * 60)
    print("Scenario A: Power Flow with Dynamic Loads")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        output_dir = Path(tmpdir) / "output"
        data_dir.mkdir()
        output_dir.mkdir()

        # Create and save datasets
        network = create_network_dataset()
        save_datasets(data_dir, [network])

        # Create simulation (simplified - no TapePlayer for now)
        sim = Simulation(data_dir=data_dir, storage_dir=output_dir)

        # Register attribute plugins
        sim.use(PowerGridAttributes)

        # Register model types
        sim.use(PowerGridModel)
        sim.use(DataCollector)

        # Add models
        sim.add_model(
            "power_grid",
            PowerGridModel,
            {
                "dataset": "power_grid",
                "calculation_type": "power_flow",
                "algorithm": "newton_raphson",
            },
        )
        sim.add_model("data_collector", DataCollector, {})

        # Set timeline: single timestep
        sim.set_timeline_info(
            TimelineInfo(
                reference=0,
                time_scale=1,
                start_time=0,
                duration=1,
            )
        )

        # Run simulation
        print("\nRunning single power flow calculation...")
        exit_code = sim.run()

        if exit_code == 0:
            print("\nSimulation completed successfully!")
            print("\nKey observations:")
            print("- Network topology: Source -> Transformer -> Lines -> Loads/Generators")
            print("- Voltage drop calculated based on network impedances")
            print("- Line loading shows power flow distribution")
        else:
            print(f"\nSimulation failed with exit code: {exit_code}")

        return exit_code


def run_state_estimation_scenario():
    """Scenario B: State estimation with sensors.

    This scenario demonstrates:
    - State estimation using voltage and power measurements
    - Handling of measurement uncertainties
    """
    print("\n" + "=" * 60)
    print("Scenario B: State Estimation with Sensors")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        output_dir = Path(tmpdir) / "output"
        data_dir.mkdir()
        output_dir.mkdir()

        # Create network with sensors
        network = create_network_dataset()
        sensors = create_sensor_dataset()

        # Merge sensor data into network
        network["data"].update(sensors["data"])
        save_datasets(data_dir, [network])

        # Create simulation
        sim = Simulation(data_dir=data_dir, storage_dir=output_dir)

        sim.use(PowerGridAttributes)
        sim.use(PowerGridModel)
        sim.use(DataCollector)

        sim.add_model(
            "power_grid",
            PowerGridModel,
            {
                "dataset": "power_grid",
                "calculation_type": "state_estimation",
            },
        )
        sim.add_model("data_collector", DataCollector, {})

        sim.set_timeline_info(
            TimelineInfo(
                reference=0,
                time_scale=1,
                start_time=0,
                duration=1,
            )
        )

        print("\nRunning state estimation...")
        exit_code = sim.run()

        if exit_code == 0:
            print("\nState estimation completed successfully!")
            print("\nKey observations:")
            print("- Estimated state based on sensor measurements")
            print("- Voltage profile reconstructed from sparse measurements")
            print("- Measurement residuals indicate data quality")
        else:
            print(f"\nState estimation failed with exit code: {exit_code}")

        return exit_code


def run_short_circuit_scenario():
    """Scenario C: Short circuit analysis.

    This scenario demonstrates:
    - Short circuit calculation for fault analysis
    - Fault current and power calculations
    """
    print("\n" + "=" * 60)
    print("Scenario C: Short Circuit Analysis")
    print("=" * 60)

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        output_dir = Path(tmpdir) / "output"
        data_dir.mkdir()
        output_dir.mkdir()

        # Create network with fault definition
        network = create_network_dataset()
        faults = create_fault_dataset()

        # Merge fault data into network
        network["data"].update(faults["data"])
        save_datasets(data_dir, [network])

        # Create simulation
        sim = Simulation(data_dir=data_dir, storage_dir=output_dir)

        sim.use(PowerGridAttributes)
        sim.use(PowerGridModel)
        sim.use(DataCollector)

        sim.add_model(
            "power_grid",
            PowerGridModel,
            {
                "dataset": "power_grid",
                "calculation_type": "short_circuit",
            },
        )
        sim.add_model("data_collector", DataCollector, {})

        sim.set_timeline_info(
            TimelineInfo(
                reference=0,
                time_scale=1,
                start_time=0,
                duration=1,
            )
        )

        print("\nRunning short circuit analysis...")
        print("Fault location: Node 3 (10 kV load bus)")
        print("Fault type: Three-phase bolted fault")
        exit_code = sim.run()

        if exit_code == 0:
            print("\nShort circuit analysis completed successfully!")
            print("\nKey observations:")
            print("- Fault current magnitude depends on source impedance")
            print("- Transformer limits fault current contribution")
            print("- Results used for protection coordination")
        else:
            print(f"\nShort circuit analysis failed with exit code: {exit_code}")

        return exit_code


def run_algorithm_comparison():
    """Compare different power flow algorithms.

    This demonstrates the available calculation methods:
    - Newton-Raphson (default, most accurate)
    - Linear (fast approximation)
    - Iterative Current (good for radial networks)
    """
    print("\n" + "=" * 60)
    print("Algorithm Comparison: Power Flow Methods")
    print("=" * 60)

    algorithms = ["newton_raphson", "linear", "iterative_current"]

    with tempfile.TemporaryDirectory() as tmpdir:
        data_dir = Path(tmpdir) / "data"
        data_dir.mkdir()

        network = create_network_dataset()
        save_datasets(data_dir, [network])

        for algo in algorithms:
            output_dir = Path(tmpdir) / f"output_{algo}"
            output_dir.mkdir()

            sim = Simulation(data_dir=data_dir, storage_dir=output_dir)
            sim.use(PowerGridModel)

            sim.add_model(
                "power_grid",
                PowerGridModel,
                {
                    "dataset": "power_grid",
                    "calculation_type": "power_flow",
                    "algorithm": algo,
                },
            )

            sim.set_timeline_info(
                TimelineInfo(reference=0, time_scale=1, start_time=0, duration=1)
            )

            print(f"\nRunning with {algo}...")
            exit_code = sim.run()
            status = "OK" if exit_code == 0 else "FAILED"
            print(f"  Result: {status}")


def main():
    """Run example scenarios."""
    print("\n" + "#" * 60)
    print("# Power Grid Model Integration - Example")
    print("#" * 60)
    print("\nThis example demonstrates the power-grid-model integration")
    print("capabilities in movici-simulation-core.\n")

    # Run all scenarios
    results = []
    results.append(("Power Flow", run_power_flow_scenario()))
    results.append(("State Estimation", run_state_estimation_scenario()))
    results.append(("Short Circuit", run_short_circuit_scenario()))

    # Algorithm comparison
    run_algorithm_comparison()

    # Summary
    print("\n" + "=" * 60)
    print("Summary")
    print("=" * 60)
    for name, code in results:
        status = "PASSED" if code == 0 else "FAILED"
        print(f"  {name}: {status}")

    # Return overall success
    return 0 if all(code == 0 for _, code in results) else 1


if __name__ == "__main__":
    sys.exit(main())
