"""Entity definitions for power grid calculation model.

This module defines EntityGroup subclasses for electrical network components:
nodes, lines, transformers, loads, generators, sources, and sensors.
"""

import dataclasses

from movici_simulation_core.attributes import (
    Connection_ToId,
)
from movici_simulation_core.core.attribute import INIT, OPT, PUB, SUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.models.common.entity_groups import LinkEntity, PointEntity

from .attributes import (
    Electrical_ActivePower,
    Electrical_ActivePowerSpecified,
    Electrical_AngleMeasurementType,
    Electrical_Capacitance,
    Electrical_Clock,
    Electrical_Clock12,
    Electrical_Clock13,
    Electrical_Conductance,
    Electrical_CopperLoss,
    Electrical_CopperLoss12,
    Electrical_CopperLoss13,
    Electrical_CopperLoss23,
    Electrical_Current1,
    Electrical_Current2,
    Electrical_Current3,
    Electrical_CurrentAngleSigma,
    Electrical_CurrentFrom,
    Electrical_CurrentSigma,
    Electrical_CurrentTo,
    Electrical_FaultCurrent,
    Electrical_FaultCurrentAngle,
    Electrical_FaultPhase,
    Electrical_FaultReactance,
    Electrical_FaultResistance,
    Electrical_FaultType,
    Electrical_FromStatus,
    Electrical_LineDropCompensationR,
    Electrical_LineDropCompensationX,
    Electrical_Loading,
    Electrical_LoadType,
    Electrical_MeasuredActivePower,
    Electrical_MeasuredCurrent,
    Electrical_MeasuredCurrentAngle,
    Electrical_MeasuredReactivePower,
    Electrical_MeasuredTerminalType,
    Electrical_MeasuredVoltage,
    Electrical_Node1Id,
    Electrical_Node2Id,
    Electrical_Node3Id,
    Electrical_NoLoadCurrent,
    Electrical_NoLoadLoss,
    Electrical_Power1,
    Electrical_Power2,
    Electrical_Power3,
    Electrical_PowerFrom,
    Electrical_PowerSigma,
    Electrical_PowerTo,
    Electrical_PrimaryVoltage,
    Electrical_RatedCurrent,
    Electrical_RatedPower,
    Electrical_RatedPower1,
    Electrical_RatedPower2,
    Electrical_RatedPower3,
    Electrical_RatedVoltage,
    Electrical_Reactance,
    Electrical_ReactivePower,
    Electrical_ReactivePower1,
    Electrical_ReactivePower2,
    Electrical_ReactivePower3,
    Electrical_ReactivePowerFrom,
    Electrical_ReactivePowerSpecified,
    Electrical_ReactivePowerTo,
    Electrical_ReferenceAngle,
    Electrical_ReferenceVoltage,
    Electrical_RegulatorControlSide,
    Electrical_Resistance,
    Electrical_RXRatio,
    Electrical_SecondaryVoltage,
    Electrical_ShortCircuitPower,
    Electrical_ShortCircuitVoltage,
    Electrical_ShortCircuitVoltage12,
    Electrical_ShortCircuitVoltage13,
    Electrical_ShortCircuitVoltage23,
    Electrical_Status,
    Electrical_Status1,
    Electrical_Status2,
    Electrical_Status3,
    Electrical_Susceptance,
    Electrical_TanDelta,
    Electrical_TapMax,
    Electrical_TapMin,
    Electrical_TapNom,
    Electrical_TapPosition,
    Electrical_TapSide,
    Electrical_TapSize,
    Electrical_TertiaryVoltage,
    Electrical_ToStatus,
    Electrical_Voltage,
    Electrical_VoltageAngle,
    Electrical_VoltageBand,
    Electrical_VoltagePU,
    Electrical_VoltageSetpoint,
    Electrical_VoltageSigma,
    Electrical_Winding1,
    Electrical_Winding2,
    Electrical_Winding3,
    Electrical_WindingFrom,
    Electrical_WindingTo,
)


class ElectricalNodeEntity(PointEntity):
    """Electrical network node (bus).

    Represents a connection point in the electrical network where
    components are connected.
    """

    __entity_name__ = "electrical_node_entities"
    __exclude__ = ["x", "y", "z", "reference"]

    # Input attributes
    rated_voltage = field(Electrical_RatedVoltage, flags=INIT)
    status = field(Electrical_Status, flags=OPT)

    # Output attributes
    voltage_pu = field(Electrical_VoltagePU, flags=PUB)
    voltage_angle = field(Electrical_VoltageAngle, flags=PUB)
    voltage = field(Electrical_Voltage, flags=PUB)
    active_power = field(Electrical_ActivePower, flags=PUB)
    reactive_power = field(Electrical_ReactivePower, flags=PUB)


