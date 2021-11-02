from movici_simulation_core.testing.road_network import generate_road_network


def test_generate_road_network():
    nodes = [(0, 1), (2, 3)]
    links = [(0, 1)]
    geom_offset = (0, 0)
    assert generate_road_network(nodes, links, geom_offset=geom_offset) == {
        "virtual_node_entities": {
            "id": [0, 1],
            "reference": ["VN0", "VN1"],
            "point_properties": {
                "position_x": [0, 2],
                "position_y": [1, 3],
            },
        },
        "transport_node_entities": {
            "id": [1000, 1001],
            "reference": ["TN0", "TN1"],
            "point_properties": {
                "position_x": [0, 2],
                "position_y": [1, 3],
            },
        },
        "virtual_link_entities": {
            "id": [2000, 2001],
            "reference": ["VL0", "VL1"],
            "line_properties": {
                "from_node_id": [0, 1],
                "to_node_id": [1000, 1001],
            },
            "shape_properties": {
                "linestring_2d": [
                    [[0, 1], [0, 1]],
                    [[2, 3], [2, 3]],
                ]
            },
        },
        "road_segment_entities": {
            "id": [3000],
            "reference": ["RS0"],
            "line_properties": {
                "from_node_id": [1000],
                "to_node_id": [1001],
            },
            "shape_properties": {
                "linestring_2d": [
                    [[0, 1], [2, 3]],
                ]
            },
            "transport.layout": [[1, 0, 0, 0]],
            "transport.max_speed": [1],
            "transport.capacity.hours": [10],
        },
    }
