import model_engine.dataset_manager.entity_definition as ed
from model_engine.dataset_manager.property_definition import (
    ConnectionProperties,
    ShapeProperties,
    Transport_DelayFactor,
    Transport_PassengerVehicleFlow,
    Transport_CargoVehicleFlow,
    TrafficProperties,
    LineProperties,
    Transport_PassengerCarUnit,
    Transport_Co2Emission_Hours,
    Transport_NoxEmission_Hours,
    Transport_EnergyConsumption_Hours,
    Transport_PassengerDemand,
    Transport_CargoDemand,
    Transport_VolumeToCapacityRatio,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB, OPT, SUB
from movici_simulation_core.models.common.entities import TransportSegmentEntity, PointEntity


class CorridorEntity(EntityGroup, name=ed.Corridor):
    from_nodes = field(to_spec(ConnectionProperties.FromIds), flags=SUB)
    to_nodes = field(to_spec(ConnectionProperties.ToIds), flags=SUB)

    max_volume_to_capacity = field(to_spec(Transport_VolumeToCapacityRatio), flags=PUB)
    travel_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    passenger_flow = field(to_spec(Transport_PassengerVehicleFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoVehicleFlow), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)
    co2_emission = field(to_spec(Transport_Co2Emission_Hours), flags=PUB)
    nox_emission = field(to_spec(Transport_NoxEmission_Hours), flags=PUB)
    energy_consumption = field(to_spec(Transport_EnergyConsumption_Hours), flags=PUB)
    line2d = field(to_spec(ShapeProperties.Linestring2d), flags=PUB)


class CorridorTransportSegmentEntity(TransportSegmentEntity):
    lengths = field(to_spec(LineProperties.Length), flags=OPT)

    travel_time = field(to_spec(TrafficProperties.AverageTime), flags=SUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=SUB)

    co2_emission = field(to_spec(Transport_Co2Emission_Hours), flags=SUB)
    nox_emission = field(to_spec(Transport_NoxEmission_Hours), flags=SUB)
    energy_consumption = field(to_spec(Transport_EnergyConsumption_Hours), flags=SUB)


class DemandNodeEntity(PointEntity):
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=SUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=SUB)
