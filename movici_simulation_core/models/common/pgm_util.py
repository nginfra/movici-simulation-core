"""Utility functions for power grid model integration.

This module provides functions to extract data from Movici entity groups
and convert them to power-grid-model collection objects.
"""

from __future__ import annotations

import typing as t

import numpy as np

from movici_simulation_core.integrations.pgm.collections import (
    FaultCollection,
    GeneratorCollection,
    LineCollection,
    LoadCollection,
    NodeCollection,
    PowerSensorCollection,
    ShuntCollection,
    SourceCollection,
    TransformerCollection,
    VoltageSensorCollection,
)

if t.TYPE_CHECKING:
    from movici_simulation_core.models.power_grid_calculation.dataset import (
        ElectricalFaultEntity,
        ElectricalGeneratorEntity,
        ElectricalLineEntity,
        ElectricalLoadEntity,
        ElectricalNodeEntity,
        ElectricalPowerSensorEntity,
        ElectricalShuntEntity,
        ElectricalSourceEntity,
        ElectricalTransformerEntity,
        ElectricalVoltageSensorEntity,
    )


def get_optional_array(attr, default: t.Any = 0, dtype: np.dtype = np.float64) -> np.ndarray:
    """Get array from attribute, using default if not initialized.

    :param attr: Attribute to extract array from.
    :param default: Default value if attribute not initialized.
    :param dtype: Data type for the array.
    :returns: Numpy array with attribute data or filled with default.
    """
    if attr.is_initialized():
        return attr.array
    return np.full(len(attr), default, dtype=dtype)


def get_status_array(attr, default: int = 1) -> np.ndarray:
    """Get status array with default value of 1 (enabled).

    :param attr: Status attribute.
    :param default: Default status value.
    :returns: Status array as int8.
    """
    if attr.is_initialized():
        return attr.array.astype(np.int8)
    return np.full(len(attr), default, dtype=np.int8)


def get_nodes(entity: "ElectricalNodeEntity") -> NodeCollection:
    """Extract node collection from entity group.

    :param entity: Electrical node entity group.
    :returns: NodeCollection for power-grid-model.
    """
    return NodeCollection(
        ids=entity.index.ids,
        u_rated=entity.rated_voltage.array,
    )


def get_lines(entity: "ElectricalLineEntity") -> LineCollection:
    """Extract line collection from entity group.

    :param entity: Electrical line entity group.
    :returns: LineCollection for power-grid-model.
    """
    return LineCollection(
        ids=entity.index.ids,
        from_node=entity.from_node_id.array,
        to_node=entity.to_node_id.array,
        from_status=get_status_array(entity.from_status),
        to_status=get_status_array(entity.to_status),
        r1=entity.resistance.array,
        x1=entity.reactance.array,
        c1=entity.capacitance.array,
        tan1=entity.tan_delta.array,
        i_n=get_optional_array(entity.rated_current, default=np.inf),
    )


def get_transformers(entity: "ElectricalTransformerEntity") -> TransformerCollection:
    """Extract transformer collection from entity group.

    :param entity: Electrical transformer entity group.
    :returns: TransformerCollection for power-grid-model.
    """
    return TransformerCollection(
        ids=entity.index.ids,
        from_node=entity.from_node_id.array,
        to_node=entity.to_node_id.array,
        from_status=get_status_array(entity.from_status),
        to_status=get_status_array(entity.to_status),
        u1=entity.primary_voltage.array,
        u2=entity.secondary_voltage.array,
        sn=entity.rated_power.array,
        uk=entity.short_circuit_voltage.array,
        pk=entity.copper_loss.array,
        i0=entity.no_load_current.array,
        p0=entity.no_load_loss.array,
        winding_from=get_optional_array(entity.winding_from, default=1, dtype=np.int8),  # wye_n
        winding_to=get_optional_array(entity.winding_to, default=1, dtype=np.int8),  # wye_n
        clock=get_optional_array(entity.clock, default=0, dtype=np.int8),
        tap_side=get_optional_array(entity.tap_side, default=0, dtype=np.int8),
        tap_pos=get_optional_array(entity.tap_position, default=0, dtype=np.int8),
        tap_min=get_optional_array(entity.tap_min, default=0, dtype=np.int8),
        tap_max=get_optional_array(entity.tap_max, default=0, dtype=np.int8),
        tap_nom=get_optional_array(entity.tap_nom, default=0, dtype=np.int8),
        tap_size=get_optional_array(entity.tap_size, default=0.0),
    )