class ElectricalVirtualNodeEntity(EntityGroup):
    """External grid connection node (virtual bus).

    Represents the external grid connection point where sources attach.
    These nodes are merged with regular nodes during network building,
    similar to how virtual_node_entities are handled in traffic assignment.

    Unlike regular nodes, virtual nodes may not have geometry as they
    represent conceptual connection points to the external grid.
    """

    __entity_name__ = "electrical_virtual_node_entities"

    # Input attributes
    rated_voltage = field(Electrical_RatedVoltage, flags=INIT)
    status = field(Electrical_Status, flags=OPT)

    # Output attributes (same as regular nodes)
    voltage_pu = field(Electrical_VoltagePU, flags=PUB)
    voltage_angle = field(Electrical_VoltageAngle, flags=PUB)
    voltage = field(Electrical_Voltage, flags=PUB)
    active_power = field(Electrical_ActivePower, flags=PUB)
    reactive_power = field(Electrical_ReactivePower, flags=PUB)


class ElectricalLineEntity(LinkEntity):
    """Electrical transmission/distribution line.

    Represents a power line connecting two nodes with impedance
    characteristics (resistance, reactance, capacitance).
    """

    __entity_name__ = "electrical_line_entities"
    __exclude__ = ["_linestring2d", "_linestring3d", "reference"]

    # Input attributes (topology inherited from LinkEntity)
    resistance = field(Electrical_Resistance, flags=INIT)
    reactance = field(Electrical_Reactance, flags=INIT)
    capacitance = field(Electrical_Capacitance, flags=INIT)
    tan_delta = field(Electrical_TanDelta, flags=INIT)
    rated_current = field(Electrical_RatedCurrent, flags=OPT)
    from_status = field(Electrical_FromStatus, flags=OPT)
    to_status = field(Electrical_ToStatus, flags=OPT)

    # Output attributes
    current_from = field(Electrical_CurrentFrom, flags=PUB)
    current_to = field(Electrical_CurrentTo, flags=PUB)
    power_from = field(Electrical_PowerFrom, flags=PUB)
    power_to = field(Electrical_PowerTo, flags=PUB)
    reactive_power_from = field(Electrical_ReactivePowerFrom, flags=PUB)
    reactive_power_to = field(Electrical_ReactivePowerTo, flags=PUB)
    loading = field(Electrical_Loading, flags=PUB)


class ElectricalCableEntity(LinkEntity):
    """Electrical cable (underground line).

    Represents an underground cable with the same electrical characteristics
    as overhead lines. Treated identically to lines in power flow calculations.
    """

    __entity_name__ = "electrical_cable_entities"
    __exclude__ = ["_linestring2d", "_linestring3d", "reference"]

    # Input attributes (same as ElectricalLineEntity)
    resistance = field(Electrical_Resistance, flags=INIT)
    reactance = field(Electrical_Reactance, flags=INIT)
    capacitance = field(Electrical_Capacitance, flags=INIT)
    tan_delta = field(Electrical_TanDelta, flags=INIT)
    rated_current = field(Electrical_RatedCurrent, flags=OPT)
    from_status = field(Electrical_FromStatus, flags=OPT)
    to_status = field(Electrical_ToStatus, flags=OPT)

    # Output attributes
    current_from = field(Electrical_CurrentFrom, flags=PUB)
    current_to = field(Electrical_CurrentTo, flags=PUB)
    power_from = field(Electrical_PowerFrom, flags=PUB)
    power_to = field(Electrical_PowerTo, flags=PUB)
    reactive_power_from = field(Electrical_ReactivePowerFrom, flags=PUB)
    reactive_power_to = field(Electrical_ReactivePowerTo, flags=PUB)
    loading = field(Electrical_Loading, flags=PUB)


