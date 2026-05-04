"""Attribute specifications for drinking water network simulation using WNTR

Attribute naming follows the documentation specification:
- drinking_water.* : Drinking water specific attributes
- shape.* : Physical shape attributes (diameter, length, curves)
- geometry.z : Elevation (from PointEntity)
- operational.* : Operational status
- topology.* : Network topology (from LinkEntity)
- type : Entity type enum (string values)
"""

from __future__ import annotations

from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import AttributeSpec, attribute_plugin_from_dict

# =============================================================================
# Shape attributes
# =============================================================================
Shape_Diameter = AttributeSpec("shape.diameter", data_type=DataType(float))
Shape_VolumeCurve = AttributeSpec("shape.volume_curve", data_type=DataType(float, (2,), csr=True))

# =============================================================================
# Drinking water attributes - Junctions
# =============================================================================
DrinkingWater_BaseDemand = AttributeSpec("drinking_water.base_demand", data_type=DataType(float))
DrinkingWater_DemandFactor = AttributeSpec(
    "drinking_water.demand_factor", data_type=DataType(float)
)
DrinkingWater_Demand = AttributeSpec("drinking_water.demand", data_type=DataType(float))

# =============================================================================
# Drinking water attributes - PDD (per-junction pressure-dependent demand)
# =============================================================================
DrinkingWater_MinimumPressure = AttributeSpec(
    "drinking_water.minimum_pressure", data_type=DataType(float)
)
DrinkingWater_RequiredPressure = AttributeSpec(
    "drinking_water.required_pressure", data_type=DataType(float)
)
DrinkingWater_PressureExponent = AttributeSpec(
    "drinking_water.pressure_exponent", data_type=DataType(float)
)

# =============================================================================
# Drinking water attributes - Common node outputs
# =============================================================================
DrinkingWater_Pressure = AttributeSpec("drinking_water.pressure", data_type=DataType(float))
DrinkingWater_Head = AttributeSpec("drinking_water.head", data_type=DataType(float))

# =============================================================================
# Drinking water attributes - Tanks
# =============================================================================
DrinkingWater_Level = AttributeSpec("drinking_water.level", data_type=DataType(float))
DrinkingWater_MinLevel = AttributeSpec("drinking_water.min_level", data_type=DataType(float))
DrinkingWater_MaxLevel = AttributeSpec("drinking_water.max_level", data_type=DataType(float))
DrinkingWater_Overflow = AttributeSpec("drinking_water.overflow", data_type=DataType(bool))

# =============================================================================
# Drinking water attributes - Reservoirs
# =============================================================================
DrinkingWater_BaseHead = AttributeSpec("drinking_water.base_head", data_type=DataType(float))
DrinkingWater_HeadFactor = AttributeSpec("drinking_water.head_factor", data_type=DataType(float))

# =============================================================================
# Drinking water attributes - Pipes
# =============================================================================
DrinkingWater_Roughness = AttributeSpec("drinking_water.roughness", data_type=DataType(float))
DrinkingWater_MinorLoss = AttributeSpec("drinking_water.minor_loss", data_type=DataType(float))
DrinkingWater_CheckValve = AttributeSpec("drinking_water.check_valve", data_type=DataType(bool))

# =============================================================================
# Drinking water attributes - Link outputs
# =============================================================================
DrinkingWater_Flow = AttributeSpec("drinking_water.flow", data_type=DataType(float))
DrinkingWater_FlowRate_Magnitude = AttributeSpec(
    "drinking_water.flow_rate.magnitude", data_type=DataType(float)
)
DrinkingWater_Velocity = AttributeSpec("drinking_water.velocity", data_type=DataType(float))

# =============================================================================
# Drinking water attributes - Pumps
# =============================================================================
DrinkingWater_Power = AttributeSpec("drinking_water.power", data_type=DataType(float))
DrinkingWater_HeadCurve = AttributeSpec(
    "drinking_water.head_curve", data_type=DataType(float, (2,), csr=True)
)

# =============================================================================
# Drinking water attributes - Valves
# =============================================================================
# Valve-specific settings (used based on valve type)
DrinkingWater_ValvePressure = AttributeSpec(
    "drinking_water.valve_pressure", data_type=DataType(float)
)  # PRV, PSV
DrinkingWater_ValveFlow = AttributeSpec(
    "drinking_water.valve_flow", data_type=DataType(float)
)  # FCV
DrinkingWater_ValveLossCoefficient = AttributeSpec(
    "drinking_water.valve_loss_coefficient", data_type=DataType(float)
)  # TCV

# =============================================================================
# Drinking water attributes - Link status output
# =============================================================================
# WNTR LinkStatus: 0=Closed, 1=Open, 2=Active, 3=CV
DrinkingWater_LinkStatus = AttributeSpec(
    "drinking_water.link_status", data_type=DataType(int), enum_name="link_status"
)

# =============================================================================
# Operational attributes
# =============================================================================
Operational_Status = AttributeSpec("operational.status", data_type=DataType(bool))

# =============================================================================
# Type attributes (string enum values)
# =============================================================================
# Pump type: 0="power", 1="head"
Type_PumpType = AttributeSpec(
    "drinking_water.pump_type", data_type=DataType(int), enum_name="pump_type"
)
# Valve type: 0="PRV", 1="PSV", 2="FCV", 3="TCV"
Type_ValveType = AttributeSpec(
    "drinking_water.valve_type", data_type=DataType(int), enum_name="valve_type"
)

# =============================================================================
# Register all attributes as plugin
# =============================================================================
DrinkingWaterNetworkAttributes = attribute_plugin_from_dict(globals())
