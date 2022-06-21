import typing as t

import numpy as np

from ...attributes import (
    Geometry_Linestring2d,
    Geometry_Linestring3d,
    Geometry_Polygon,
    Geometry_X,
    Geometry_Y,
    Reference,
    Topology_FromNodeId,
    Topology_ToNodeId,
)
from ...core import INIT, OPT, CSRAttribute, EntityGroup, field
from ...exceptions import NotReady
from ...models.common.attributes import (
    Transport_Capacity_Hours,
    Transport_Layout,
    Transport_MaxSpeed,
)


def delayed_raise(err: Exception):
    def _inner(*_, **__):
        raise err from None

    return _inner


try:
    from movici_geo_query.geometry import (
        ClosedPolygonGeometry,
        Geometry,
        LinestringGeometry,
        PointGeometry,
    )
except ImportError as e:

    Geometry = delayed_raise(e)
    LinestringGeometry = delayed_raise(e)
    PointGeometry = delayed_raise(e)
    ClosedPolygonGeometry = delayed_raise(e)

try:
    from shapely.geometry import LineString, Point, Polygon
    from shapely.geometry.base import BaseGeometry
except ImportError as e:

    BaseGeometry = delayed_raise(e)
    LineString = delayed_raise(e)
    Point = delayed_raise(e)
    Polygon = delayed_raise(e)


class GeometryEntity(EntityGroup):
    reference = field(Reference, flags=OPT)

    def get_geometry(self) -> Geometry:
        raise NotImplementedError

    def get_single_geometry(self, index: int) -> BaseGeometry:
        raise NotImplementedError


class PointEntity(GeometryEntity):
    x = field(Geometry_X, flags=INIT)
    y = field(Geometry_Y, flags=INIT)

    def get_geometry(self) -> PointGeometry:
        return PointGeometry(points=np.stack((self.x.array, self.y.array), axis=-1))

    def get_single_geometry(self, index: int) -> Point:
        return Point(self.x.array[index], self.y.array[index])


class LineEntity(GeometryEntity):
    _linestring2d = field(Geometry_Linestring2d, flags=OPT)
    _linestring3d = field(Geometry_Linestring3d, flags=OPT)
    _linestring: t.Optional[CSRAttribute] = None

    @property
    def linestring(self) -> CSRAttribute:
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
    polygon = field(Geometry_Polygon, flags=INIT)

    def get_geometry(self) -> ClosedPolygonGeometry:
        return ClosedPolygonGeometry(
            points=self.polygon.csr.data, row_ptr=self.polygon.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> Polygon:
        return Polygon(self.polygon.csr.slice([index]).data[:, 0:2])


class LinkEntity(LineEntity):
    from_node_id = field(Topology_FromNodeId, flags=INIT)
    to_node_id = field(Topology_ToNodeId, flags=INIT)


class VirtualLinkEntity(LinkEntity):
    __entity_name__ = "virtual_link_entities"
    max_speed = field(Transport_MaxSpeed, flags=OPT)
    capacity = field(Transport_Capacity_Hours, flags=OPT)


class TransportLinkEntity(LinkEntity):
    layout = field(Transport_Layout, flags=OPT)


class TransportSegmentEntity(LinkEntity):
    layout = field(Transport_Layout, flags=OPT)
    _max_speed = field(Transport_MaxSpeed, flags=OPT)
    capacity = field(Transport_Capacity_Hours, flags=OPT)

    @property
    def max_speed(self):
        return self._max_speed