class ElectricalLinkEntity(LinkEntity):
    """Zero-impedance electrical connection.

    Represents a zero-impedance connection between nodes, typically
    connecting virtual nodes to the main network. Converted to
    low-impedance lines for PGM calculations, similar to how
    virtual_link_entities are handled in traffic assignment.
    """

    __entity_name__ = "electrical_link_entities"
    __exclude__ = ["_linestring2d", "_linestring3d", "reference"]

    # Only topology, no electrical parameters
    # from_node_id and to_node_id inherited from LinkEntity
    from_status = field(Electrical_FromStatus, flags=OPT)
    to_status = field(Electrical_ToStatus, flags=OPT)

    # Output attributes (same as lines)
    current_from = field(Electrical_CurrentFrom, flags=PUB)
    current_to = field(Electrical_CurrentTo, flags=PUB)
    power_from = field(Electrical_PowerFrom, flags=PUB)
    power_to = field(Electrical_PowerTo, flags=PUB)
    reactive_power_from = field(Electrical_ReactivePowerFrom, flags=PUB)
    reactive_power_to = field(Electrical_ReactivePowerTo, flags=PUB)
    loading = field(Electrical_Loading, flags=PUB)


class ElectricalTransformerEntity(LinkEntity):
    """Two-winding power transformer.

    Represents a transformer connecting two nodes with voltage
    transformation and tap changing capability.
    """

    __entity_name__ = "electrical_transformer_entities"
    __exclude__ = ["_linestring2d", "_linestring3d", "reference"]

    # Input attributes
    primary_voltage = field(Electrical_PrimaryVoltage, flags=INIT)
    secondary_voltage = field(Electrical_SecondaryVoltage, flags=INIT)
    rated_power = field(Electrical_RatedPower, flags=INIT)
    short_circuit_voltage = field(Electrical_ShortCircuitVoltage, flags=INIT)
    copper_loss = field(Electrical_CopperLoss, flags=INIT)
    no_load_current = field(Electrical_NoLoadCurrent, flags=INIT)
    no_load_loss = field(Electrical_NoLoadLoss, flags=INIT)
    winding_from = field(Electrical_WindingFrom, flags=OPT)
    winding_to = field(Electrical_WindingTo, flags=OPT)
    clock = field(Electrical_Clock, flags=OPT)
    tap_side = field(Electrical_TapSide, flags=OPT)
    tap_position = field(Electrical_TapPosition, flags=OPT)
    tap_min = field(Electrical_TapMin, flags=OPT)
    tap_max = field(Electrical_TapMax, flags=OPT)
    tap_nom = field(Electrical_TapNom, flags=OPT)
    tap_size = field(Electrical_TapSize, flags=OPT)
    from_status = field(Electrical_FromStatus, flags=OPT)
    to_status = field(Electrical_ToStatus, flags=OPT)

    # Output attributes
    current_from = field(Electrical_CurrentFrom, flags=PUB)
    current_to = field(Electrical_CurrentTo, flags=PUB)
    power_from = field(Electrical_PowerFrom, flags=PUB)
    power_to = field(Electrical_PowerTo, flags=PUB)
    loading = field(Electrical_Loading, flags=PUB)


class ElectricalLoadEntity(EntityGroup):
    """Electrical load (consumer).

    Represents a power consumer connected to a node. Load values
    can be updated dynamically during simulation.
    """

    __entity_name__ = "electrical_load_entities"

    # Input attributes
    node_id = field(Connection_ToId, flags=INIT)
    status = field(Electrical_Status, flags=OPT)
    load_type = field(Electrical_LoadType, flags=OPT)

    # Subscribable attributes (dynamic updates)
    p_specified = field(Electrical_ActivePowerSpecified, flags=SUB)
    q_specified = field(Electrical_ReactivePowerSpecified, flags=SUB)


class ElectricalGeneratorEntity(EntityGroup):
    """Electrical generator.

    Represents a power generator connected to a node. Generation
    values can be updated dynamically during simulation.
    """

    __entity_name__ = "electrical_generator_entities"

    # Input attributes
    node_id = field(Connection_ToId, flags=INIT)
    status = field(Electrical_Status, flags=OPT)
    load_type = field(Electrical_LoadType, flags=OPT)  # Reuse load_type enum

    # Subscribable attributes (dynamic updates)
    p_specified = field(Electrical_ActivePowerSpecified, flags=SUB)
    q_specified = field(Electrical_ReactivePowerSpecified, flags=SUB)


class ElectricalSourceEntity(EntityGroup):
    """External grid connection (slack bus).

    Represents a connection to the external grid that provides
    the voltage reference for power flow calculations.
    """

    __entity_name__ = "electrical_source_entities"

    # Input attributes
    node_id = field(Connection_ToId, flags=INIT)
    status = field(Electrical_Status, flags=OPT)
    reference_voltage = field(Electrical_ReferenceVoltage, flags=INIT)
    reference_angle = field(Electrical_ReferenceAngle, flags=OPT)
    short_circuit_power = field(Electrical_ShortCircuitPower, flags=OPT)
    rx_ratio = field(Electrical_RXRatio, flags=OPT)


