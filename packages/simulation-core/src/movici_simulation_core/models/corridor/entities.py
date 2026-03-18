from movici_simulation_core.attributes import (
    Connection_FromIds,
    Connection_ToIds,
    Geometry_Linestring2d,
    Shape_Length,
)
from movici_simulation_core.core.attribute import OPT, PUB, SUB, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.models.common.entity_groups import PointEntity, TransportSegmentEntity
from movici_simulation_core.models.corridor.attributes import (
    TrafficProperties_AverageTime,
    Transport_CargoDemand,
    Transport_CargoVehicleFlow,
    Transport_Co2Emission_Hours,
    Transport_DelayFactor,
    Transport_EnergyConsumption_Hours,
    Transport_NoxEmission_Hours,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_PassengerVehicleFlow,
    Transport_VolumeToCapacityRatio,
)


class CorridorEntity(EntityGroup, name="corridor_entities"):
    from_nodes = field(Connection_FromIds, flags=SUB)
    to_nodes = field(Connection_ToIds, flags=SUB)

    max_volume_to_capacity = field(Transport_VolumeToCapacityRatio, flags=PUB)
    travel_time = field(TrafficProperties_AverageTime, flags=PUB)
    delay_factor = field(Transport_DelayFactor, flags=PUB)
    passenger_flow = field(Transport_PassengerVehicleFlow, flags=PUB)
    cargo_flow = field(Transport_CargoVehicleFlow, flags=PUB)
    passenger_car_unit = field(Transport_PassengerCarUnit, flags=PUB)
    co2_emission = field(Transport_Co2Emission_Hours, flags=PUB)
    nox_emission = field(Transport_NoxEmission_Hours, flags=PUB)
    energy_consumption = field(Transport_EnergyConsumption_Hours, flags=PUB)
    line2d = field(Geometry_Linestring2d, flags=PUB)


class CorridorTransportSegmentEntity(TransportSegmentEntity):
    lengths = field(Shape_Length, flags=OPT)

    travel_time = field(TrafficProperties_AverageTime, flags=SUB)
    passenger_car_unit = field(Transport_PassengerCarUnit, flags=SUB)

    co2_emission = field(Transport_Co2Emission_Hours, flags=SUB)
    nox_emission = field(Transport_NoxEmission_Hours, flags=SUB)
    energy_consumption = field(Transport_EnergyConsumption_Hours, flags=SUB)


class DemandNodeEntity(PointEntity):
    passenger_demand = field(Transport_PassengerDemand, flags=SUB)
    cargo_demand = field(Transport_CargoDemand, flags=SUB)
