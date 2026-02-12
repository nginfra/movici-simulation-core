"""Entity definitions for drinking water network simulation

Entity groups follow the documentation specification with:

- ``drinking_water.*`` attributes for water-specific properties
- ``shape.*`` attributes for physical dimensions
- ``geometry.z`` for elevation (redeclared as INIT where required)
- ``operational.status`` for link status
- ``type`` attribute for pump/valve type enums
"""

import dataclasses

from movici_simulation_core.attributes import Geometry_Z, Shape_Length
from movici_simulation_core.core.attribute import INIT, OPT, PUB, field
from movici_simulation_core.models.common.entity_groups import LinkEntity, PointEntity

from .attributes import (
    DrinkingWater_BaseDemand,
    DrinkingWater_BaseHead,
    DrinkingWater_CheckValve,
    DrinkingWater_Demand,
    DrinkingWater_DemandFactor,
    DrinkingWater_Flow,
    DrinkingWater_FlowRate_Magnitude,
    DrinkingWater_Head,
    DrinkingWater_HeadCurve,
    DrinkingWater_HeadFactor,
    DrinkingWater_Level,
    DrinkingWater_LinkStatus,
    DrinkingWater_MaxLevel,
    DrinkingWater_MinimumPressure,
    DrinkingWater_MinLevel,
    DrinkingWater_MinorLoss,
    DrinkingWater_MinVolume,
    DrinkingWater_Overflow,
    DrinkingWater_Power,
    DrinkingWater_Pressure,
    DrinkingWater_PressureExponent,
    DrinkingWater_RequiredPressure,
    DrinkingWater_Roughness,
    DrinkingWater_Speed,
    DrinkingWater_ValveFlow,
    DrinkingWater_ValveLossCoefficient,
    DrinkingWater_ValvePressure,
    DrinkingWater_Velocity,
    Operational_Status,
    Shape_Diameter,
    Shape_VolumeCurve,
    Type_PumpType,
    Type_ValveType,
)


class WaterNodeEntity(PointEntity):
    """Base class for water network node entities with common output attributes."""

    pressure = field(DrinkingWater_Pressure, flags=PUB)
    head = field(DrinkingWater_Head, flags=PUB)
    demand = field(DrinkingWater_Demand, flags=PUB)


class WaterLinkEntity(LinkEntity):
    """Base class for water network link entities with common output attributes."""

    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)
    link_status = field(DrinkingWater_LinkStatus, flags=PUB)


class WaterJunctionEntity(
    WaterNodeEntity,
):
    """Water network junctions (demand nodes).

    Junctions are nodes in the drinking water network. They connect pipes
    and can be used as demand nodes.
    """

    __entity_name__ = "water_junction_entities"

    # INIT attributes
    base_demand = field(DrinkingWater_BaseDemand, flags=INIT)
    elevation = field(Geometry_Z, flags=INIT)

    # OPT attributes
    demand_factor = field(DrinkingWater_DemandFactor, flags=OPT)
    minimum_pressure = field(DrinkingWater_MinimumPressure, flags=OPT)
    required_pressure = field(DrinkingWater_RequiredPressure, flags=OPT)
    pressure_exponent = field(DrinkingWater_PressureExponent, flags=OPT)


class WaterTankEntity(WaterNodeEntity):
    """Water storage tanks.

    Tanks are buffers for drinking water. They are transient elements -
    as simulation progresses, tanks may fill up or empty over time.

    Tank volume can be defined either by:

    - Constant diameter (cylindrical tank): use ``diameter``, ``min_level``, ``max_level``
    - Volume curve (non-cylindrical): use ``volume_curve``, ``min_volume``
    """

    __entity_name__ = "water_tank_entities"

    elevation = field(Geometry_Z, flags=INIT)

    # OPT attributes - either diameter group OR volume_curve group
    # Cylindrical tank attributes
    diameter = field(Shape_Diameter, flags=OPT)
    min_level = field(DrinkingWater_MinLevel, flags=OPT)
    max_level = field(DrinkingWater_MaxLevel, flags=OPT)

    # Volume curve tank attributes
    volume_curve = field(Shape_VolumeCurve, flags=OPT)
    min_volume = field(DrinkingWater_MinVolume, flags=OPT)

    # Common optional attributes
    overflow = field(DrinkingWater_Overflow, flags=OPT)

    # INIT|PUB attributes - initial value required, then published
    level = field(DrinkingWater_Level, flags=INIT | PUB)


class WaterReservoirEntity(WaterNodeEntity):
    """Water reservoirs (infinite head sources).

    A reservoir is a tank that never empties. It has a fixed head which
    can be scaled by a multiplier. Reservoirs can act as water sources
    or drains depending on the head relative to connected nodes.

    .. note::
       Reservoirs don't use elevation - head is specified directly.
    """

    __entity_name__ = "water_reservoir_entities"

    # INIT attributes
    base_head = field(DrinkingWater_BaseHead, flags=INIT)

    # OPT attributes
    head_factor = field(DrinkingWater_HeadFactor, flags=OPT)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)


class WaterPipeEntity(WaterLinkEntity):
    """Water pipes.

    Pipes transport water from one node at high head to another at lower
    head, experiencing pressure drop (head loss) in the process.
    """

    __entity_name__ = "water_pipe_entities"

    # INIT attributes
    diameter = field(Shape_Diameter, flags=INIT)
    roughness = field(DrinkingWater_Roughness, flags=INIT)

    # OPT attributes
    length = field(Shape_Length, flags=OPT)
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)
    check_valve = field(DrinkingWater_CheckValve, flags=OPT)
    status = field(Operational_Status, flags=OPT)

    # PUB attributes
    velocity = field(DrinkingWater_Velocity, flags=PUB)


class WaterPumpEntity(WaterLinkEntity):
    """Water pumps.

    Pumps increase the head from one node to another. Two types:

    - Power pump: Fixed power, speed ignored
    - Head pump: Uses head curve, speed scales the curve
    """

    __entity_name__ = "water_pump_entities"

    # INIT attributes
    pump_type = field(Type_PumpType, flags=INIT)

    # OPT attributes (depends on pump_type)
    power = field(DrinkingWater_Power, flags=OPT)
    head_curve = field(DrinkingWater_HeadCurve, flags=OPT)
    speed = field(DrinkingWater_Speed, flags=OPT)
    status = field(Operational_Status, flags=OPT)


class WaterValveEntity(WaterLinkEntity):
    """Water valves.

    Valves reduce flow in a controlled manner. Types:

    - PRV (Pressure Reducing): Limits downstream pressure
    - PSV (Pressure Sustaining): Maintains upstream pressure
    - FCV (Flow Control): Limits maximum flow
    - TCV (Throttle Control): Uses loss coefficient

    .. note:: GPV and PBV valves are not supported by the WNTRSimulator.
    """

    __entity_name__ = "water_valve_entities"

    # INIT attributes
    valve_type = field(Type_ValveType, flags=INIT)
    diameter = field(Shape_Diameter, flags=INIT)

    # OPT attributes (depends on valve_type)
    valve_pressure = field(DrinkingWater_ValvePressure, flags=OPT)
    valve_flow = field(DrinkingWater_ValveFlow, flags=OPT)
    valve_loss_coefficient = field(DrinkingWater_ValveLossCoefficient, flags=OPT)
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)


@dataclasses.dataclass
class DrinkingWaterNetwork:
    junctions: WaterJunctionEntity
    tanks: WaterTankEntity
    reservoirs: WaterReservoirEntity
    pipes: WaterPipeEntity
    pumps: WaterPumpEntity
    valves: WaterValveEntity