class ElectricalShuntEntity(EntityGroup):
    """Shunt element (capacitor/reactor bank).

    Represents a shunt-connected element for reactive power compensation.
    """

    __entity_name__ = "electrical_shunt_entities"

    # Input attributes
    node_id = field(Connection_ToId, flags=INIT)
    status = field(Electrical_Status, flags=OPT)
    conductance = field(Electrical_Conductance, flags=INIT)
    susceptance = field(Electrical_Susceptance, flags=INIT)


class ElectricalVoltageSensorEntity(EntityGroup):
    """Voltage sensor for state estimation.

    Provides voltage measurements for state estimation calculations.
    """

    __entity_name__ = "electrical_voltage_sensor_entities"

    # Input attributes
    node_id = field(Connection_ToId, flags=INIT)
    voltage_sigma = field(Electrical_VoltageSigma, flags=INIT)

    # Subscribable attributes (measurement updates)
    measured_voltage = field(Electrical_MeasuredVoltage, flags=SUB)


class ElectricalPowerSensorEntity(EntityGroup):
    """Power sensor for state estimation.

    Provides power measurements for state estimation calculations.
    """

    __entity_name__ = "electrical_power_sensor_entities"

    # Input attributes
    measured_object_id = field(Connection_ToId, flags=INIT)
    measured_terminal_type = field(Electrical_MeasuredTerminalType, flags=INIT)
    power_sigma = field(Electrical_PowerSigma, flags=INIT)

    # Subscribable attributes (measurement updates)
    measured_active_power = field(Electrical_MeasuredActivePower, flags=SUB)
    measured_reactive_power = field(Electrical_MeasuredReactivePower, flags=SUB)


class ElectricalCurrentSensorEntity(EntityGroup):
    """Current sensor for state estimation.

    Provides current measurements for state estimation calculations.
    PGM component: sym_current_sensor.
    """

    __entity_name__ = "electrical_current_sensor_entities"

    # Input attributes
    measured_object_id = field(Connection_ToId, flags=INIT)
    measured_terminal_type = field(Electrical_MeasuredTerminalType, flags=INIT)
    current_sigma = field(Electrical_CurrentSigma, flags=INIT)
    angle_measurement_type = field(Electrical_AngleMeasurementType, flags=INIT)
    current_angle_sigma = field(Electrical_CurrentAngleSigma, flags=INIT)

    # Subscribable attributes (measurement updates)
    measured_current = field(Electrical_MeasuredCurrent, flags=SUB)
    measured_current_angle = field(Electrical_MeasuredCurrentAngle, flags=SUB)


class ElectricalFaultEntity(EntityGroup):
    """Fault definition for short-circuit analysis.

    Defines fault location and characteristics for short-circuit studies.
    """

    __entity_name__ = "electrical_fault_entities"

    # Input attributes
    fault_object_id = field(Connection_ToId, flags=INIT)  # Node or branch ID
    status = field(Electrical_Status, flags=OPT)
    fault_type = field(Electrical_FaultType, flags=INIT)
    fault_phase = field(Electrical_FaultPhase, flags=OPT)
    fault_resistance = field(Electrical_FaultResistance, flags=OPT)
    fault_reactance = field(Electrical_FaultReactance, flags=OPT)

    # Output attributes (short-circuit results)
    fault_current = field(Electrical_FaultCurrent, flags=PUB)
    fault_current_angle = field(Electrical_FaultCurrentAngle, flags=PUB)


