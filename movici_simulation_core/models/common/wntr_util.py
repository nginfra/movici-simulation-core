"""Utility functions for converting Movici entities to WNTR collections.

These functions extract data from Movici entity groups and create the
intermediate collection objects used by the WNTR network wrapper.
"""

from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core.integrations.wntr import (
    JunctionCollection,
    PipeCollection,
    PumpCollection,
    ReservoirCollection,
    TankCollection,
    ValveCollection,
)
from movici_simulation_core.integrations.wntr.id_mapper import IdMapper

if t.TYPE_CHECKING:
    from movici_simulation_core.models.water_network_simulation.dataset import (
        WaterJunctionEntity,
        WaterPipeEntity,
        WaterPumpEntity,
        WaterReservoirEntity,
        WaterTankEntity,
        WaterValveEntity,
    )


def _get_coordinates(entity) -> t.Optional[np.ndarray]:
    """Extract coordinates from an entity if available.

    :param entity: Entity with optional x and y attributes
    :return: (N, 2) array of coordinates or None
    """
    if entity.x.is_initialized() and entity.y.is_initialized():
        return np.column_stack([entity.x.array, entity.y.array])
    return None


def _get_node_names(entity, id_mapper: IdMapper) -> t.Tuple[t.List[str], t.List[str]]:
    """Extract from/to node names for link entities.

    :param entity: Link entity with from_node_id and to_node_id attributes
    :param id_mapper: IdMapper for ID translation
    :return: Tuple of (from_nodes, to_nodes) lists
    """
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in entity.from_node_id.array]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in entity.to_node_id.array]
    return from_nodes, to_nodes


def get_junctions(junctions: "WaterJunctionEntity", id_mapper: IdMapper) -> JunctionCollection:
    """Convert junction entities to JunctionCollection.

    :param junctions: WaterJunctionEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: JunctionCollection with junction data
    """
    node_names = id_mapper.register_nodes(junctions.index.ids, entity_type="junction")
    demand_factors = (
        junctions.demand_factor.array if junctions.demand_factor.is_initialized() else None
    )

    return JunctionCollection(
        node_names=node_names,
        elevations=junctions.elevation.array,
        base_demands=junctions.base_demand.array,
        demand_factors=demand_factors,
        coordinates=_get_coordinates(junctions),
    )


def get_tanks(tanks: "WaterTankEntity", id_mapper: IdMapper) -> TankCollection:
    """Convert tank entities to TankCollection.

    :param tanks: WaterTankEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: TankCollection with tank data
    """
    node_names = id_mapper.register_nodes(tanks.index.ids, entity_type="tank")
    volume_curves = (
        _extract_csr_curves(tanks.volume_curve) if tanks.volume_curve.is_initialized() else None
    )

    return TankCollection(
        node_names=node_names,
        elevations=tanks.elevation.array,
        init_levels=tanks.level.array,
        min_levels=tanks.min_level.array if tanks.min_level.is_initialized() else None,
        max_levels=tanks.max_level.array if tanks.max_level.is_initialized() else None,
        diameters=tanks.diameter.array if tanks.diameter.is_initialized() else None,
        min_volumes=tanks.min_volume.array if tanks.min_volume.is_initialized() else None,
        volume_curves=volume_curves,
        overflows=tanks.overflow.array if tanks.overflow.is_initialized() else None,
        coordinates=_get_coordinates(tanks),
    )


def get_reservoirs(reservoirs: "WaterReservoirEntity", id_mapper: IdMapper) -> ReservoirCollection:
    """Convert reservoir entities to ReservoirCollection.

    :param reservoirs: WaterReservoirEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: ReservoirCollection with reservoir data
    """
    node_names = id_mapper.register_nodes(reservoirs.index.ids, entity_type="reservoir")
    head_factors = (
        reservoirs.head_factor.array if reservoirs.head_factor.is_initialized() else None
    )

    return ReservoirCollection(
        node_names=node_names,
        base_heads=reservoirs.base_head.array,
        head_factors=head_factors,
        coordinates=_get_coordinates(reservoirs),
    )


