"""Tests for power grid calculation model."""

import numpy as np

from movici_simulation_core.integrations.pgm.collections import (
    LineCollection,
    LoadCollection,
    NodeCollection,
    SourceCollection,
)
from movici_simulation_core.integrations.pgm.network_wrapper import (
    CalculationMethod,
    PowerGridWrapper,
)


class TestPowerGridWrapper:
    """Tests for PowerGridWrapper class."""

    def test_build_simple_network(self):
        """Test building a simple 2-node network."""
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],  # 10 kV
        )
        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],  # 1.0 p.u.
        )
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[1000.0],  # 1 kW
            q_specified=[0.0],
        )
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],  # 0.1 Ω
            x1=[0.05],  # 0.05 Ω
            c1=[0.0],
            tan1=[0.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        assert wrapper.model is not None
        assert len(wrapper.input_data) > 0

    def test_power_flow_calculation(self):
        """Test running power flow on simple network."""
        wrapper = PowerGridWrapper()

        # Simple network: Source -> Line -> Load
        nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )
        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],
        )
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[100000.0],  # 100 kW
            q_specified=[0.0],
        )
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[0.0],
            tan1=[0.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        # Check that we got results
        assert result.nodes is not None
        assert len(result.nodes) == 2

        # Source node should be at 1.0 p.u.
        source_idx = np.where(result.nodes.ids == 1)[0][0]
        assert abs(result.nodes.u_pu[source_idx] - 1.0) < 0.01

        # Load node should have some voltage drop
        load_idx = np.where(result.nodes.ids == 2)[0][0]
        assert result.nodes.u_pu[load_idx] < 1.0  # Voltage drop expected

    def test_update_loads(self):
        """Test updating load values."""
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )
        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],
        )
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[100000.0],
            q_specified=[0.0],
        )
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[0.0],
            tan1=[0.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        # First calculation
        result1 = wrapper.calculate_power_flow()
        load_idx = np.where(result1.nodes.ids == 2)[0][0]
        voltage1 = result1.nodes.u_pu[load_idx]

        # Update load to higher value
        updated_loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[200000.0],  # Double the load
            q_specified=[0.0],
        )
        wrapper.update_loads(updated_loads)

        # Second calculation
        result2 = wrapper.calculate_power_flow()
        voltage2 = result2.nodes.u_pu[load_idx]

        # Higher load should cause more voltage drop
        assert voltage2 < voltage1

    def test_calculation_methods(self):
        """Test different calculation methods produce similar results."""
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )
        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],
        )
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[50000.0],
            q_specified=[10000.0],
        )
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.01],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        # Newton-Raphson (default)
        result_nr = wrapper.calculate_power_flow(method=CalculationMethod.NEWTON_RAPHSON)

        # Iterative current
        result_ic = wrapper.calculate_power_flow(method=CalculationMethod.ITERATIVE_CURRENT)

        # Results should be similar (within 1%)
        load_idx = np.where(result_nr.nodes.ids == 2)[0][0]
        diff = abs(result_nr.nodes.u_pu[load_idx] - result_ic.nodes.u_pu[load_idx])
        assert diff < 0.01

    def test_line_results(self):
        """Test that line results are returned."""
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )
        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],
        )
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[100000.0],
            q_specified=[0.0],
        )
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[0.0],
            tan1=[0.0],
            i_n=[100.0],  # Rated current
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        assert result.lines is not None
        assert len(result.lines) == 1

        # Check that current is flowing
        assert result.lines.i_from[0] > 0
        assert result.lines.i_to[0] > 0

        # Check loading is calculated
        assert result.lines.loading[0] > 0

    def test_close_cleanup(self):
        """Test that close cleans up resources."""
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(ids=[1], u_rated=[10000.0])
        sources = SourceCollection(ids=[1], node=[1], u_ref=[1.0])

        wrapper.build_network(nodes=nodes, sources=sources)
        assert wrapper.model is not None

        wrapper.close()

        assert wrapper.model is None
        assert len(wrapper.input_data) == 0