def get_loads(entity: "ElectricalLoadEntity") -> LoadCollection:
    """Extract load collection from entity group.

    :param entity: Electrical load entity group.
    :returns: LoadCollection for power-grid-model.
    """
    return LoadCollection(
        ids=entity.index.ids,
        node=entity.node_id.array,
        status=get_status_array(entity.status),
        type=get_optional_array(entity.load_type, default=0, dtype=np.int8),  # const_power
        p_specified=entity.p_specified.array,
        q_specified=entity.q_specified.array,
    )


def get_generators(entity: "ElectricalGeneratorEntity") -> GeneratorCollection:
    """Extract generator collection from entity group.

    :param entity: Electrical generator entity group.
    :returns: GeneratorCollection for power-grid-model.
    """
    return GeneratorCollection(
        ids=entity.index.ids,
        node=entity.node_id.array,
        status=get_status_array(entity.status),
        type=get_optional_array(entity.load_type, default=0, dtype=np.int8),
        p_specified=entity.p_specified.array,
        q_specified=entity.q_specified.array,
    )


def get_sources(entity: "ElectricalSourceEntity") -> SourceCollection:
    """Extract source collection from entity group.

    :param entity: Electrical source entity group.
    :returns: SourceCollection for power-grid-model.
    """
    return SourceCollection(
        ids=entity.index.ids,
        node=entity.node_id.array,
        status=get_status_array(entity.status),
        u_ref=entity.reference_voltage.array,
        u_ref_angle=get_optional_array(entity.reference_angle, default=0.0),
        sk=get_optional_array(entity.short_circuit_power, default=1e10),
        rx_ratio=get_optional_array(entity.rx_ratio, default=0.1),
    )


def get_shunts(entity: "ElectricalShuntEntity") -> ShuntCollection:
    """Extract shunt collection from entity group.

    :param entity: Electrical shunt entity group.
    :returns: ShuntCollection for power-grid-model.
    """
    return ShuntCollection(
        ids=entity.index.ids,
        node=entity.node_id.array,
        status=get_status_array(entity.status),
        g1=entity.conductance.array,
        b1=entity.susceptance.array,
    )


def get_voltage_sensors(entity: "ElectricalVoltageSensorEntity") -> VoltageSensorCollection:
    """Extract voltage sensor collection from entity group.

    :param entity: Electrical voltage sensor entity group.
    :returns: VoltageSensorCollection for power-grid-model.
    """
    return VoltageSensorCollection(
        ids=entity.index.ids,
        measured_object=entity.node_id.array,
        u_measured=entity.measured_voltage.array,
        u_sigma=entity.voltage_sigma.array,
    )


def get_power_sensors(entity: "ElectricalPowerSensorEntity") -> PowerSensorCollection:
    """Extract power sensor collection from entity group.

    :param entity: Electrical power sensor entity group.
    :returns: PowerSensorCollection for power-grid-model.
    """
    return PowerSensorCollection(
        ids=entity.index.ids,
        measured_object=entity.measured_object_id.array,
        measured_terminal_type=entity.measured_terminal_type.array,
        p_measured=entity.measured_active_power.array,
        q_measured=entity.measured_reactive_power.array,
        power_sigma=entity.power_sigma.array,
    )


def get_faults(entity: "ElectricalFaultEntity") -> FaultCollection:
    """Extract fault collection from entity group.

    :param entity: Electrical fault entity group.
    :returns: FaultCollection for power-grid-model.
    """
    return FaultCollection(
        ids=entity.index.ids,
        status=get_status_array(entity.status),
        fault_type=entity.fault_type.array,
        fault_phase=get_optional_array(entity.fault_phase, default=0, dtype=np.int8),
        fault_object=entity.fault_object_id.array,
        r_f=get_optional_array(entity.fault_resistance, default=0.0),
        x_f=get_optional_array(entity.fault_reactance, default=0.0),
    )
