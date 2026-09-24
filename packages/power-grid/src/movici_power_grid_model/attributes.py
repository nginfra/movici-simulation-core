"""Electrical attribute definitions for power grid calculation model."""

from __future__ import annotations

from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import AttributeSpec, attribute_plugin_from_dict

# =============================================================================
# Node Attributes
# =============================================================================

# Input attributes (INIT)
Electrical_RatedVoltage = AttributeSpec("electrical.rated_voltage", DataType(float))  # V
Electrical_Status = AttributeSpec("electrical.status", DataType(int))  # 0=off, 1=on

# Output attributes (PUB)
Electrical_VoltagePU = AttributeSpec("electrical.voltage_pu", DataType(float))  # per-unit
Electrical_VoltageAngle = AttributeSpec("electrical.voltage_angle", DataType(float))  # rad
Electrical_Voltage = AttributeSpec("electrical.voltage", DataType(float))  # V (absolute)
Electrical_ActivePower = AttributeSpec("electrical.active_power", DataType(float))  # W
Electrical_ReactivePower = AttributeSpec("electrical.reactive_power", DataType(float))  # VAr

# =============================================================================
# Line/Branch Attributes
# =============================================================================

# Input attributes (INIT)
Electrical_Resistance = AttributeSpec("electrical.resistance", DataType(float))  # Ohm (r1)
Electrical_Reactance = AttributeSpec("electrical.reactance", DataType(float))  # Ohm (x1)
Electrical_Capacitance = AttributeSpec("electrical.capacitance", DataType(float))  # F (c1)
Electrical_TanDelta = AttributeSpec("electrical.tan_delta", DataType(float))  # tan1
Electrical_RatedCurrent = AttributeSpec("electrical.rated_current", DataType(float))  # A (i_n)
Electrical_FromStatus = AttributeSpec("electrical.from_status", DataType(int))
Electrical_ToStatus = AttributeSpec("electrical.to_status", DataType(int))

# Output attributes (PUB)
Electrical_CurrentFrom = AttributeSpec("electrical.current_from", DataType(float))  # A
Electrical_CurrentTo = AttributeSpec("electrical.current_to", DataType(float))  # A
Electrical_PowerFrom = AttributeSpec("electrical.power_from", DataType(float))  # W
Electrical_PowerTo = AttributeSpec("electrical.power_to", DataType(float))  # W
Electrical_ReactivePowerFrom = AttributeSpec(
    "electrical.reactive_power_from", DataType(float)
)  # VAr
Electrical_ReactivePowerTo = AttributeSpec("electrical.reactive_power_to", DataType(float))  # VAr
Electrical_Loading = AttributeSpec("electrical.loading", DataType(float))  # ratio (0-1+)

# =============================================================================
# Load/Generator Attributes
# =============================================================================

# Input attributes (SUB - dynamic)
Electrical_ActivePowerSpecified = AttributeSpec(
    "electrical.active_power_specified", DataType(float)
)  # W
Electrical_ReactivePowerSpecified = AttributeSpec(
    "electrical.reactive_power_specified", DataType(float)
)  # VAr
Electrical_LoadType = AttributeSpec(
    "electrical.load_type", DataType(int)
)  # enum: 0=const_power, 1=const_impedance, 2=const_current

# =============================================================================
# Transformer Attributes
# =============================================================================

# Input attributes (INIT)
Electrical_PrimaryVoltage = AttributeSpec("electrical.primary_voltage", DataType(float))  # V (u1)
Electrical_SecondaryVoltage = AttributeSpec(
    "electrical.secondary_voltage", DataType(float)
)  # V (u2)
Electrical_RatedPower = AttributeSpec("electrical.rated_power", DataType(float))  # VA (sn)
Electrical_ShortCircuitVoltage = AttributeSpec(
    "electrical.short_circuit_voltage", DataType(float)
)  # p.u. (uk)
Electrical_CopperLoss = AttributeSpec("electrical.copper_loss", DataType(float))  # W (pk)
Electrical_NoLoadCurrent = AttributeSpec(
    "electrical.no_load_current", DataType(float)
)  # p.u. (i0)
Electrical_NoLoadLoss = AttributeSpec("electrical.no_load_loss", DataType(float))  # W (p0)
Electrical_WindingFrom = AttributeSpec(
    "electrical.winding_from", DataType(int)
)  # enum: 0=wye, 1=wye_n, 2=delta
Electrical_WindingTo = AttributeSpec("electrical.winding_to", DataType(int))
Electrical_Clock = AttributeSpec("electrical.clock", DataType(int))  # 0-12

