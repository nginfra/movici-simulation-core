from movici_simulation_core.data_tracker.attribute import (
    field,
    SUB,
    PUB,
    OPT,
)
from movici_simulation_core.models.common.attributes import (
    Transport_AverageTime,
    Transport_CargoAllowed,
    Transport_CargoAverageTime,
    Transport_CargoVehicleMaxSpeed,
    Transport_MaxSpeed,
    Transport_PassengerAverageTime,
    Transport_PassengerVehicleMaxSpeed,
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
    __entity_name__ = "track_segment_entitites"
    _max_speed = field(Transport_MaxSpeed, flags=OPT)
    average_time = field(Transport_AverageTime, flags=0)
    passenger_flow = field(Transport_PassengerFlow, flags=PUB)
    cargo_flow = field(Transport_CargoFlow, flags=PUB)


class PassengerTrackSegmentEntity(TrackSegmentEntity):
    passenger_max_speed = field(Transport_PassengerVehicleMaxSpeed, flags=OPT)
    passenger_average_time = field(Transport_PassengerAverageTime, flags=PUB)

    @property
    def max_speed(self):
        if self.passenger_max_speed.has_data():
            return self.passenger_max_speed
        else:
            return self._max_speed


class CargoTrackSegmentEntity(TrackSegmentEntity):
    cargo_max_speed = field(Transport_CargoVehicleMaxSpeed, flags=OPT)
    cargo_average_time = field(Transport_CargoAverageTime, flags=PUB)
    cargo_allowed = field(Transport_CargoAllowed, flags=OPT)

    @property
    def max_speed(self):
        if self.cargo_max_speed.has_data():
            return self.cargo_max_speed
        else:
            return self._max_speed
