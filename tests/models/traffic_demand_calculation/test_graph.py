import numpy as np
import pytest

from movici_simulation_core.data_tracker.index import Index
from movici_simulation_core.models.common.entities import (
    PointEntity,
    LinkEntity,
    TransportSegmentEntity,
)
from movici_simulation_core.models.traffic_demand_calculation.network import (
    build_graph,
    Graph,
    Network,
)
from movici_simulation_core.testing.helpers import create_entity_group_with_data


class TestGraph:
    @pytest.fixture
    def cost_factor(self):
        return np.array([1, 4, 1, 2, 3, 1], dtype=float)

    @pytest.fixture
    def nodes(self):
        return np.array([1, 2, 3, 4, 5])

    @pytest.fixture
    def nodes_index(self, nodes):
        return Index(nodes)

    @pytest.fixture
    def graph(self, nodes, nodes_index, cost_factor) -> Graph:
        r"""
        1 -> 2 <--> 4 -> 5
              \-> 3-^
        """
        from_node_id = np.array([1, 2, 3, 2, 4, 4])
        to_node_id = np.array([2, 4, 4, 3, 5, 2])
        graph = build_graph(nodes_index, from_node_id=from_node_id, to_node_id=to_node_id)
        graph.update_cost_factor(cost_factor)
        return graph

    def test_build_graph(self, graph):
        np.testing.assert_array_equal(graph.indptr, [0, 1, 3, 4, 6, 6])
        np.testing.assert_array_equal(graph.indices, [1, 2, 3, 3, 1, 4])
        np.testing.assert_array_equal(graph.cost_factor_indices, [0, 3, 1, 2, 5, 4])

    def test_get_cost(self, graph, nodes_index):
        from_id, to_id = 2, 3
        assert graph.get_cost(nodes_index[from_id], nodes_index[to_id]) == 2

    def test_get_neighbours(self, graph):
        np.testing.assert_array_equal(graph.get_neighbours(1), [2, 3])


@pytest.fixture
def network_1():
    r"""
    (6) ----v
    ^- 1 -> 2 <-------> 4 -> 5 <-(8)
          \-> 3--------^|
               \->(7)<-/
    """
    transport_nodes = create_entity_group_with_data(PointEntity("t"), {"id": [1, 2, 3, 4, 5]})
    virtual_nodes = create_entity_group_with_data(PointEntity("t"), {"id": [6, 7, 8]})
    transport_links = create_entity_group_with_data(
        TransportSegmentEntity("tl"),
        {
            "id": [9, 10, 11, 12, 13, 14],
            "line_properties": {
                "from_node_id": [1, 2, 3, 2, 4, 4],
                "to_node_id": [2, 4, 4, 3, 5, 2],
            },
        },
    )
    virtual_links = create_entity_group_with_data(
        LinkEntity("vl"),
        {
            "id": [15, 16, 17, 18, 19],
            "line_properties": {
                "from_node_id": [1, 6, 3, 4, 8],
                "to_node_id": [6, 2, 7, 7, 5],
            },
        },
    )
    cost_factor = np.ones((6,), dtype=float)
    network = Network(transport_nodes, transport_links, virtual_nodes, virtual_links, cost_factor)
    return network


@pytest.fixture
def network_2():
    r"""
             (6)    (7)
             / \   /
    (5)--0--1--2--3--4--(8)
    """
    transport_nodes = create_entity_group_with_data(PointEntity("t"), {"id": [0, 1, 2, 3, 4]})
    virtual_nodes = create_entity_group_with_data(PointEntity("t"), {"id": [5, 6, 7, 8]})
    transport_links = create_entity_group_with_data(
        TransportSegmentEntity("tl"),
        {
            "id": [9, 10, 11, 12, 13, 14, 15, 16],
            "line_properties": {
                "from_node_id": [0, 1, 1, 2, 2, 3, 3, 4],
                "to_node_id": [1, 0, 2, 1, 3, 2, 4, 3],
            },
        },
    )
    virtual_links = create_entity_group_with_data(
        LinkEntity("vl"),
        {
            "id": [17, 18, 19, 20, 21],
            "line_properties": {
                "from_node_id": [5, 1, 6, 7, 4],
                "to_node_id": [0, 6, 2, 3, 8],
            },
        },
    )
    cost_factor = np.array([1, 1, 2, 2, 3, 3, 4, 4], dtype=float)
    return Network(transport_nodes, transport_links, virtual_nodes, virtual_links, cost_factor)


