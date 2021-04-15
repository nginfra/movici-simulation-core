import model_engine.dataset_manager.entity_definition as ed
from model_engine.dataset_manager.property_definition import (
    ConnectionProperties,
    ShapeProperties,
    Transport_DelayFactor,
    Transport_PassengerFlow,
    Transport_CargoFlow,
    TrafficProperties,
    LineProperties,
    Transport_MaxSpeed,
    Transport_Capacity_Hours,
    Transport_PassengerCarUnit,
    RoadSegmentProperties,
    Transport_Co2Emission_Hours,
    Transport_NoxEmission_Hours,
    Transport_EnergyConsumption_Hours,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB, INIT, OPT, SUB
from movici_simulation_core.models.common.entities import LinkEntity


class CorridorEntity(EntityGroup, name=ed.Corridor):
    from_nodes = field(to_spec(ConnectionProperties.FromIds), flags=INIT)
    to_nodes = field(to_spec(ConnectionProperties.ToIds), flags=INIT)

    max_capacity_usage = field(to_spec(Transport_Capacity_Hours), flags=PUB)
    travel_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)
    co2_emission = field(to_spec(Transport_Co2Emission_Hours), flags=PUB)
    nox_emission = field(to_spec(Transport_NoxEmission_Hours), flags=PUB)
    energy_demand = field(to_spec(Transport_EnergyConsumption_Hours), flags=PUB)
    line2d = field(to_spec(ShapeProperties.Linestring2d), flags=PUB)


class TransportSegmentEntity(LinkEntity):
    lengths = field(to_spec(LineProperties.Length), flags=OPT)

    layout = field(to_spec(RoadSegmentProperties.Layout), flags=INIT)
    max_speed = field(to_spec(Transport_MaxSpeed), flags=INIT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=INIT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=SUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=SUB)
    travel_time = field(to_spec(TrafficProperties.AverageTime), flags=SUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=SUB)

    co2_emission = field(to_spec(Transport_Co2Emission_Hours), flags=SUB)
    nox_emission = field(to_spec(Transport_NoxEmission_Hours), flags=SUB)
    energy_demand = field(to_spec(Transport_EnergyConsumption_Hours), flags=SUB)
