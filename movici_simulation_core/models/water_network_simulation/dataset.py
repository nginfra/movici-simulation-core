"""Entity definitions for drinking water network simulation

Entity groups follow the documentation specification with:

- ``drinking_water.*`` attributes for water-specific properties
- ``shape.*`` attributes for physical dimensions
- ``geometry.z`` for elevation (redeclared as INIT where required)
- ``operational.status`` for link status
- ``type`` attribute for pump/valve type enums
"""

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
    DrinkingWater_Headloss,
    DrinkingWater_Level,
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
    DrinkingWater_ValveCurve,
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


class WaterJunctionEntity(PointEntity):
    """Water network junctions (demand nodes).

    Junctions are nodes in the drinking water network. They connect pipes
    and can be used as demand nodes.

    :ivar elevation: Elevation (``geometry.z``, INIT)
    :ivar base_demand: Base demand on this node (``drinking_water.base_demand``, INIT)
    :ivar demand_factor: Scaling factor for demand (``drinking_water.demand_factor``, OPT)
    :ivar demand: Effective demand output (``drinking_water.demand``, PUB)
    :ivar pressure: Dynamic pressure at the node (``drinking_water.pressure``, PUB)
    :ivar head: Static (total) head (``drinking_water.head``, PUB)
    """

    __entity_name__ = "water_junction_entities"

    # INIT attributes - redeclare z as required
    elevation = field(Geometry_Z, flags=INIT)
    base_demand = field(DrinkingWater_BaseDemand, flags=INIT)

    # OPT attributes
    demand_factor = field(DrinkingWater_DemandFactor, flags=OPT)
    minimum_pressure = field(DrinkingWater_MinimumPressure, flags=OPT)
    required_pressure = field(DrinkingWater_RequiredPressure, flags=OPT)
    pressure_exponent = field(DrinkingWater_PressureExponent, flags=OPT)

    # PUB attributes
    demand = field(DrinkingWater_Demand, flags=PUB)
    pressure = field(DrinkingWater_Pressure, flags=PUB)
    head = field(DrinkingWater_Head, flags=PUB)


class WaterTankEntity(PointEntity):
    """Water storage tanks.

    Tanks are buffers for drinking water. They are transient elements -
    as simulation progresses, tanks may fill up or empty over time.

    Tank volume can be defined either by:

    - Constant diameter (cylindrical tank): use ``diameter``, ``min_level``, ``max_level``
    - Volume curve (non-cylindrical): use ``volume_curve``, ``min_volume``

    :ivar elevation: Elevation at tank bottom (``geometry.z``, INIT)
    :ivar diameter: Tank diameter for cylindrical tanks (``shape.diameter``, OPT)
    :ivar min_level: Minimum level for drainage (``drinking_water.min_level``, OPT)
    :ivar max_level: Maximum level / overflow threshold (``drinking_water.max_level``, OPT)
    :ivar volume_curve: Volume vs depth curve as CSR (``shape.volume_curve``, OPT)
    :ivar min_volume: Minimum volume for drainage (``drinking_water.min_volume``, OPT)
    :ivar overflow: Whether tank can overflow when full (``drinking_water.overflow``, OPT)
    :ivar level: Water level, initial + output (``drinking_water.level``, INIT|PUB)
    :ivar demand: Net flow into tank (``drinking_water.demand``, PUB)
    :ivar pressure: Pressure in the tank (``drinking_water.pressure``, PUB)
    :ivar head: Total head in the tank (``drinking_water.head``, PUB)
    """

    __entity_name__ = "water_tank_entities"

    # INIT attributes - redeclare z as required
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

    # PUB attributes
    demand = field(DrinkingWater_Demand, flags=PUB)
    pressure = field(DrinkingWater_Pressure, flags=PUB)
    head = field(DrinkingWater_Head, flags=PUB)


class WaterReservoirEntity(PointEntity):
    """Water reservoirs (infinite head sources).

    A reservoir is a tank that never empties. It has a fixed head which
    can be scaled by a multiplier. Reservoirs can act as water sources
    or drains depending on the head relative to connected nodes.

    .. note::
       Reservoirs don't use elevation - head is specified directly.

    :ivar base_head: Base head of the reservoir (``drinking_water.base_head``, INIT)
    :ivar head_factor: Head multiplier, default 1.0 (``drinking_water.head_factor``, OPT)
    :ivar head: Calculated head output (``drinking_water.head``, PUB)
    :ivar demand: Net flow into reservoir, negative means outflow (``drinking_water.demand``, PUB)
    :ivar flow: Total flow rate out of reservoir (``drinking_water.flow``, PUB)
    """

    __entity_name__ = "water_reservoir_entities"

    # INIT attributes
    base_head = field(DrinkingWater_BaseHead, flags=INIT)

    # OPT attributes
    head_factor = field(DrinkingWater_HeadFactor, flags=OPT)

    # PUB attributes
    head = field(DrinkingWater_Head, flags=PUB)
    demand = field(DrinkingWater_Demand, flags=PUB)
    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)