@pytest.fixture
def network_3(road_network_for_traffic):
    r"""
     (10)->0->2<-(12)
           ^   \
            \--1<-(11)
    The link between 1 and 2 is defined as 1->2 but with a layout having only a reverse direction,
    """
    data = road_network_for_traffic["data"]
    transport_nodes = create_entity_group_with_data(
        PointEntity("t"), data["transport_node_entities"]
    )
    virtual_nodes = create_entity_group_with_data(PointEntity("t"), data["virtual_node_entities"])
    transport_links = create_entity_group_with_data(
        TransportSegmentEntity("t"), data["road_segment_entities"]
    )
    virtual_links = create_entity_group_with_data(LinkEntity("t"), data["virtual_link_entities"])
    return Network(transport_nodes, transport_links, virtual_nodes, virtual_links)


class TestNetwork1:
    @pytest.fixture
    def network(self, network_1):
        return network_1

    def test_network_creates_graph(self, network):
        graph = network.graph
        np.testing.assert_array_equal(graph.indptr, [0, 2, 5, 7, 10, 11, 13, 15, 16])
        # every virtual link is bidirectional, which means it gets duplicated in a directed graph
        # 6 transport links plus 2*5 virtual links gives 16 links total
        np.testing.assert_array_equal(
            graph.indices, [1, 5, 2, 3, 5, 3, 6, 1, 4, 6, 7, 0, 1, 2, 3, 4]
        )

        np.testing.assert_array_equal(
            graph.cost_factor_indices, [0, 6, 3, 1, 12, 2, 8, 5, 4, 9, 15, 11, 7, 13, 14, 10]
        )

    def test_transport_links_have_a_normal_cost_factor(self, network):
        assert np.sum(network.cost_factor == 1) == network.tl_count

    def test_outgoing_virtual_links_have_high_cost_factor(self, network):
        indices = network.node_index[network.virtual_node_ids]
        graph = network.graph
        for idx in indices:
            begin, end = graph.indptr[idx : idx + 2]
            np.testing.assert_array_equal(network.cost_factor[begin:end], network.MAX_COST_FACTOR)

    def test_incoming_virtual_links_have_low_cost_factor(self, network):
        graph = network.graph
        incoming_virtual_links = [(1, 6), (2, 6), (3, 7), (4, 7), (5, 8)]
        incoming_indices = (network.node_index[link] for link in incoming_virtual_links)
        for src, tgt in incoming_indices:
            assert graph.get_cost(src, tgt) == network.MIN_COST_FACTOR

    def test_set_source_node_lowers_outgoing_cost_factor(self, network):
        source_node = 6
        network.set_source_node(6)
        idx = network.node_index[source_node]
        begin, end = network.graph.indptr[idx : idx + 2]
        np.testing.assert_array_equal(network.cost_factor[begin:end], network.MIN_COST_FACTOR)

    def test_set_other_source_node_resets_previous_cost_factor(self, network):
        network.set_source_node(6)
        network.set_source_node(8)
        idx = network.node_index[6]
        begin, end = network.graph.indptr[idx : idx + 2]
        np.testing.assert_array_equal(network.cost_factor[begin:end], network.MAX_COST_FACTOR)

    def test_shortest_path(self, network):
        dist, prev = network.get_shortest_path(6)
        np.testing.assert_array_almost_equal(dist, [0, 0, 1, 1, 2, 0, 1, 2])
        np.testing.assert_array_almost_equal(prev, [5, 5, 1, 1, 3, -9999, 2, 4])

    def test_doesnt_route_through_virtual_node(self, network):
        # set the direct link between 2 and 4 to a higher value, so that the shortest path
        # goes through node 3 and 4. If routing is possible through VN 7, the distance between
        # 3 and 4 becomes almost 0. We don't want that

        network.update_cost_factor([1, 4, 1, 1, 1, 1])
        dist, prev = network.get_shortest_path(6)
        assert np.isclose(dist[7], 3)
        assert 6 not in prev  # 6 is the index of VN7

    def test_can_get_full_matrix_of_shortest_paths(self, network):
        result = network.all_shortest_paths(network.virtual_node_ids)
        np.testing.assert_array_almost_equal(result, [[0, 1, 2], [1, 0, 1], [np.inf, np.inf, 0]])


