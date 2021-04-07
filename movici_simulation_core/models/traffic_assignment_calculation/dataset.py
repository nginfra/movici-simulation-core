from model_engine.dataset_manager.property_definition import (
    ShapeProperties,
    LineProperties,
    PointProperties,
    TrafficProperties,
    ConnectionProperties,
    Transport_MaxSpeed,
    Transport_Capacity_Hours,
    Transport_PassengerFlow,
    Transport_CargoFlow,
    Transport_DelayFactor,
    Transport_VolumeToCapacityRatio,
    Transport_PassengerCarUnit,
    Transport_PassengerDemand,
    Transport_CargoDemand,
    RoadSegmentProperties,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import (
    field,
    INIT,
    SUB,
    PUB,
    OPT,
    CSRProperty,
)


class SegmentEntity(EntityGroup):
    _linestring2d = field(to_spec(ShapeProperties.Linestring2d), flags=OPT)
    _linestring3d = field(to_spec(ShapeProperties.Linestring3d), flags=OPT)

    from_node_id = field(to_spec(LineProperties.FromNodeId), flags=INIT)
    to_node_id = field(to_spec(LineProperties.ToNodeId), flags=INIT)
    layout = field(to_spec(RoadSegmentProperties.Layout), flags=INIT)

    max_speed = field(to_spec(Transport_MaxSpeed), flags=INIT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=INIT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
    average_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    volume_to_capacity = field(to_spec(Transport_VolumeToCapacityRatio), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)

    @property
    def linestring(self) -> CSRProperty:
        if self._linestring3d.is_initialized():
            return self._linestring3d
        if self._linestring2d.is_initialized():
            return self._linestring2d
        raise RuntimeError(
            f"_linestring2d or _linestring3d needs to have data before linestring "
            f"is called on line entity {self.__entity_name__} "
        )


class VertexEntity(EntityGroup):
    x = field(to_spec(PointProperties.PositionX), flags=INIT)
    y = field(to_spec(PointProperties.PositionY), flags=INIT)


class VirtualNodeEntity(EntityGroup):
    to_nodes = field(to_spec(ConnectionProperties.ToIds), flags=INIT)
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=SUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=SUB)
