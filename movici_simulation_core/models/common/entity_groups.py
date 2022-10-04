import typing as t

import numpy as np

from movici_simulation_core.csr import slice_csr_array

from ...attributes import (
    Geometry_Linestring2d,
    Geometry_Linestring3d,
    Geometry_Polygon,
    Geometry_Polygon2d,
    Geometry_Polygon3d,
    Geometry_X,
    Geometry_Y,
    Geometry_Z,
    Grid_GridPoints,
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
        OpenPolygonGeometry,
        PointGeometry,
    )
except ImportError as e:

    ClosedPolygonGeometry = delayed_raise(e)
    Geometry = delayed_raise(e)
    LinestringGeometry = delayed_raise(e)
    OpenPolygonGeometry = delayed_raise(e)
    PointGeometry = delayed_raise(e)

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

    def dimensions(self):
        raise NotImplementedError

    def get_geometry(self) -> Geometry:
        raise NotImplementedError

    def get_single_geometry(self, index: int) -> BaseGeometry:
        raise NotImplementedError

    def ensure_ready(self) -> None:
        if not self.is_ready():
            raise NotReady

    def is_ready(self):
        return True


class PointEntity(GeometryEntity):
    x = field(Geometry_X, flags=INIT)
    y = field(Geometry_Y, flags=INIT)
    z = field(Geometry_Z, flags=OPT)

    def dimensions(self):
        return 3 if self.z.is_initialized() else 2

    def is_ready(self):
        return self.x.is_initialized() and self.y.is_initialized()

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
                    f"LineString '{self.__entity_name__}' does not have geometry data"
                )

        return self._linestring

    def dimensions(self):
        try:
            return self.linestring.csr.data.shape[1]
        except RuntimeError:
            return None

    def is_ready(self) -> bool:
        return self._linestring3d.is_initialized() or self._linestring2d.is_initialized()

    def get_geometry(self) -> LinestringGeometry:
        return LinestringGeometry(
            points=self.linestring.csr.data[:, 0:2], row_ptr=self.linestring.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> LineString:
        return LineString(self.linestring.csr.slice([index]).data[:, 0:2])


class PolygonEntity(GeometryEntity):
    _polygon_legacy = field(Geometry_Polygon, flags=OPT)
    _polygon2d = field(Geometry_Polygon2d, flags=OPT)
    _polygon3d = field(Geometry_Polygon3d, flags=OPT)
    _polygon: t.Optional[CSRAttribute] = None

    @property
    def polygon(self) -> CSRAttribute:
        if not self._polygon:
            if self._polygon3d.is_initialized():
                self._polygon = self._polygon3d
            elif self._polygon2d.is_initialized():
                self._polygon = self._polygon2d
            elif self._polygon_legacy.is_initialized():
                self._polygon = self._polygon_legacy
            else:
                raise RuntimeError(
                    f"PolygonEntity '{self.__entity_name__}' does not have geometry data"
                )

        return self._polygon

    def dimensions(self):
        try:
            return self.polygon.csr.data.shape[1]
        except RuntimeError:
            return None

    def is_ready(self) -> bool:
        return any(
            pol.is_initialized()
            for pol in [self._polygon3d, self._polygon2d, self._polygon_legacy]
        )

    def get_geometry(self) -> ClosedPolygonGeometry:
        return ClosedPolygonGeometry(
            points=self.polygon.csr.data[:, 0:2], row_ptr=self.polygon.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> Polygon:
        return Polygon(self.polygon.csr.slice([index]).data[:, 0:2])


class GridCellEntity(GeometryEntity):
    grid_points = field(Grid_GridPoints, flags=INIT)
    points: t.Optional[PointEntity] = None
    _polygon_data: t.Optional[np.ndarray] = None

    def set_points(self, points: PointEntity):
        self.points = points

    def get_geometry(self) -> ClosedPolygonGeometry:
        polygon_data = self._resolve_polygons()
        return OpenPolygonGeometry(
            points=polygon_data,
            row_ptr=self.grid_points.csr.row_ptr,
        )

    def get_single_geometry(self, index: int) -> Polygon:
        polygon_data = self._resolve_polygons()
        geometry = slice_csr_array(polygon_data, self.grid_points.csr.row_ptr, [index])
        return Polygon(geometry[:, 0:2])

    def is_ready(self):
        return (
            self.points is not None
            and self.points.is_ready()
            and self.grid_points.is_initialized()
        )

    def _resolve_polygons(self) -> np.ndarray:
        if self._polygon_data is not None:
            return self._polygon_data

        if self.points is None:
            raise RuntimeError("GridCellEntity must have points set")

        point_geometry = np.stack((self.points.x.array, self.points.y.array), axis=-1)
        points_indices = self.points.index[self.grid_points.csr.data]
        self._polygon_data = point_geometry[points_indices]
        return self._polygon_data


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
