from movici_simulation_core.testing.road_network import generate_road_network


def test_generate_road_network():
    nodes = [(0, 1), (2, 3)]
    links = [(0, 1)]
    geom_offset = (0, 0)
    assert generate_road_network(nodes, links, geom_offset=geom_offset) == {
        "virtual_node_entities": {
            "id": [0, 1],
            "reference": ["VN0", "VN1"],
            "geometry.x": [0, 2],
            "geometry.y": [1, 3],
        },
        "transport_node_entities": {
            "id": [1000, 1001],
            "reference": ["TN0", "TN1"],
            "geometry.x": [0, 2],
            "geometry.y": [1, 3],
        },
        "virtual_link_entities": {
            "id": [2000, 2001],
            "reference": ["VL0", "VL1"],
            "topology.from_node_id": [0, 1],
            "topology.to_node_id": [1000, 1001],
            "geometry.linestring_2d": [
                [[0, 1], [0, 1]],
                [[2, 3], [2, 3]],
            ],
        },
        "road_segment_entities": {
            "id": [3000],
            "reference": ["RS0"],
            "topology.from_node_id": [1000],
            "topology.to_node_id": [1001],
            "geometry.linestring_2d": [
                [[0, 1], [2, 3]],
            ],
            "transport.layout": [[1, 0, 0, 0]],
            "transport.max_speed": [1],
            "transport.capacity.hours": [10],
        },
    }
