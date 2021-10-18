from movici_simulation_core.data_tracker.property import (
    field,
    SUB,
    PUB,
    OPT,
)
from movici_simulation_core.models.common.attributes import (
    TrafficProperties_AverageTime,
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
    Transport_DelayFactor,
    Transport_VolumeToCapacityRatio,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_CargoDemand,
    Transport_AdditionalTime,
)
from movici_simulation_core.models.common.entities import (
    TransportSegmentEntity,
    PointEntity,
)


class TrafficTransportSegmentEntity(TransportSegmentEntity):
    passenger_flow = field(Transport_PassengerVehicleFlow, flags=PUB)
    cargo_flow = field(Transport_CargoVehicleFlow, flags=PUB)
    average_time = field(TrafficProperties_AverageTime, flags=PUB)
    delay_factor = field(Transport_DelayFactor, flags=PUB)
    volume_to_capacity = field(Transport_VolumeToCapacityRatio, flags=PUB)
    passenger_car_unit = field(Transport_PassengerCarUnit, flags=PUB)
    additional_time = field(Transport_AdditionalTime, flags=OPT)


class DemandNodeEntity(PointEntity):
    passenger_demand = field(Transport_PassengerDemand, flags=SUB)
    cargo_demand = field(Transport_CargoDemand, flags=SUB)