# Tap changer attributes
Electrical_TapSide = AttributeSpec("electrical.tap_side", DataType(int))  # 0=from, 1=to
Electrical_TapPosition = AttributeSpec("electrical.tap_position", DataType(int))
Electrical_TapMin = AttributeSpec("electrical.tap_min", DataType(int))
Electrical_TapMax = AttributeSpec("electrical.tap_max", DataType(int))
Electrical_TapNom = AttributeSpec("electrical.tap_nom", DataType(int))
Electrical_TapSize = AttributeSpec("electrical.tap_size", DataType(float))  # V

# =============================================================================
# Source (External Grid) Attributes
# =============================================================================

Electrical_ReferenceVoltage = AttributeSpec(
    "electrical.reference_voltage", DataType(float)
)  # p.u. (u_ref)
Electrical_ReferenceAngle = AttributeSpec(
    "electrical.reference_angle", DataType(float)
)  # rad (u_ref_angle)
Electrical_ShortCircuitPower = AttributeSpec(
    "electrical.short_circuit_power", DataType(float)
)  # VA (sk)
Electrical_RXRatio = AttributeSpec("electrical.rx_ratio", DataType(float))  # rx_ratio

# =============================================================================
# Shunt Attributes
# =============================================================================

Electrical_Conductance = AttributeSpec("electrical.conductance", DataType(float))  # S (g1)
Electrical_Susceptance = AttributeSpec("electrical.susceptance", DataType(float))  # S (b1)

# =============================================================================
# Sensor Attributes (for State Estimation)
# =============================================================================

Electrical_MeasuredVoltage = AttributeSpec("electrical.measured_voltage", DataType(float))  # V
Electrical_VoltageSigma = AttributeSpec("electrical.voltage_sigma", DataType(float))  # V
Electrical_MeasuredActivePower = AttributeSpec(
    "electrical.measured_active_power", DataType(float)
)  # W
Electrical_MeasuredReactivePower = AttributeSpec(
    "electrical.measured_reactive_power", DataType(float)
)  # VAr
Electrical_PowerSigma = AttributeSpec("electrical.power_sigma", DataType(float))  # VA
Electrical_MeasuredCurrent = AttributeSpec("electrical.measured_current", DataType(float))  # A
Electrical_CurrentSigma = AttributeSpec("electrical.current_sigma", DataType(float))  # A
Electrical_MeasuredTerminalType = AttributeSpec(
    "electrical.measured_terminal_type", DataType(int)
)  # enum
Electrical_AngleMeasurementType = AttributeSpec(
    "electrical.angle_measurement_type", DataType(int)
)  # enum: 0=local, 1=global
Electrical_MeasuredCurrentAngle = AttributeSpec(
    "electrical.measured_current_angle", DataType(float)
)  # rad
Electrical_CurrentAngleSigma = AttributeSpec(
    "electrical.current_angle_sigma", DataType(float)
)  # rad

# =============================================================================
# Three-Winding Transformer Attributes
# =============================================================================

# Node connections (3 sides)
Electrical_Node1Id = AttributeSpec("electrical.node_1_id", DataType(int))
Electrical_Node2Id = AttributeSpec("electrical.node_2_id", DataType(int))
Electrical_Node3Id = AttributeSpec("electrical.node_3_id", DataType(int))

# Per-side status
Electrical_Status1 = AttributeSpec("electrical.status_1", DataType(int))
Electrical_Status2 = AttributeSpec("electrical.status_2", DataType(int))
Electrical_Status3 = AttributeSpec("electrical.status_3", DataType(int))

# Voltages (u1 = PrimaryVoltage, u2 = SecondaryVoltage)
Electrical_TertiaryVoltage = AttributeSpec(
    "electrical.tertiary_voltage", DataType(float)
)  # V (u3)

# Per-winding rated power
Electrical_RatedPower1 = AttributeSpec("electrical.rated_power_1", DataType(float))  # VA (sn_1)
Electrical_RatedPower2 = AttributeSpec("electrical.rated_power_2", DataType(float))  # VA (sn_2)
Electrical_RatedPower3 = AttributeSpec("electrical.rated_power_3", DataType(float))  # VA (sn_3)

