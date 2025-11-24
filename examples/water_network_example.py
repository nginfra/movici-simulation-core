"""Example: Water Network Simulation using WNTR

This example demonstrates how to use the water_network_simulation model
to simulate a water distribution network using WNTR.

The example shows two modes:
1. Loading an existing EPANET INP file
2. Building a network from scratch using Movici datasets
"""

from pathlib import Path


def example_inp_file_mode():
    """Example using INP file mode"""
    print("=" * 60)
    print("Water Network Simulation - INP File Mode")
    print("=" * 60)

    try:
        from movici_simulation_core.integrations.wntr import NetworkWrapper

        # Path to example INP file
        inp_file = Path(__file__).parent / "simple_water_network.inp"

        if not inp_file.exists():
            print(f"INP file not found: {inp_file}")
            return

        # Create network wrapper from INP file
        print(f"\nLoading INP file: {inp_file.name}")
        network = NetworkWrapper(mode="inp_file", inp_file=inp_file)

        # Print network summary
        print("\nNetwork Summary:")
        summary = network.get_network_summary()
        for key, value in summary.items():
            print(f"  {key}: {value}")

        # Run simulation
        print("\nRunning hydraulic simulation...")
        results = network.run_simulation(
            duration=86400,  # 24 hours
            hydraulic_timestep=3600,  # 1 hour
        )

        # Display results
        print("\nSimulation Results (at final timestep):")
        print("\nJunctions:")
        print(f"  {'Node':<10} {'Pressure (m)':<15} {'Head (m)':<15} {'Demand (LPS)':<15}")
        print("  " + "-" * 55)

        for i, name in enumerate(results.node_names[:5]):  # Show first 5 nodes
            if results.node_pressures is not None:
                pressure = results.node_pressures[i]
                head = results.node_heads[i]
                demand = results.node_demands[i]
                print(f"  {name:<10} {pressure:>14.2f} {head:>14.2f} {demand:>14.4f}")

        print("\nPipes:")
        print(f"  {'Link':<10} {'Flow (LPS)':<15} {'Velocity (m/s)':<15} {'Headloss (m)':<15}")
        print("  " + "-" * 55)

        for i, name in enumerate(results.link_names[:5]):  # Show first 5 links
            if results.link_flows is not None:
                flow = results.link_flows[i]
                velocity = results.link_velocities[i]
                headloss = results.link_headlosses[i]
                print(f"  {name:<10} {flow:>14.4f} {velocity:>14.4f} {headloss:>14.4f}")

        print("\n✓ Simulation completed successfully!")
        network.close()

    except ImportError as e:
        print(f"\nError: WNTR not installed. Please install with: pip install wntr")
        print(f"Details: {e}")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


def example_pattern_management():
    """Example of pattern management"""
    print("\n" + "=" * 60)
    print("Pattern Management Example")
    print("=" * 60)

    try:
        import wntr

        from movici_simulation_core.integrations.wntr import PatternManager

        # Create a simple network
        wn = wntr.network.WaterNetworkModel()
        wn.add_pattern("constant", [1.0])

        # Create pattern manager
        pm = PatternManager(wn)

        # Create a daily demand pattern (24 hourly values)
        hourly_pattern = [
            0.6,
            0.5,
            0.5,
            0.5,  # 00:00-04:00 (night)
            0.6,
            0.8,
            1.2,
            1.5,  # 04:00-08:00 (morning)
            1.4,
            1.2,
            1.0,
            0.9,  # 08:00-12:00 (midday)
            0.8,
            0.9,
            1.0,
            1.1,  # 12:00-16:00 (afternoon)
            1.3,
            1.5,
            1.6,
            1.4,  # 16:00-20:00 (evening)
            1.2,
            1.0,
            0.8,
            0.7,  # 20:00-24:00 (night)
        ]

        print("\nCreating daily demand pattern...")
        pattern = pm.create_daily_pattern("daily_demand", hourly_pattern)

        print(f"✓ Pattern created: {len(pattern.multipliers)} hourly values")
        print(f"  Peak multiplier: {max(hourly_pattern):.2f}")
        print(f"  Minimum multiplier: {min(hourly_pattern):.2f}")
        print(f"  Average multiplier: {sum(hourly_pattern) / len(hourly_pattern):.2f}")

        # Create interpolated pattern
        time_value_pairs = [
            (0, 0.5),  # midnight
            (6, 1.5),  # 6 AM - morning peak
            (12, 0.8),  # noon - low demand
            (18, 1.6),  # 6 PM - evening peak
            (24, 0.5),  # midnight
        ]

        print("\nCreating interpolated pattern...")
        pm.set_pattern_timestep(3600)  # 1 hour timestep
        interp_pattern = pm.interpolate_pattern("interpolated", time_value_pairs)

        print(f"✓ Interpolated pattern created: {len(interp_pattern.multipliers)} values")

        print("\nAll patterns in model:")
        for name in wn.pattern_name_list:
            pat = wn.get_pattern(name)
            print(f"  - {name}: {len(pat.multipliers)} multipliers")

    except ImportError:
        print("\nError: WNTR not installed. Please install with: pip install wntr")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


