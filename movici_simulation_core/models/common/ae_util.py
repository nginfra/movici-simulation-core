import numpy as np

from movici_simulation_core.ae_wrapper.collections import NodeCollection, LinkCollection
from movici_simulation_core.ae_wrapper.point_generator import PointGenerator
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.models.common.entities import (
    PointEntity,
    TransportSegmentEntity,
    VirtualLinkEntity,
)


def get_transport_directions(segments: TransportSegmentEntity) -> np.ndarray:
    directions = []
    for layout in segments.layout:
        forward = layout[0] > 0
        backward = layout[1] > 0
        other = np.any(layout[2:] > 0)

        direction = 0
        if not other:
            if forward and not backward:
                direction = 1
            if backward and not forward:
                direction = -1

        directions.append(direction)
    return np.array(directions)


def get_nodes(nodes: PointEntity, point_generator: PointGenerator) -> NodeCollection:

    geometries = []
    for node_x, node_y in zip(nodes.x, nodes.y):
        geometry = point_generator.generate_and_add([node_x, node_y])
        geometries.append(geometry)

    return NodeCollection(
        ids=nodes.index.ids,
        is_centroids=np.zeros(len(nodes), dtype=bool),
        geometries=geometries,
    )


def get_links(segments: TransportSegmentEntity) -> LinkCollection:
    geometries = []
    linestring_csr = segments.linestring.csr
    for i in range(len(linestring_csr.row_ptr) - 1):
        geometries.append(linestring_csr.get_row(i)[:, :2])

    directions = get_transport_directions(segments)
    lanes = np.sum(segments.layout, axis=1)

    return LinkCollection(
        ids=segments.index.ids,
        from_nodes=segments.from_node_id.array,
        to_nodes=segments.to_node_id.array,
        directions=directions,
        geometries=geometries,
        max_speeds=segments.max_speed.array,
        capacities=segments.capacity.array * lanes,
    )


def get_demand_nodes(demand_nodes: PointEntity, point_generator: PointGenerator) -> NodeCollection:
    geometries = []
    for node_x, node_y in zip(demand_nodes.x, demand_nodes.y):
        geometry = point_generator.generate_and_add([node_x, node_y])
        geometries.append(geometry)

    return NodeCollection(
        ids=demand_nodes.index.ids,
        is_centroids=np.ones(len(geometries), dtype=bool),
        geometries=geometries,
    )


def get_demand_links(segments: VirtualLinkEntity) -> LinkCollection:
    geometries = []
    linestring_csr = segments.linestring.csr
    for i in range(len(linestring_csr.row_ptr) - 1):
        geometries.append(linestring_csr.get_row(i)[:, :2])

    if segments.max_speed.has_data() and segments.capacity.has_data():
        max_speeds = np.full(len(geometries), float("inf"))
        capacities = np.full(len(geometries), float("inf"))
    else:
        max_speeds = segments.max_speed.array
        capacities = segments.capacity.array

    return LinkCollection(
        ids=segments.index.ids,
        from_nodes=segments.from_node_id.array,
        to_nodes=segments.to_node_id.array,
        directions=np.zeros(len(geometries)),
        geometries=geometries,
        max_speeds=max_speeds,
        capacities=capacities,
    )


def fill_project(
    project: ProjectWrapper,
    demand_nodes: PointEntity,
    demand_links: VirtualLinkEntity,
    transport_nodes: PointEntity,
    transport_segments: TransportSegmentEntity,
):
    demand_nodes = get_demand_nodes(demand_nodes, project.point_generator)
    project.add_nodes(demand_nodes)

    nodes = get_nodes(transport_nodes, project.point_generator)
    project.add_nodes(nodes)

    links = get_links(transport_segments)
    project.add_links(links)

    demand_links = get_demand_links(demand_links)
    project.add_links(demand_links, raise_on_geometry_mismatch=False)