class TestNetwork2:
    @pytest.fixture
    def network(self, network_2):
        return network_2

    def test_directionality(self, network):
        np.testing.assert_array_equal(network.vl_directionality, [1, -1, 1, 1, -1])

    def test_graph_links(self, network):
        np.testing.assert_array_equal(network.graph.indptr, [0, 2, 5, 8, 11, 13, 14, 16, 17, 18])
        np.testing.assert_array_equal(
            network.graph.indices, [1, 5, 0, 2, 6, 1, 3, 6, 2, 4, 7, 3, 8, 0, 1, 2, 3, 4]
        )

    @pytest.mark.parametrize(
        "src,tgt,cost",
        [
            (0, 1, 1),
            (0, 5, Network.MIN_COST_FACTOR),
            (1, 0, 1),
            (1, 2, 2),
            (1, 6, Network.MIN_COST_FACTOR),
            (2, 1, 2),
            (2, 3, 3),
            (2, 6, Network.MIN_COST_FACTOR),
            (3, 2, 3),
            (3, 4, 4),
            (3, 7, Network.MIN_COST_FACTOR),
            (4, 3, 4),
            (4, 8, Network.MIN_COST_FACTOR),
            (5, 0, Network.MAX_COST_FACTOR),
            (6, 1, Network.MAX_COST_FACTOR),
            (6, 2, Network.MAX_COST_FACTOR),
            (7, 3, Network.MAX_COST_FACTOR),
            (8, 4, Network.MAX_COST_FACTOR),
        ],
    )
    def test_cost_factor(self, network, src, tgt, cost):
        assert network.graph.get_cost(src, tgt) == cost

    def test_can_get_full_matrix_of_shortest_paths(self, network):
        result = network.all_shortest_paths()
        np.testing.assert_array_almost_equal(
            result,
            [
                [0, 1, 6, 10],
                [1, 0, 3, 7],
                [6, 3, 0, 4],
                [10, 7, 4, 0],
            ],
        )


@pytest.mark.parametrize(
    "layout,mapping,indices, indptr",
    [
        ([1, 0, 0, 0], [0], [1, 2, 3, 0, 1], [0, 2, 3, 4, 5]),
        ([2, 0, 0, 0], [0], [1, 2, 3, 0, 1], [0, 2, 3, 4, 5]),
        ([0, 1, 0, 0], [0], [2, 0, 3, 0, 1], [0, 1, 3, 4, 5]),
        ([1, 1, 0, 0], [0, 0], [1, 2, 0, 3, 0, 1], [0, 2, 4, 5, 6]),
        ([0, 0, 1, 0], [0, 0], [1, 2, 0, 3, 0, 1], [0, 2, 4, 5, 6]),
        ([0, 0, 0, 1], [0, 0], [1, 2, 0, 3, 0, 1], [0, 2, 4, 5, 6]),
    ],
)
def test_network_with_layout(layout, mapping, indices, indptr):
    r"""
    (2)<->0->1<->(3)
    :return:
    """
    transport_nodes = create_entity_group_with_data(PointEntity("tn"), {"id": [0, 1]})
    virtual_nodes = create_entity_group_with_data(PointEntity("vn"), {"id": [2, 3]})
    transport_links = create_entity_group_with_data(
        TransportSegmentEntity("tl"),
        {
            "id": [4],
            "line_properties": {"from_node_id": [0], "to_node_id": [1]},
            "transport.layout": [layout],
        },
    )
    virtual_links = create_entity_group_with_data(
        LinkEntity("vl"),
        {"id": [10, 11], "line_properties": {"from_node_id": [2, 3], "to_node_id": [0, 1]}},
    )
    network = Network(transport_nodes, transport_links, virtual_nodes, virtual_links)
    np.testing.assert_array_equal(network.tl_mapping, mapping)
    np.testing.assert_array_equal(network.graph.indices, indices)
    np.testing.assert_array_equal(network.graph.indptr, indptr)


def test_get_network_with_links_based_on_layout(network_3):
    vn10, vn11, vn12 = network_3.node_index[[10, 11, 12]]
    np.testing.assert_array_equal(network_3.graph.indices, [2, vn10, 0, 0, vn11, 1, vn12, 0, 1, 2])
    np.testing.assert_array_equal(network_3.graph.indptr, [0, 2, 5, 7, 8, 9, 10])