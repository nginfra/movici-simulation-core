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
from movici_simulation_core.models.common.pgm_util import (
    merge_line_collections,
    merge_node_collections,
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


class TestVirtualNodesAndLinks:
    """Tests for virtual nodes and links integration.

    These tests verify that virtual nodes (external grid connection points)
    and links (zero-impedance connections) work correctly with the
    power-grid-model integration, similar to how virtual_node_entities
    and virtual_link_entities work in traffic assignment.
    """

    def test_merged_virtual_nodes_in_power_flow(self):
        """Test power flow with virtual nodes merged into regular nodes.

        Topology:
            [Source] -> VirtualNode (380kV) -> Link -> Node1 (10kV)
                -> Line -> Node2 (10kV) -> [Load]

        The virtual node represents the external grid connection point.
        """
        wrapper = PowerGridWrapper()

        # Regular nodes (10 kV distribution network)
        regular_nodes = NodeCollection(
            ids=[1, 2],
            u_rated=[10000.0, 10000.0],
        )

        # Virtual node (external grid at 380 kV, stepped down via link)
        # In reality this would be a transformer, but for testing we use same voltage
        virtual_nodes = NodeCollection(
            ids=[100],  # Virtual node ID
            u_rated=[10000.0],  # Same voltage for simplicity
        )

        # Merge virtual nodes with regular nodes
        nodes = merge_node_collections(regular_nodes, virtual_nodes)

        # Source connects to virtual node
        sources = SourceCollection(
            ids=[1],
            node=[100],  # Connected to virtual node
            u_ref=[1.0],
        )

        # Link connects virtual node to main network (low impedance)
        link_lines = LineCollection(
            ids=[1000],
            from_node=[100],
            to_node=[1],
            r1=[1e-6],  # Minimal resistance
            x1=[1e-6],  # Minimal reactance
            c1=[1e-12],
            tan1=[0.0],
        )

        # Regular line
        regular_lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[0.0],
            tan1=[0.0],
        )

        # Merge link lines with regular lines
        lines = merge_line_collections(link_lines, regular_lines)

        # Load at end of network
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[100000.0],  # 100 kW
            q_specified=[0.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        # Check that all 3 nodes have results
        assert len(result.nodes) == 3

        # Virtual node (source) should be at ~1.0 p.u.
        virtual_idx = np.where(result.nodes.ids == 100)[0][0]
        assert abs(result.nodes.u_pu[virtual_idx] - 1.0) < 0.01

        # Node 1 should be very close to virtual node (minimal drop over link)
        node1_idx = np.where(result.nodes.ids == 1)[0][0]
        assert abs(result.nodes.u_pu[node1_idx] - result.nodes.u_pu[virtual_idx]) < 0.001

        # Node 2 should have some voltage drop due to load
        node2_idx = np.where(result.nodes.ids == 2)[0][0]
        assert result.nodes.u_pu[node2_idx] < result.nodes.u_pu[node1_idx]

    def test_cables_treated_same_as_lines(self):
        """Test that cables (merged as lines) work correctly in power flow.

        Cables are underground lines with the same electrical model as
        overhead lines, just merged into the line collection.
        """
        wrapper = PowerGridWrapper()

        nodes = NodeCollection(
            ids=[1, 2, 3],
            u_rated=[10000.0, 10000.0, 10000.0],
        )

        sources = SourceCollection(
            ids=[1],
            node=[1],
            u_ref=[1.0],
        )

        # Regular overhead line
        lines = LineCollection(
            ids=[1],
            from_node=[1],
            to_node=[2],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
        )

        # Underground cable (higher capacitance typical of cables)
        cables = LineCollection(
            ids=[2],
            from_node=[2],
            to_node=[3],
            r1=[0.08],  # Slightly lower resistance (larger conductor)
            x1=[0.03],  # Lower reactance
            c1=[1e-7],  # Higher capacitance (typical of cables)
            tan1=[0.001],
        )

        # Merge cables with lines
        all_lines = merge_line_collections(lines, cables)

        loads = LoadCollection(
            ids=[1],
            node=[3],
            p_specified=[50000.0],
            q_specified=[10000.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=all_lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        # Check results
        assert len(result.nodes) == 3
        assert result.lines is not None
        assert len(result.lines) == 2

        # Both lines should have current flowing
        assert all(result.lines.i_from > 0)

    def test_full_network_with_virtual_nodes_links_and_cables(self):
        """Test complete network with all new entity types.

        Topology:
            [Source] -> VirtualNode (HV) --(Link)--> Node1
                                                       |
                                                    (Cable)
                                                       |
                                                     Node2 --(Line)--> Node3 -> [Load]
        """
        wrapper = PowerGridWrapper()

        # Regular nodes
        regular_nodes = NodeCollection(
            ids=[1, 2, 3],
            u_rated=[10000.0, 10000.0, 10000.0],
        )

        # Virtual node (HV connection point)
        virtual_nodes = NodeCollection(
            ids=[100],
            u_rated=[10000.0],
        )

        # Merge all nodes
        nodes = merge_node_collections(regular_nodes, virtual_nodes)

        # Source at virtual node
        sources = SourceCollection(
            ids=[1],
            node=[100],
            u_ref=[1.0],
        )

        # Link from virtual node to Node 1
        links = LineCollection(
            ids=[1000],
            from_node=[100],
            to_node=[1],
            r1=[1e-6],
            x1=[1e-6],
            c1=[1e-12],
            tan1=[0.0],
        )

        # Cable from Node 1 to Node 2
        cables = LineCollection(
            ids=[2000],
            from_node=[1],
            to_node=[2],
            r1=[0.05],
            x1=[0.02],
            c1=[1e-7],
            tan1=[0.001],
        )

        # Regular line from Node 2 to Node 3
        lines = LineCollection(
            ids=[1],
            from_node=[2],
            to_node=[3],
            r1=[0.1],
            x1=[0.05],
            c1=[1e-9],
            tan1=[0.0],
        )

        # Merge all branches: links -> cables -> lines
        all_lines = merge_line_collections(links, cables)
        all_lines = merge_line_collections(all_lines, lines)

        # Load at Node 3
        loads = LoadCollection(
            ids=[1],
            node=[3],
            p_specified=[75000.0],
            q_specified=[15000.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=all_lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        # Verify all entities have results
        assert len(result.nodes) == 4  # 3 regular + 1 virtual
        assert len(result.lines) == 3  # 1 link + 1 cable + 1 line

        # Verify voltage profile makes sense
        # Virtual node should be at reference voltage
        virtual_idx = np.where(result.nodes.ids == 100)[0][0]
        assert abs(result.nodes.u_pu[virtual_idx] - 1.0) < 0.01

        # Voltage should decrease along the network
        node1_idx = np.where(result.nodes.ids == 1)[0][0]
        node2_idx = np.where(result.nodes.ids == 2)[0][0]
        node3_idx = np.where(result.nodes.ids == 3)[0][0]

        # Allow for small numerical tolerance
        assert result.nodes.u_pu[node1_idx] >= result.nodes.u_pu[node2_idx] - 0.001
        assert result.nodes.u_pu[node2_idx] >= result.nodes.u_pu[node3_idx] - 0.001

        # Link should have minimal losses (very small voltage drop)
        link_idx = np.where(result.lines.ids == 1000)[0][0]
        # Power loss on link should be very small
        link_loss = abs(result.lines.p_from[link_idx]) - abs(result.lines.p_to[link_idx])
        assert abs(link_loss) < 100  # Less than 100 W loss on link

    def test_multiple_virtual_nodes_and_links(self):
        """Test network with multiple virtual nodes (multiple grid connections).

        This represents a meshed network with multiple infeed points,
        similar to the Den Haag MV network with 5 virtual nodes.
        """
        wrapper = PowerGridWrapper()

        # Regular nodes (MV network)
        regular_nodes = NodeCollection(
            ids=[1, 2, 3],
            u_rated=[10000.0, 10000.0, 10000.0],
        )

        # Two virtual nodes (two HV/MV substations)
        virtual_nodes = NodeCollection(
            ids=[100, 200],
            u_rated=[10000.0, 10000.0],
        )

        nodes = merge_node_collections(regular_nodes, virtual_nodes)

        # Two sources (one at each virtual node)
        sources = SourceCollection(
            ids=[1, 2],
            node=[100, 200],
            u_ref=[1.0, 1.0],
        )

        # Links from virtual nodes to network
        links = LineCollection(
            ids=[1000, 2000],
            from_node=[100, 200],
            to_node=[1, 3],
            r1=[1e-6, 1e-6],
            x1=[1e-6, 1e-6],
            c1=[1e-12, 1e-12],
            tan1=[0.0, 0.0],
        )

        # Lines connecting the MV network
        lines = LineCollection(
            ids=[1, 2],
            from_node=[1, 2],
            to_node=[2, 3],
            r1=[0.1, 0.1],
            x1=[0.05, 0.05],
            c1=[1e-9, 1e-9],
            tan1=[0.0, 0.0],
        )

        all_lines = merge_line_collections(links, lines)

        # Load at center node
        loads = LoadCollection(
            ids=[1],
            node=[2],
            p_specified=[200000.0],  # 200 kW
            q_specified=[50000.0],
        )

        wrapper.build_network(
            nodes=nodes,
            lines=all_lines,
            loads=loads,
            sources=sources,
        )

        result = wrapper.calculate_power_flow()

        # Verify all nodes have results
        assert len(result.nodes) == 5  # 3 regular + 2 virtual

        # Both virtual nodes should be at reference voltage
        for vid in [100, 200]:
            idx = np.where(result.nodes.ids == vid)[0][0]
            assert abs(result.nodes.u_pu[idx] - 1.0) < 0.01

        # Power should flow from both sources
        # (load is split between two infeeds)
        assert result.sources is not None
        for source_p in result.sources.p:
            assert source_p > 0  # Both sources supplying power
