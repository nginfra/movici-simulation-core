"""Entity definitions for water network simulation"""

from movici_simulation_core.core.attribute import INIT, OPT, PUB, SUB, field
from movici_simulation_core.models.common.entity_groups import LinkEntity, PointEntity

from .attributes import (
    Water_ActualDemand,
    Water_BaseDemand,
    Water_BulkCoeff,
    Water_DemandDeficit,
    Water_DemandMultiplier,
    Water_DemandPattern,
    Water_Diameter,
    Water_Elevation,
    Water_Flow,
    Water_FlowDirection,
    Water_Head,
    Water_HeadMultiplier,
    Water_HeadPattern,
    Water_Headloss,
    Water_InitialLevel,
    Water_InitialStatus,
    Water_Level,
    Water_LinkStatus,
    Water_MaxLevel,
    Water_MinLevel,
    Water_MinorLoss,
    Water_MinVolume,
    Water_Power,
    Water_Pressure,
    Water_PumpCurve,
    Water_PumpSpeed,
    Water_PumpType,
    Water_Roughness,
    Water_TankDiameter,
    Water_ValveSetting,
    Water_ValveType,
    Water_Velocity,
    Water_VolumeCurve,
    Water_WallCoeff,
)


class WaterJunctionEntity(PointEntity):
    """Water network junctions (demand nodes)"""

    __entity_name__ = "water_junction_entities"

    # INIT attributes (static network properties)
    elevation = field(Water_Elevation, flags=INIT)
    base_demand = field(Water_BaseDemand, flags=INIT)

    # SUB attributes (input from tape files or other models)
    demand_multiplier = field(Water_DemandMultiplier, flags=SUB | OPT)
    demand_pattern = field(Water_DemandPattern, flags=SUB | OPT)

    # PUB attributes (simulation outputs)
    pressure = field(Water_Pressure, flags=PUB)
    head = field(Water_Head, flags=PUB)
    actual_demand = field(Water_ActualDemand, flags=PUB)
    demand_deficit = field(Water_DemandDeficit, flags=PUB | OPT)


class WaterTankEntity(PointEntity):
    """Water storage tanks"""

    __entity_name__ = "water_tank_entities"

    # INIT attributes
    elevation = field(Water_Elevation, flags=INIT)
    init_level = field(Water_InitialLevel, flags=INIT)
    min_level = field(Water_MinLevel, flags=INIT)
    max_level = field(Water_MaxLevel, flags=INIT)
    diameter = field(Water_TankDiameter, flags=INIT)
    min_volume = field(Water_MinVolume, flags=INIT | OPT)
    volume_curve = field(Water_VolumeCurve, flags=INIT | OPT)

    # PUB attributes
    level = field(Water_Level, flags=PUB)
    head = field(Water_Head, flags=PUB)
    pressure = field(Water_Pressure, flags=PUB)


class WaterReservoirEntity(PointEntity):
    """Water reservoirs (infinite head sources)"""

    __entity_name__ = "water_reservoir_entities"

    # INIT attributes
    head = field(Water_Head, flags=INIT)

    # SUB attributes (can vary with head pattern)
    head_multiplier = field(Water_HeadMultiplier, flags=SUB | OPT)
    head_pattern = field(Water_HeadPattern, flags=SUB | OPT)

    # PUB attributes
    flow = field(Water_Flow, flags=PUB)


class WaterPipeEntity(LinkEntity):
    """Water pipes"""

    __entity_name__ = "water_pipe_entities"

    # INIT attributes
    diameter = field(Water_Diameter, flags=INIT)
    roughness = field(Water_Roughness, flags=INIT)
    minor_loss = field(Water_MinorLoss, flags=INIT | OPT)
    initial_status = field(Water_InitialStatus, flags=INIT | OPT)
    bulk_coeff = field(Water_BulkCoeff, flags=INIT | OPT)
    wall_coeff = field(Water_WallCoeff, flags=INIT | OPT)

    # SUB attributes (dynamic control)
    status = field(Water_LinkStatus, flags=SUB | OPT)

    # PUB attributes (simulation results)
    flow = field(Water_Flow, flags=PUB)
    velocity = field(Water_Velocity, flags=PUB)
    headloss = field(Water_Headloss, flags=PUB)
    flow_direction = field(Water_FlowDirection, flags=PUB | OPT)


class WaterPumpEntity(LinkEntity):
    """Water pumps"""

    __entity_name__ = "water_pump_entities"

    # INIT attributes
    pump_type = field(Water_PumpType, flags=INIT)
    pump_curve = field(Water_PumpCurve, flags=INIT | OPT)
    power = field(Water_Power, flags=INIT | OPT)

    # SUB attributes
    status = field(Water_LinkStatus, flags=SUB | OPT)
    speed = field(Water_PumpSpeed, flags=SUB | OPT)

    # PUB attributes
    flow = field(Water_Flow, flags=PUB)
    pump_power = field(Water_Power, flags=PUB)


class WaterValveEntity(LinkEntity):
    """Water valves (PRV, PSV, FCV, TCV, etc.)"""

    __entity_name__ = "water_valve_entities"

    # INIT attributes
    valve_type = field(Water_ValveType, flags=INIT)
    diameter = field(Water_Diameter, flags=INIT)
    setting = field(Water_ValveSetting, flags=INIT)
    minor_loss = field(Water_MinorLoss, flags=INIT | OPT)
    initial_status = field(Water_InitialStatus, flags=INIT | OPT)

    # SUB attributes
    status = field(Water_LinkStatus, flags=SUB | OPT)

    # PUB attributes
    flow = field(Water_Flow, flags=PUB)
    velocity = field(Water_Velocity, flags=PUB | OPT)
    headloss = field(Water_Headloss, flags=PUB | OPT)
