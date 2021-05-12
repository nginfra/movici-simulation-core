from model_engine.dataset_manager.property_definition import (
    TrafficProperties,
    Transport_PassengerFlow,
    Transport_CargoFlow,
    Transport_DelayFactor,
    Transport_VolumeToCapacityRatio,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_CargoDemand,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.property import (
    field,
    SUB,
    PUB,
)
from movici_simulation_core.models.common.entities import (
    TransportSegmentEntity,
    PointEntity,
)


class TrafficTransportSegmentEntity(TransportSegmentEntity):
    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
    average_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    volume_to_capacity = field(to_spec(Transport_VolumeToCapacityRatio), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)


class DemandNodeEntity(PointEntity):
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=SUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=SUB)