class ElectricalThreeWindingTransformerEntity(EntityGroup):
    """Three-winding power transformer (Branch3).

    Connects three nodes at potentially different voltage levels.
    PGM component: three_winding_transformer.
    """

    __entity_name__ = "electrical_three_winding_transformer_entities"

    # Node connections (3 sides)
    node_1_id = field(Electrical_Node1Id, flags=INIT)
    node_2_id = field(Electrical_Node2Id, flags=INIT)
    node_3_id = field(Electrical_Node3Id, flags=INIT)

    # Per-side status
    status_1 = field(Electrical_Status1, flags=OPT)
    status_2 = field(Electrical_Status2, flags=OPT)
    status_3 = field(Electrical_Status3, flags=OPT)

    # Voltage per winding
    primary_voltage = field(Electrical_PrimaryVoltage, flags=INIT)
    secondary_voltage = field(Electrical_SecondaryVoltage, flags=INIT)
    tertiary_voltage = field(Electrical_TertiaryVoltage, flags=INIT)

    # Per-winding rated power
    rated_power_1 = field(Electrical_RatedPower1, flags=INIT)
    rated_power_2 = field(Electrical_RatedPower2, flags=INIT)
    rated_power_3 = field(Electrical_RatedPower3, flags=INIT)

    # Per-pair short circuit voltage and copper loss
    short_circuit_voltage_12 = field(Electrical_ShortCircuitVoltage12, flags=INIT)
    short_circuit_voltage_13 = field(Electrical_ShortCircuitVoltage13, flags=INIT)
    short_circuit_voltage_23 = field(Electrical_ShortCircuitVoltage23, flags=INIT)
    copper_loss_12 = field(Electrical_CopperLoss12, flags=INIT)
    copper_loss_13 = field(Electrical_CopperLoss13, flags=INIT)
    copper_loss_23 = field(Electrical_CopperLoss23, flags=INIT)

    # No-load parameters
    no_load_current = field(Electrical_NoLoadCurrent, flags=INIT)
    no_load_loss = field(Electrical_NoLoadLoss, flags=INIT)

    # Per-side winding type
    winding_1 = field(Electrical_Winding1, flags=OPT)
    winding_2 = field(Electrical_Winding2, flags=OPT)
    winding_3 = field(Electrical_Winding3, flags=OPT)

    # Clock numbers
    clock_12 = field(Electrical_Clock12, flags=OPT)
    clock_13 = field(Electrical_Clock13, flags=OPT)

    # Tap changer
    tap_side = field(Electrical_TapSide, flags=OPT)
    tap_position = field(Electrical_TapPosition, flags=OPT)
    tap_min = field(Electrical_TapMin, flags=OPT)
    tap_max = field(Electrical_TapMax, flags=OPT)
    tap_nom = field(Electrical_TapNom, flags=OPT)
    tap_size = field(Electrical_TapSize, flags=OPT)

    # Output attributes
    current_1 = field(Electrical_Current1, flags=PUB)
    current_2 = field(Electrical_Current2, flags=PUB)
    current_3 = field(Electrical_Current3, flags=PUB)
    power_1 = field(Electrical_Power1, flags=PUB)
    power_2 = field(Electrical_Power2, flags=PUB)
    power_3 = field(Electrical_Power3, flags=PUB)
    reactive_power_1 = field(Electrical_ReactivePower1, flags=PUB)
    reactive_power_2 = field(Electrical_ReactivePower2, flags=PUB)
    reactive_power_3 = field(Electrical_ReactivePower3, flags=PUB)
    loading = field(Electrical_Loading, flags=PUB)


class ElectricalTapRegulatorEntity(EntityGroup):
    """Transformer tap regulator for automatic voltage control.

    Adjusts transformer tap position to maintain voltage within
    a specified band. PGM component: transformer_tap_regulator.
    """

    __entity_name__ = "electrical_tap_regulator_entities"

    # Input attributes
    regulated_object_id = field(Connection_ToId, flags=INIT)  # Transformer ID
    status = field(Electrical_Status, flags=OPT)
    control_side = field(Electrical_RegulatorControlSide, flags=INIT)
    voltage_setpoint = field(Electrical_VoltageSetpoint, flags=INIT)
    voltage_band = field(Electrical_VoltageBand, flags=INIT)
    line_drop_compensation_r = field(Electrical_LineDropCompensationR, flags=OPT)
    line_drop_compensation_x = field(Electrical_LineDropCompensationX, flags=OPT)

    # Output attributes
    tap_position = field(Electrical_TapPosition, flags=PUB)


@dataclasses.dataclass
class PowerGridNetwork:
    """Groups all entity types for a power grid dataset."""

    nodes: ElectricalNodeEntity
    virtual_nodes: ElectricalVirtualNodeEntity
    lines: ElectricalLineEntity
    cables: ElectricalCableEntity
    links: ElectricalLinkEntity
    transformers: ElectricalTransformerEntity
    three_winding_transformers: ElectricalThreeWindingTransformerEntity
    loads: ElectricalLoadEntity
    generators: ElectricalGeneratorEntity
    sources: ElectricalSourceEntity
    shunts: ElectricalShuntEntity
    voltage_sensors: ElectricalVoltageSensorEntity
    power_sensors: ElectricalPowerSensorEntity
    current_sensors: ElectricalCurrentSensorEntity
    faults: ElectricalFaultEntity
    tap_regulators: ElectricalTapRegulatorEntity