def get_pipes(pipes: "WaterPipeEntity", id_mapper: IdMapper) -> PipeCollection:
    """Convert pipe entities to PipeCollection.

    :param pipes: WaterPipeEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: PipeCollection with pipe data
    """
    link_names = id_mapper.register_links(pipes.index.ids, entity_type="pipe")
    from_nodes, to_nodes = _get_node_names(pipes, id_mapper)

    # Get lengths - from attribute or calculate from geometry
    if pipes.length.is_initialized():
        lengths = pipes.length.array
    elif pipes.linestring.is_initialized():
        lengths = np.array([pipes.get_single_geometry(i).length for i in range(len(link_names))])
    else:
        lengths = np.full(len(link_names), 100.0)

    return PipeCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        lengths=lengths,
        diameters=pipes.diameter.array,
        roughnesses=pipes.roughness.array,
        minor_losses=pipes.minor_loss.array if pipes.minor_loss.is_initialized() else None,
        check_valves=pipes.check_valve.array if pipes.check_valve.is_initialized() else None,
        statuses=pipes.status.array if pipes.status.is_initialized() else None,
    )


def get_pumps(pumps: "WaterPumpEntity", id_mapper: IdMapper) -> PumpCollection:
    """Convert pump entities to PumpCollection.

    :param pumps: WaterPumpEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: PumpCollection with pump data
    """
    link_names = id_mapper.register_links(pumps.index.ids, entity_type="pump")
    from_nodes, to_nodes = _get_node_names(pumps, id_mapper)
    head_curves = (
        _extract_csr_curves(pumps.head_curve) if pumps.head_curve.is_initialized() else None
    )

    return PumpCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        pump_types=[str(t) for t in pumps.pump_type.array],
        powers=pumps.power.array if pumps.power.is_initialized() else None,
        head_curves=head_curves,
        speeds=pumps.speed.array if pumps.speed.is_initialized() else None,
        statuses=pumps.status.array if pumps.status.is_initialized() else None,
    )


def get_valves(valves: "WaterValveEntity", id_mapper: IdMapper) -> ValveCollection:
    """Convert valve entities to ValveCollection.

    :param valves: WaterValveEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: ValveCollection with valve data
    """
    link_names = id_mapper.register_links(valves.index.ids, entity_type="valve")
    from_nodes, to_nodes = _get_node_names(valves, id_mapper)
    valve_curves = (
        _extract_csr_curves(valves.valve_curve) if valves.valve_curve.is_initialized() else None
    )
    valve_loss_coefficients = (
        valves.valve_loss_coefficient.array
        if valves.valve_loss_coefficient.is_initialized()
        else None
    )

    return ValveCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        valve_types=[str(t) for t in valves.valve_type.array],
        diameters=valves.diameter.array,
        valve_pressures=valves.valve_pressure.array
        if valves.valve_pressure.is_initialized()
        else None,
        valve_flows=valves.valve_flow.array if valves.valve_flow.is_initialized() else None,
        valve_loss_coefficients=valve_loss_coefficients,
        valve_curves=valve_curves,
        minor_losses=valves.minor_loss.array if valves.minor_loss.is_initialized() else None,
    )


def _extract_csr_curves(csr_attribute) -> t.List[t.Optional[np.ndarray]]:
    """Extract individual curve arrays from a CSR attribute.

    CSR (Compressed Sparse Row) attributes store variable-length arrays
    for each entity. This function extracts them into a list of arrays.

    :param csr_attribute: CSR attribute containing curve data
    :return: List of numpy arrays, one per entity (or None if no data)
    """
    csr = csr_attribute.csr
    curves = []

    for i in range(len(csr.row_ptr) - 1):
        start = csr.row_ptr[i]
        end = csr.row_ptr[i + 1]

        if end > start:
            # Extract the curve data for this entity
            curve_data = csr.data[start:end]
            curves.append(curve_data)
        else:
            curves.append(None)

    return curves