def example_control_management():
    """Example of control rule management"""
    print("\n" + "=" * 60)
    print("Control Management Example")
    print("=" * 60)

    try:
        import wntr

        from movici_simulation_core.integrations.wntr import ControlManager

        # Create a simple network with a pump
        wn = wntr.network.WaterNetworkModel()
        wn.add_junction("J1", base_demand=0.01, elevation=100)
        wn.add_junction("J2", base_demand=0.02, elevation=50)
        wn.add_reservoir("R1", base_head=150)
        wn.add_pipe("P1", "R1", "J1", length=100, diameter=0.3, roughness=100)
        wn.add_pump("PU1", "J1", "J2", pump_type="POWER", pump_parameter=50.0)

        # Create control manager
        cm = ControlManager(wn)

        # Add time-based control: Open pump at 6 AM (21600 seconds)
        print("\nAdding time-based control: Open pump at 6 AM")
        cm.add_time_control(
            control_name="pump_on_morning",
            target_element="PU1",
            target_attribute="status",
            value=1,  # OPEN
            time=21600,  # 6 AM
            time_type="sim_time",
        )

        # Add time-based control: Close pump at 10 PM (79200 seconds)
        print("Adding time-based control: Close pump at 10 PM")
        cm.add_time_control(
            control_name="pump_off_night",
            target_element="PU1",
            target_attribute="status",
            value=0,  # CLOSED
            time=79200,  # 10 PM
            time_type="sim_time",
        )

        # Add conditional control: Close pump if tank level > 20m
        print("Adding conditional control: Monitor junction pressure")
        # Note: In real scenario, you'd monitor a tank level
        # This is a simplified example
        try:
            cm.add_conditional_control(
                control_name="pump_off_high_pressure",
                target_element="PU1",
                target_attribute="status",
                value=0,  # CLOSED
                source_element="J2",
                source_attribute="head",
                operator=">",
                threshold=70.0,
            )
        except Exception as e:
            print(f"  (Conditional control example - some limitations apply)")

        print(f"\n✓ Controls added successfully!")
        print(f"  Total controls in model: {len(wn.control_name_list)}")

        print("\nControl list:")
        for control_name in wn.control_name_list:
            print(f"  - {control_name}")

    except ImportError:
        print("\nError: WNTR not installed. Please install with: pip install wntr")
    except Exception as e:
        print(f"\nError: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run all examples"""
    print("\n" + "=" * 60)
    print("WNTR Water Network Simulation Examples")
    print("=" * 60)

    example_inp_file_mode()
    example_pattern_management()
    example_control_management()

    print("\n" + "=" * 60)
    print("All examples completed!")
    print("=" * 60)


if __name__ == "__main__":
    main()
