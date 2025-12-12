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


def get_junctions(junctions: "WaterJunctionEntity", id_mapper: IdMapper) -> JunctionCollection:
    """Convert junction entities to JunctionCollection.

    :param junctions: WaterJunctionEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: JunctionCollection with junction data
    """
    movici_ids = junctions.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="junction")

    elevations = junctions.elevation.array
    base_demands = junctions.base_demand.array

    # Get demand factors if available
    demand_factors = None
    if junctions.demand_factor.is_initialized():
        demand_factors = junctions.demand_factor.array

    # Get coordinates if available
    coordinates = None
    if junctions.x.is_initialized() and junctions.y.is_initialized():
        coordinates = np.column_stack([junctions.x.array, junctions.y.array])

    return JunctionCollection(
        node_names=node_names,
        elevations=elevations,
        base_demands=base_demands,
        demand_factors=demand_factors,
        coordinates=coordinates,
    )


def get_tanks(tanks: "WaterTankEntity", id_mapper: IdMapper) -> TankCollection:
    """Convert tank entities to TankCollection.

    :param tanks: WaterTankEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: TankCollection with tank data
    """
    movici_ids = tanks.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="tank")

    elevations = tanks.elevation.array
    init_levels = tanks.level.array  # level is INIT|PUB, initial value

    # Cylindrical tank attributes (optional)
    diameters = tanks.diameter.array if tanks.diameter.is_initialized() else None
    min_levels = tanks.min_level.array if tanks.min_level.is_initialized() else None
    max_levels = tanks.max_level.array if tanks.max_level.is_initialized() else None

    # Volume curve tank attributes (optional)
    min_volumes = tanks.min_volume.array if tanks.min_volume.is_initialized() else None

    # Volume curves as CSR data
    volume_curves = None
    if tanks.volume_curve.is_initialized():
        volume_curves = _extract_csr_curves(tanks.volume_curve)

    # Overflow flag
    overflows = tanks.overflow.array if tanks.overflow.is_initialized() else None

    # Coordinates
    coordinates = None
    if tanks.x.is_initialized() and tanks.y.is_initialized():
        coordinates = np.column_stack([tanks.x.array, tanks.y.array])

    return TankCollection(
        node_names=node_names,
        elevations=elevations,
        init_levels=init_levels,
        min_levels=min_levels,
        max_levels=max_levels,
        diameters=diameters,
        min_volumes=min_volumes,
        volume_curves=volume_curves,
        overflows=overflows,
        coordinates=coordinates,
    )


def get_reservoirs(reservoirs: "WaterReservoirEntity", id_mapper: IdMapper) -> ReservoirCollection:
    """Convert reservoir entities to ReservoirCollection.

    :param reservoirs: WaterReservoirEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: ReservoirCollection with reservoir data
    """
    movici_ids = reservoirs.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="reservoir")

    base_heads = reservoirs.base_head.array

    # Get head factors if available
    head_factors = None
    if reservoirs.head_factor.is_initialized():
        head_factors = reservoirs.head_factor.array

    # Coordinates
    coordinates = None
    if reservoirs.x.is_initialized() and reservoirs.y.is_initialized():
        coordinates = np.column_stack([reservoirs.x.array, reservoirs.y.array])

    return ReservoirCollection(
        node_names=node_names,
        base_heads=base_heads,
        head_factors=head_factors,
        coordinates=coordinates,
    )


def get_pipes(pipes: "WaterPipeEntity", id_mapper: IdMapper) -> PipeCollection:
    """Convert pipe entities to PipeCollection.

    :param pipes: WaterPipeEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: PipeCollection with pipe data
    """
    movici_ids = pipes.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="pipe")

    # Get from/to node names from IDs
    from_node_ids = pipes.from_node_id.array
    to_node_ids = pipes.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    # Get lengths - from attribute or calculate from geometry
    if pipes.length.is_initialized():
        lengths = pipes.length.array
    elif pipes.linestring.is_initialized():
        lengths = np.zeros(len(link_names))
        for i in range(len(link_names)):
            geom = pipes.get_single_geometry(i)
            lengths[i] = geom.length
    else:
        # Default length if no geometry
        lengths = np.full(len(link_names), 100.0)

    diameters = pipes.diameter.array
    roughnesses = pipes.roughness.array

    # Optional attributes
    minor_losses = pipes.minor_loss.array if pipes.minor_loss.is_initialized() else None
    check_valves = pipes.check_valve.array if pipes.check_valve.is_initialized() else None

    # Status as boolean
    statuses = None
    if pipes.status.is_initialized():
        statuses = pipes.status.array

    return PipeCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        lengths=lengths,
        diameters=diameters,
        roughnesses=roughnesses,
        minor_losses=minor_losses,
        check_valves=check_valves,
        statuses=statuses,
    )


def get_pumps(pumps: "WaterPumpEntity", id_mapper: IdMapper) -> PumpCollection:
    """Convert pump entities to PumpCollection.

    :param pumps: WaterPumpEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: PumpCollection with pump data
    """
    movici_ids = pumps.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="pump")

    # Get from/to node names
    from_node_ids = pumps.from_node_id.array
    to_node_ids = pumps.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    # Pump types as strings
    pump_types = [str(t) for t in pumps.pump_type.array]

    # Power for power pumps
    powers = pumps.power.array if pumps.power.is_initialized() else None

    # Head curves as CSR data for head pumps
    head_curves = None
    if pumps.head_curve.is_initialized():
        head_curves = _extract_csr_curves(pumps.head_curve)

    # Speeds
    speeds = pumps.speed.array if pumps.speed.is_initialized() else None

    # Status as boolean
    statuses = None
    if pumps.status.is_initialized():
        statuses = pumps.status.array

    return PumpCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        pump_types=pump_types,
        powers=powers,
        head_curves=head_curves,
        speeds=speeds,
        statuses=statuses,
    )


def get_valves(valves: "WaterValveEntity", id_mapper: IdMapper) -> ValveCollection:
    """Convert valve entities to ValveCollection.

    :param valves: WaterValveEntity instance
    :param id_mapper: IdMapper for tracking IDs
    :return: ValveCollection with valve data
    """
    movici_ids = valves.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="valve")

    # Get from/to node names
    from_node_ids = valves.from_node_id.array
    to_node_ids = valves.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    # Valve types as strings
    valve_types = [str(t) for t in valves.valve_type.array]
    diameters = valves.diameter.array

    # Type-specific settings
    valve_pressures = valves.valve_pressure.array if valves.valve_pressure.is_initialized() else None
    valve_flows = valves.valve_flow.array if valves.valve_flow.is_initialized() else None
    valve_loss_coefficients = (
        valves.valve_loss_coefficient.array if valves.valve_loss_coefficient.is_initialized() else None
    )

    # Valve curves as CSR data for GPV
    valve_curves = None
    if valves.valve_curve.is_initialized():
        valve_curves = _extract_csr_curves(valves.valve_curve)

    # Minor losses
    minor_losses = valves.minor_loss.array if valves.minor_loss.is_initialized() else None

    return ValveCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        valve_types=valve_types,
        diameters=diameters,
        valve_pressures=valve_pressures,
        valve_flows=valve_flows,
        valve_loss_coefficients=valve_loss_coefficients,
        valve_curves=valve_curves,
        minor_losses=minor_losses,
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
