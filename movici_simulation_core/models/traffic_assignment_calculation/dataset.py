from model_engine.dataset_manager.property_definition import (
    ShapeProperties,
    LineProperties,
    PointProperties,
    TrafficProperties,
    ConnectionProperties,
    Transport_Direction,
    Transport_MaxSpeed,
    Transport_Capacity_Hours,
    Transport_PassengerFlow,
    Transport_CargoFlow,
    Transport_DelayFactor,
    Transport_VolumeToCapacityRatio,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_CargoDemand,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, SUB, PUB


class SegmentEntity(EntityGroup):
    linestring = field(to_spec(ShapeProperties.Linestring2d), flags=INIT)

    from_node_id = field(to_spec(LineProperties.FromNodeId), flags=INIT)
    to_node_id = field(to_spec(LineProperties.ToNodeId), flags=INIT)
    direction = field(to_spec(Transport_Direction), flags=INIT)

    max_speed = field(to_spec(Transport_MaxSpeed), flags=INIT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=INIT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
    average_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    volume_to_capacity = field(to_spec(Transport_VolumeToCapacityRatio), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)


class VertexEntity(EntityGroup):
    x = field(to_spec(PointProperties.PositionX), flags=INIT)
    y = field(to_spec(PointProperties.PositionY), flags=INIT)


class VirtualNodeEntity(EntityGroup):
    to_dataset = field(to_spec(ConnectionProperties.ToDataset), flags=INIT)
    to_nodes = field(to_spec(ConnectionProperties.ToIds), flags=INIT)
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=SUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=SUB)
