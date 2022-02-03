from movici_simulation_core.core.attributes import (
    Shape_Length,
    Geometry_Linestring2d,
    Connection_FromIds,
    Connection_ToIds,
)
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.attribute import field, PUB, OPT, SUB
from movici_simulation_core.models.common.entities import TransportSegmentEntity, PointEntity
from movici_simulation_core.models.corridor.attributes import (
    TrafficProperties_AverageTime,
    Transport_VolumeToCapacityRatio,
    Transport_DelayFactor,
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
    Transport_PassengerCarUnit,
    Transport_Co2Emission_Hours,
    Transport_NoxEmission_Hours,
    Transport_EnergyConsumption_Hours,
    Transport_PassengerDemand,
    Transport_CargoDemand,
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
