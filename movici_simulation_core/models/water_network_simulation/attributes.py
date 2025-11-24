"""Attribute specifications for water network simulation using WNTR"""

from __future__ import annotations

from movici_simulation_core.core import DataType
from movici_simulation_core.core.schema import AttributeSpec, attribute_plugin_from_dict

# Junction attributes
Water_Elevation = AttributeSpec("water.elevation", data_type=DataType(float))
Water_BaseDemand = AttributeSpec("water.base_demand", data_type=DataType(float))
Water_DemandMultiplier = AttributeSpec("water.demand_multiplier", data_type=DataType(float))
Water_DemandPattern = AttributeSpec("water.demand_pattern", data_type=DataType(str))
Water_Pressure = AttributeSpec("water.pressure", data_type=DataType(float))
Water_Head = AttributeSpec("water.head", data_type=DataType(float))
Water_ActualDemand = AttributeSpec("water.actual_demand", data_type=DataType(float))
Water_DemandDeficit = AttributeSpec("water.demand_deficit", data_type=DataType(float))

# Pipe attributes
Water_Diameter = AttributeSpec("water.diameter", data_type=DataType(float))
Water_Roughness = AttributeSpec("water.roughness", data_type=DataType(float))
Water_MinorLoss = AttributeSpec("water.minor_loss", data_type=DataType(float))
Water_LinkStatus = AttributeSpec("water.link_status", data_type=DataType(int))
Water_Flow = AttributeSpec("water.flow", data_type=DataType(float))
Water_Velocity = AttributeSpec("water.velocity", data_type=DataType(float))
Water_Headloss = AttributeSpec("water.headloss", data_type=DataType(float))
Water_FlowDirection = AttributeSpec("water.flow_direction", data_type=DataType(int))

# Pump attributes
Water_PumpCurve = AttributeSpec("water.pump_curve", data_type=DataType(str))
Water_PumpSpeed = AttributeSpec("water.pump_speed", data_type=DataType(float))
Water_Power = AttributeSpec("water.power", data_type=DataType(float))
Water_PumpType = AttributeSpec("water.pump_type", data_type=DataType(str))

# Valve attributes
Water_ValveType = AttributeSpec("water.valve_type", data_type=DataType(str))
Water_ValveSetting = AttributeSpec("water.valve_setting", data_type=DataType(float))

# Tank attributes
Water_InitialLevel = AttributeSpec("water.initial_level", data_type=DataType(float))
Water_MinLevel = AttributeSpec("water.min_level", data_type=DataType(float))
Water_MaxLevel = AttributeSpec("water.max_level", data_type=DataType(float))
Water_TankDiameter = AttributeSpec("water.tank_diameter", data_type=DataType(float))
Water_Level = AttributeSpec("water.level", data_type=DataType(float))
Water_MinVolume = AttributeSpec("water.min_volume", data_type=DataType(float))
Water_VolumeCurve = AttributeSpec("water.volume_curve", data_type=DataType(str))

# Reservoir attributes
Water_HeadMultiplier = AttributeSpec("water.head_multiplier", data_type=DataType(float))
Water_HeadPattern = AttributeSpec("water.head_pattern", data_type=DataType(str))

# General link attributes
Water_InitialStatus = AttributeSpec("water.initial_status", data_type=DataType(int))
Water_BulkCoeff = AttributeSpec("water.bulk_coeff", data_type=DataType(float))
Water_WallCoeff = AttributeSpec("water.wall_coeff", data_type=DataType(float))

WaterNetworkAttributes = attribute_plugin_from_dict(globals())
