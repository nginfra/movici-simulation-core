import typing as t
from abc import abstractmethod

import numpy as np
from shapely.geometry import LineString, Point, Polygon
from shapely.geometry.base import BaseGeometry

from model_engine.dataset_manager.property_definition import (
    ShapeProperties,
    LineProperties,
    PointProperties,
    Transport_MaxSpeed,
    Transport_Capacity_Hours,
    Reference,
    Transport_Layout,
)
from movici_simulation_core.legacy_base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, OPT, CSRProperty, INIT
from movici_simulation_core.exceptions import NotReady

from boost_geo_query.geometry import (
    Geometry,
    LinestringGeometry,
    PointGeometry,
    ClosedPolygonGeometry,
)


class GeometryEntity(EntityGroup):
    reference = field(to_spec(Reference), flags=OPT)

    @abstractmethod
    def get_geometry(self) -> Geometry:
        ...

    @abstractmethod
    def get_single_geometry(self, index: int) -> BaseGeometry:
        ...


class PointEntity(GeometryEntity):
    x = field(to_spec(PointProperties.PositionX), flags=INIT)
    y = field(to_spec(PointProperties.PositionY), flags=INIT)

    def get_geometry(self) -> PointGeometry:
        return PointGeometry(points=np.stack((self.x.array, self.y.array), axis=-1))

    def get_single_geometry(self, index: int) -> Point:
        return Point(self.x.array[index], self.y.array[index])


class LineEntity(GeometryEntity):
    _linestring2d = field(to_spec(ShapeProperties.Linestring2d), flags=OPT)
    _linestring3d = field(to_spec(ShapeProperties.Linestring3d), flags=OPT)
    _linestring: t.Optional[CSRProperty] = None

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

    def ensure_ready(self) -> None:
        if not self.is_ready():
            raise NotReady

    def is_ready(self) -> bool:
        return self._linestring3d.is_initialized() or self._linestring2d.is_initialized()

    def get_geometry(self) -> LinestringGeometry:
        return LinestringGeometry(
            points=self.linestring.csr.data[:, 0:2], row_ptr=self.linestring.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> LineString:
        return LineString(self.linestring.csr.slice([index]).data[:, 0:2])


class PolygonEntity(GeometryEntity):
    polygon = field(to_spec(ShapeProperties.Polygon), flags=INIT)

    def get_geometry(self) -> ClosedPolygonGeometry:
        return ClosedPolygonGeometry(
            points=self.polygon.csr.data, row_ptr=self.polygon.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> Polygon:
        return Polygon(self.polygon.csr.slice([index]).data[:, 0:2])


class LinkEntity(LineEntity):
    from_node_id = field(to_spec(LineProperties.FromNodeId), flags=INIT)
    to_node_id = field(to_spec(LineProperties.ToNodeId), flags=INIT)


class VirtualLinkEntity(LinkEntity):
    max_speed = field(to_spec(Transport_MaxSpeed), flags=OPT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=OPT)


class TransportSegmentEntity(LinkEntity):
    layout = field(to_spec(Transport_Layout), flags=INIT)
    max_speed = field(to_spec(Transport_MaxSpeed), flags=INIT)
    capacity = field(to_spec(Transport_Capacity_Hours), flags=INIT)