class WaterPipeEntity(LinkEntity):
    """Water pipes.

    Pipes transport water from one node at high head to another at lower
    head, experiencing pressure drop (head loss) in the process.

    :ivar diameter: Pipe diameter (``shape.diameter``, INIT)
    :ivar roughness: Pipe roughness factor (``drinking_water.roughness``, INIT)
    :ivar length: Pipe length, calculated from geometry if not set (``shape.length``, OPT)
    :ivar minor_loss: Minor loss coefficient (``drinking_water.minor_loss``, OPT)
    :ivar check_valve: Whether pipe has check valve (``drinking_water.check_valve``, OPT)
    :ivar status: Whether pipe is open/closed (``operational.status``, OPT|PUB)
    :ivar flow: Flow rate through pipe (``drinking_water.flow``, PUB)
    :ivar velocity: Flow velocity (``drinking_water.velocity``, PUB)
    :ivar headloss: Head loss in pipe (``drinking_water.headloss``, PUB)
    """

    __entity_name__ = "water_pipe_entities"

    # INIT attributes
    diameter = field(Shape_Diameter, flags=INIT)
    roughness = field(DrinkingWater_Roughness, flags=INIT)

    # OPT attributes
    length = field(Shape_Length, flags=OPT)
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)
    check_valve = field(DrinkingWater_CheckValve, flags=OPT)

    # OPT|PUB attributes
    status = field(Operational_Status, flags=OPT | PUB)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)
    velocity = field(DrinkingWater_Velocity, flags=PUB)
    headloss = field(DrinkingWater_Headloss, flags=PUB)


class WaterPumpEntity(LinkEntity):
    """Water pumps.

    Pumps increase the head from one node to another. Two types:

    - Power pump: Fixed power, speed ignored
    - Head pump: Uses head curve, speed scales the curve

    :ivar pump_type: Pump type, ``"power"`` or ``"head"`` (``type``, INIT)
    :ivar power: Fixed power for power pumps (``drinking_water.power``, OPT)
    :ivar head_curve: Head/flow curve as CSR for head pumps (``drinking_water.head_curve``, OPT)
    :ivar speed: Relative pump speed, default 1.0 (``drinking_water.speed``, OPT)
    :ivar status: Whether pump is open/closed (``operational.status``, OPT|PUB)
    :ivar flow: Flow rate through pump (``drinking_water.flow``, PUB)
    """

    __entity_name__ = "water_pump_entities"

    # INIT attributes
    pump_type = field(Type_PumpType, flags=INIT)

    # OPT attributes (depends on pump_type)
    power = field(DrinkingWater_Power, flags=OPT)
    head_curve = field(DrinkingWater_HeadCurve, flags=OPT)
    speed = field(DrinkingWater_Speed, flags=OPT)

    # OPT|PUB attributes
    status = field(Operational_Status, flags=OPT | PUB)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)


class WaterValveEntity(LinkEntity):
    """Water valves.

    Valves reduce flow in a controlled manner. Types:

    - PRV (Pressure Reducing): Limits downstream pressure
    - PSV (Pressure Sustaining): Maintains upstream pressure
    - PBV (Pressure Breaker): Maintains constant pressure drop
    - FCV (Flow Control): Limits maximum flow
    - TCV (Throttle Control): Uses loss coefficient
    - GPV (General Purpose): User-defined head loss curve

    :ivar valve_type: Valve type string (``type``, INIT)
    :ivar diameter: Valve diameter (``shape.diameter``, INIT)
    :ivar valve_pressure: Pressure setting for PRV/PSV/PBV (``drinking_water.valve_pressure``, OPT)
    :ivar valve_flow: Flow setting for FCV (``drinking_water.valve_flow``, OPT)
    :ivar valve_loss_coefficient: TCV loss coeff (``drinking_water.valve_loss_coefficient``, OPT)
    :ivar valve_curve: Head loss curve as CSR for GPV (``drinking_water.valve_curve``, OPT)
    :ivar minor_loss: Minor loss coefficient (``drinking_water.minor_loss``, OPT)
    :ivar flow: Flow rate through valve (``drinking_water.flow``, PUB)
    """

    __entity_name__ = "water_valve_entities"

    # INIT attributes
    valve_type = field(Type_ValveType, flags=INIT)
    diameter = field(Shape_Diameter, flags=INIT)

    # OPT attributes (depends on valve_type)
    valve_pressure = field(DrinkingWater_ValvePressure, flags=OPT)
    valve_flow = field(DrinkingWater_ValveFlow, flags=OPT)
    valve_loss_coefficient = field(DrinkingWater_ValveLossCoefficient, flags=OPT)
    valve_curve = field(DrinkingWater_ValveCurve, flags=OPT)
    minor_loss = field(DrinkingWater_MinorLoss, flags=OPT)

    # PUB attributes
    flow = field(DrinkingWater_Flow, flags=PUB)
    flow_rate_magnitude = field(DrinkingWater_FlowRate_Magnitude, flags=PUB)