# Per-pair short circuit voltage
Electrical_ShortCircuitVoltage12 = AttributeSpec(
    "electrical.short_circuit_voltage_12", DataType(float)
)  # p.u. (uk_12)
Electrical_ShortCircuitVoltage13 = AttributeSpec(
    "electrical.short_circuit_voltage_13", DataType(float)
)  # p.u. (uk_13)
Electrical_ShortCircuitVoltage23 = AttributeSpec(
    "electrical.short_circuit_voltage_23", DataType(float)
)  # p.u. (uk_23)

# Per-pair copper loss
Electrical_CopperLoss12 = AttributeSpec("electrical.copper_loss_12", DataType(float))  # W (pk_12)
Electrical_CopperLoss13 = AttributeSpec("electrical.copper_loss_13", DataType(float))  # W (pk_13)
Electrical_CopperLoss23 = AttributeSpec("electrical.copper_loss_23", DataType(float))  # W (pk_23)

# Per-side winding type
Electrical_Winding1 = AttributeSpec("electrical.winding_1", DataType(int))  # enum: wye/wye_n/delta
Electrical_Winding2 = AttributeSpec("electrical.winding_2", DataType(int))
Electrical_Winding3 = AttributeSpec("electrical.winding_3", DataType(int))

# Clock numbers
Electrical_Clock12 = AttributeSpec("electrical.clock_12", DataType(int))  # 0-12
Electrical_Clock13 = AttributeSpec("electrical.clock_13", DataType(int))  # 0-12

# Per-side output attributes (PUB)
Electrical_Current1 = AttributeSpec("electrical.current_1", DataType(float))  # A (i_1)
Electrical_Current2 = AttributeSpec("electrical.current_2", DataType(float))  # A (i_2)
Electrical_Current3 = AttributeSpec("electrical.current_3", DataType(float))  # A (i_3)
Electrical_Power1 = AttributeSpec("electrical.power_1", DataType(float))  # W (p_1)
Electrical_Power2 = AttributeSpec("electrical.power_2", DataType(float))  # W (p_2)
Electrical_Power3 = AttributeSpec("electrical.power_3", DataType(float))  # W (p_3)
Electrical_ReactivePower1 = AttributeSpec(
    "electrical.reactive_power_1", DataType(float)
)  # VAr (q_1)
Electrical_ReactivePower2 = AttributeSpec(
    "electrical.reactive_power_2", DataType(float)
)  # VAr (q_2)
Electrical_ReactivePower3 = AttributeSpec(
    "electrical.reactive_power_3", DataType(float)
)  # VAr (q_3)

# =============================================================================
# Regulator Attributes
# =============================================================================

Electrical_RegulatorControlSide = AttributeSpec(
    "electrical.regulator_control_side", DataType(int)
)  # 0=from, 1=to
Electrical_VoltageSetpoint = AttributeSpec(
    "electrical.voltage_setpoint", DataType(float)
)  # V (u_set)
Electrical_VoltageBand = AttributeSpec("electrical.voltage_band", DataType(float))  # V (u_band)
Electrical_LineDropCompensationR = AttributeSpec(
    "electrical.line_drop_compensation_r", DataType(float)
)  # Ohm
Electrical_LineDropCompensationX = AttributeSpec(
    "electrical.line_drop_compensation_x", DataType(float)
)  # Ohm

# =============================================================================
# Fault Attributes (for Short Circuit)
# =============================================================================

Electrical_FaultType = AttributeSpec(
    "electrical.fault_type", DataType(int)
)  # enum: 0=three_phase, 1=single_phase_to_ground, etc.
Electrical_FaultPhase = AttributeSpec("electrical.fault_phase", DataType(int))  # enum
Electrical_FaultResistance = AttributeSpec("electrical.fault_resistance", DataType(float))  # Ohm
Electrical_FaultReactance = AttributeSpec("electrical.fault_reactance", DataType(float))  # Ohm

# Fault output attributes (short-circuit results)
Electrical_FaultCurrent = AttributeSpec("electrical.fault_current", DataType(float))  # A (i_f)
Electrical_FaultCurrentAngle = AttributeSpec(
    "electrical.fault_current_angle", DataType(float)
)  # rad (i_f_angle)

# =============================================================================
# Plugin Export
# =============================================================================

PowerGridAttributes = attribute_plugin_from_dict(globals())
