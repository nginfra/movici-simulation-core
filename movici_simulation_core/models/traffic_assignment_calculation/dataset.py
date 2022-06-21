from movici_simulation_core.core.attribute import OPT, PUB, SUB, field
from movici_simulation_core.models.common.attributes import (
    Transport_AdditionalTime,
    Transport_AverageTime,
    Transport_Capacity_Hours,
    Transport_CargoAllowed,
    Transport_CargoAverageTime,
    Transport_CargoDemand,
    Transport_CargoVehicleFlow,
    Transport_CargoVehicleMaxSpeed,
    Transport_DelayFactor,
    Transport_MaxSpeed,
    Transport_PassengerAverageTime,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_PassengerVehicleFlow,
    Transport_PassengerVehicleMaxSpeed,
    Transport_VolumeToCapacityRatio,
)
from movici_simulation_core.models.common.entity_groups import PointEntity, TransportSegmentEntity
from movici_simulation_core.models.unit_conversions.attributes import (
    Transport_CargoFlow,
    Transport_PassengerFlow,
)


class TrafficTransportSegmentEntity(TransportSegmentEntity):
    passenger_flow = field(Transport_PassengerVehicleFlow, flags=PUB)
    cargo_flow = field(Transport_CargoVehicleFlow, flags=PUB)
    average_time = field(Transport_AverageTime, flags=PUB)
    delay_factor = field(Transport_DelayFactor, flags=PUB)
    volume_to_capacity = field(Transport_VolumeToCapacityRatio, flags=PUB)
    passenger_car_unit = field(Transport_PassengerCarUnit, flags=PUB)
    additional_time = field(Transport_AdditionalTime, flags=OPT)


class DemandNodeEntity(PointEntity):
    passenger_demand = field(Transport_PassengerDemand, flags=SUB)
    cargo_demand = field(Transport_CargoDemand, flags=SUB)


class TrackSegmentEntity(TrafficTransportSegmentEntity):
    __entity_name__ = "track_segment_entities"
    _max_speed = field(Transport_MaxSpeed, flags=OPT)
    average_time = field(Transport_AverageTime, flags=0)
    passenger_flow = field(Transport_PassengerFlow, flags=PUB)
    cargo_flow = field(Transport_CargoFlow, flags=PUB)


class PassengerTrackSegmentEntity(TrackSegmentEntity):
    capacity = field(Transport_Capacity_Hours, flags=OPT)
    passenger_max_speed = field(Transport_PassengerVehicleMaxSpeed, flags=OPT)
    passenger_average_time = field(Transport_PassengerAverageTime, flags=PUB)

    @property
    def max_speed(self):
        if self.passenger_max_speed.has_data():
            return self.passenger_max_speed
        else:
            return self._max_speed


class CargoTrackSegmentEntity(TrackSegmentEntity):
    capacity = field(Transport_Capacity_Hours, flags=OPT)
    cargo_max_speed = field(Transport_CargoVehicleMaxSpeed, flags=OPT)
    cargo_average_time = field(Transport_CargoAverageTime, flags=PUB)
    cargo_allowed = field(Transport_CargoAllowed, flags=OPT)

    @property
    def max_speed(self):
        if self.cargo_max_speed.has_data():
            return self.cargo_max_speed
        else:
            return self._max_speed
