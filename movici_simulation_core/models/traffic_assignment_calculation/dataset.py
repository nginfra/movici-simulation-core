import typing as t

from model_engine.dataset_manager.property_definition import (
    ShapeProperties,
    LineProperties,
    PointProperties,
    TrafficProperties,
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


class DemandLinkEntity(EntityGroup):
    _linestring2d = field(to_spec(ShapeProperties.Linestring2d), flags=OPT)
    _linestring3d = field(to_spec(ShapeProperties.Linestring3d), flags=OPT)
    _linestring: t.Optional[CSRProperty] = None

    from_node_id = field(to_spec(LineProperties.FromNodeId), flags=INIT)
    to_node_id = field(to_spec(LineProperties.ToNodeId), flags=INIT)

    @property
    def linestring(self) -> CSRProperty:
        if not self._linestring:
            if self._linestring3d.is_initialized():
                self._linestring = self._linestring3d
            elif self._linestring2d.is_initialized():
                self._linestring = self._linestring2d
            else:
                raise RuntimeError(
                    f"_linestring2d or _linestring3d needs to have data before linestring "
                    f"is called on line entity {self.__entity_name__} "
                )

        return self._linestring


class TransportSegmentEntity(DemandLinkEntity):
    layout = field(to_spec(RoadSegmentProperties.Layout), flags=INIT)

    max_speed = field(to_spec(Transport_MaxSpeed), flags=INIT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=INIT)

    passenger_flow = field(to_spec(Transport_PassengerFlow), flags=PUB)
    cargo_flow = field(to_spec(Transport_CargoFlow), flags=PUB)
    average_time = field(to_spec(TrafficProperties.AverageTime), flags=PUB)
    delay_factor = field(to_spec(Transport_DelayFactor), flags=PUB)
    volume_to_capacity = field(to_spec(Transport_VolumeToCapacityRatio), flags=PUB)
    passenger_car_unit = field(to_spec(Transport_PassengerCarUnit), flags=PUB)


class TransportNodeEntity(EntityGroup):
    x = field(to_spec(PointProperties.PositionX), flags=INIT)
    y = field(to_spec(PointProperties.PositionY), flags=INIT)


class DemandNodeEntity(TransportNodeEntity):
    passenger_demand = field(to_spec(Transport_PassengerDemand), flags=SUB)
    cargo_demand = field(to_spec(Transport_CargoDemand), flags=SUB)
