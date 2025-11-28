"""Utility functions for converting Movici entities to WNTR collections"""

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
    """Convert junction entities to JunctionCollection

        :param junctions: WaterJunctionEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: JunctionCollection
    """
    movici_ids = junctions.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="junction")

    elevations = junctions.elevation.array
    base_demands = junctions.base_demand.array

    # Get demand patterns if available
    demand_patterns = None
    if junctions.demand_pattern.has_data():
        demand_patterns = [str(p) if p else None for p in junctions.demand_pattern.array]

    # Get coordinates if available
    coordinates = None
    if junctions.x.is_initialized() and junctions.y.is_initialized():
        coordinates = np.column_stack([junctions.x.array, junctions.y.array])

    return JunctionCollection(
        node_names=node_names,
        elevations=elevations,
        base_demands=base_demands,
        demand_patterns=demand_patterns,
        coordinates=coordinates,
    )


def get_tanks(tanks: "WaterTankEntity", id_mapper: IdMapper) -> TankCollection:
    """Convert tank entities to TankCollection

        :param tanks: WaterTankEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: TankCollection
    """
    movici_ids = tanks.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="tank")

    elevations = tanks.elevation.array
    init_levels = tanks.init_level.array
    min_levels = tanks.min_level.array
    max_levels = tanks.max_level.array
    diameters = tanks.diameter.array

    # Optional attributes
    min_volumes = tanks.min_volume.array if tanks.min_volume.has_data() else None
    volume_curves = None
    if tanks.volume_curve.has_data():
        volume_curves = [str(c) if c else None for c in tanks.volume_curve.array]

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
        coordinates=coordinates,
    )


def get_reservoirs(reservoirs: "WaterReservoirEntity", id_mapper: IdMapper) -> ReservoirCollection:
    """Convert reservoir entities to ReservoirCollection

        :param reservoirs: WaterReservoirEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: ReservoirCollection
    """
    movici_ids = reservoirs.index.ids
    node_names = id_mapper.register_nodes(movici_ids, entity_type="reservoir")

    heads = reservoirs.head.array

    # Get head patterns if available
    head_patterns = None
    if reservoirs.head_pattern.has_data():
        head_patterns = [str(p) if p else None for p in reservoirs.head_pattern.array]

    # Coordinates
    coordinates = None
    if reservoirs.x.is_initialized() and reservoirs.y.is_initialized():
        coordinates = np.column_stack([reservoirs.x.array, reservoirs.y.array])

    return ReservoirCollection(
        node_names=node_names,
        heads=heads,
        head_patterns=head_patterns,
        coordinates=coordinates,
    )


def get_pipes(pipes: "WaterPipeEntity", id_mapper: IdMapper) -> PipeCollection:
    """Convert pipe entities to PipeCollection

        :param pipes: WaterPipeEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: PipeCollection
    """
    movici_ids = pipes.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="pipe")

    # Get from/to node names from IDs
    from_node_ids = pipes.from_node_id.array
    to_node_ids = pipes.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    # Calculate lengths from geometry if available
    lengths = np.zeros(len(link_names))
    if pipes.linestring.is_initialized():
        for i in range(len(link_names)):
            geom = pipes.get_single_geometry(i)
            lengths[i] = geom.length
    else:
        # Default length if no geometry
        lengths[:] = 100.0

    diameters = pipes.diameter.array
    roughnesses = pipes.roughness.array

    # Optional attributes
    minor_losses = pipes.minor_loss.array if pipes.minor_loss.has_data() else None

    statuses = None
    if pipes.initial_status.has_data():
        statuses = ["OPEN" if s == 1 else "CLOSED" for s in pipes.initial_status.array]

    return PipeCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        lengths=lengths,
        diameters=diameters,
        roughnesses=roughnesses,
        minor_losses=minor_losses,
        statuses=statuses,
    )


def get_pumps(pumps: "WaterPumpEntity", id_mapper: IdMapper) -> PumpCollection:
    """Convert pump entities to PumpCollection

        :param pumps: WaterPumpEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: PumpCollection
    """
    movici_ids = pumps.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="pump")

    # Get from/to node names
    from_node_ids = pumps.from_node_id.array
    to_node_ids = pumps.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    # Pump types
    pump_types = [str(t) for t in pumps.pump_type.array]

    # Optional attributes
    pump_curves = None
    if pumps.pump_curve.has_data():
        pump_curves = [str(c) if c else None for c in pumps.pump_curve.array]

    powers = pumps.power.array if pumps.power.has_data() else None
    speeds = pumps.speed.array if pumps.speed.has_data() else None

    statuses = None
    if pumps.status.has_data():
        statuses = ["OPEN" if s == 1 else "CLOSED" for s in pumps.status.array]

    return PumpCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        pump_types=pump_types,
        pump_curves=pump_curves,
        powers=powers,
        speeds=speeds,
        statuses=statuses,
    )


def get_valves(valves: "WaterValveEntity", id_mapper: IdMapper) -> ValveCollection:
    """Convert valve entities to ValveCollection

        :param valves: WaterValveEntity instance
        :param id_mapper: IdMapper for tracking IDs

    :return: ValveCollection
    """
    movici_ids = valves.index.ids
    link_names = id_mapper.register_links(movici_ids, entity_type="valve")

    # Get from/to node names
    from_node_ids = valves.from_node_id.array
    to_node_ids = valves.to_node_id.array
    from_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in from_node_ids]
    to_nodes = [id_mapper.get_wntr_name(int(nid)) for nid in to_node_ids]

    valve_types = [str(t) for t in valves.valve_type.array]
    diameters = valves.diameter.array
    settings = valves.setting.array

    # Optional attributes
    minor_losses = valves.minor_loss.array if valves.minor_loss.has_data() else None

    statuses = None
    if valves.status.has_data():
        statuses = ["OPEN" if s == 1 else "CLOSED" for s in valves.status.array]

    return ValveCollection(
        link_names=link_names,
        from_nodes=from_nodes,
        to_nodes=to_nodes,
        valve_types=valve_types,
        diameters=diameters,
        settings=settings,
        minor_losses=minor_losses,
        statuses=statuses,
    )
