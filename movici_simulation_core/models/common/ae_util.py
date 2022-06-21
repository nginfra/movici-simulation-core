import typing as t

import numpy as np

from movici_simulation_core.ae_wrapper.collections import LinkCollection, NodeCollection
from movici_simulation_core.ae_wrapper.point_generator import PointGenerator
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.core import UniformAttribute
from movici_simulation_core.models.common.entity_groups import (
    PointEntity,
    TransportSegmentEntity,
    VirtualLinkEntity,
)

# This epsilon isn't very small, but making it smaller breaks aequilibrae
eps = 5 * 1e-5


def calculate_capacities(capacities: np.ndarray, layouts: np.ndarray) -> np.ndarray:
    lanes = np.sum(layouts, axis=1)
    return np.maximum(capacities * lanes, eps)


def get_capacities_from_attribute(
    capacity_attribute: UniformAttribute,
    layout_attribute: t.Optional[UniformAttribute] = None,
) -> np.ndarray:
    capacities = capacity_attribute.array.copy()
    capacities[capacity_attribute.is_special() | capacity_attribute.is_undefined()] = float("inf")

    if layout_attribute is None:
        layout_array = np.ones((len(capacities), 1), dtype=np.int32)
    else:
        layout_array = layout_attribute.array

    capacities = calculate_capacities(capacities, layout_array)
    return capacities


def get_max_speeds_from_attribute(max_speed_attribute: UniformAttribute) -> np.ndarray:
    max_speeds = max_speed_attribute.array.copy()
    max_speeds[max_speed_attribute.is_special() | max_speed_attribute.is_undefined()] = float(
        "inf"
    )

    return max_speeds


def get_cargo_allowed_from_attribute(cargo_allowed_attribute: UniformAttribute) -> np.ndarray:
    rv = cargo_allowed_attribute.array.astype(bool)
    rv[cargo_allowed_attribute.is_undefined()] = True
    return rv


def get_transport_directions(segments: TransportSegmentEntity) -> np.ndarray:
    contributions = np.array([1, -1, 0, 0])
    return (np.minimum(segments.layout, 1) * contributions).sum(axis=1)


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

    max_speeds = get_max_speeds_from_attribute(segments.max_speed)
    capacities = get_capacities_from_attribute(segments.capacity, segments.layout)

    return LinkCollection(
        ids=segments.index.ids,
        from_nodes=segments.from_node_id.array,
        to_nodes=segments.to_node_id.array,
        directions=directions,
        geometries=geometries,
        max_speeds=max_speeds,
        capacities=capacities,
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
    if segments.max_speed.has_data():
        max_speeds = get_max_speeds_from_attribute(segments.max_speed)
    else:
        max_speeds = np.full(len(geometries), float("inf"))

    if segments.capacity.has_data():
        capacities = get_capacities_from_attribute(segments.capacity)
    else:
        capacities = np.full(len(geometries), float("inf"))

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
