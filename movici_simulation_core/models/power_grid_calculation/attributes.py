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
Electrical_Resistance = AttributeSpec("electrical.resistance", DataType(float))  # Ω (r1)
Electrical_Reactance = AttributeSpec("electrical.reactance", DataType(float))  # Ω (x1)
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
# Three-Winding Transformer Attributes
# =============================================================================

Electrical_TertiaryVoltage = AttributeSpec(
    "electrical.tertiary_voltage", DataType(float)
)  # V (u3)
Electrical_RatedPower1 = AttributeSpec("electrical.rated_power_1", DataType(float))  # VA (sn_1)
Electrical_RatedPower2 = AttributeSpec("electrical.rated_power_2", DataType(float))  # VA (sn_2)
Electrical_RatedPower3 = AttributeSpec("electrical.rated_power_3", DataType(float))  # VA (sn_3)
Electrical_ShortCircuitVoltage12 = AttributeSpec(
    "electrical.short_circuit_voltage_12", DataType(float)
)  # uk_12
Electrical_ShortCircuitVoltage13 = AttributeSpec(
    "electrical.short_circuit_voltage_13", DataType(float)
)  # uk_13
Electrical_ShortCircuitVoltage23 = AttributeSpec(
    "electrical.short_circuit_voltage_23", DataType(float)
)  # uk_23

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

# =============================================================================
# Fault Attributes (for Short Circuit)
# =============================================================================

Electrical_FaultType = AttributeSpec(
    "electrical.fault_type", DataType(int)
)  # enum: 0=three_phase, 1=single_phase_to_ground, etc.
Electrical_FaultPhase = AttributeSpec("electrical.fault_phase", DataType(int))  # enum
Electrical_FaultResistance = AttributeSpec("electrical.fault_resistance", DataType(float))  # Ω
Electrical_FaultReactance = AttributeSpec("electrical.fault_reactance", DataType(float))  # Ω

# Short circuit results
Electrical_FaultCurrent = AttributeSpec("electrical.fault_current", DataType(float))  # A
Electrical_FaultPower = AttributeSpec("electrical.fault_power", DataType(float))  # VA

# =============================================================================
# Regulator Attributes
# =============================================================================

Electrical_RegulatorControlSide = AttributeSpec("electrical.regulator_control_side", DataType(int))
Electrical_VoltageSetpoint = AttributeSpec("electrical.voltage_setpoint", DataType(float))  # V
Electrical_VoltageBand = AttributeSpec("electrical.voltage_band", DataType(float))  # V
Electrical_LineDropCompensationR = AttributeSpec(
    "electrical.line_drop_compensation_r", DataType(float)
)  # Ω
Electrical_LineDropCompensationX = AttributeSpec(
    "electrical.line_drop_compensation_x", DataType(float)
)  # Ω

# =============================================================================
# Plugin Export
# =============================================================================

PowerGridAttributes = attribute_plugin_from_dict(globals())
