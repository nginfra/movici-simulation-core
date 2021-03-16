from abc import abstractmethod

import numpy as np
from movici_simulation_core.base_model.config_helpers import property_mapping
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, INIT, OPT
from spatial_mapper.geometry import (
    PointCollection,
    LineStringCollection,
    GeometryCollection,
    ClosedPolygonCollection,
)
from spatial_mapper.mapper import Mapper

PositionX = property_mapping[("point_properties", "position_x")]
PositionY = property_mapping[("point_properties", "position_y")]
Linestring2D = property_mapping[("shape_properties", "linestring_2d")]
Linestring3D = property_mapping[("shape_properties", "linestring_3d")]
Polygon = property_mapping[("shape_properties", "polygon")]


class GeometryEntity(EntityGroup):
    @abstractmethod
    def get_geometry(self) -> GeometryCollection:
        ...

    def get_mapper(self) -> Mapper:
        return Mapper(self.get_geometry())


class PointEntity(GeometryEntity):
    x = field(PositionX, flags=INIT)
    y = field(PositionY, flags=INIT)

    def get_geometry(self) -> PointCollection:
        return PointCollection(coord_seq=np.stack((self.x.array, self.y.array), axis=-1))


class LineEntity(GeometryEntity):
    line2d = field(Linestring2D, flags=OPT)
    line3d = field(Linestring3D, flags=OPT)

    def get_geometry(self) -> LineStringCollection:
        if self.line3d.is_initialized():
            line_data = self.line3d.csr.data[:, 0:2]
            line_ptr = self.line3d.csr.row_ptr
        elif self.line2d.is_initialized():
            line_data = self.line2d.csr.data
            line_ptr = self.line2d.csr.row_ptr
        else:
            raise RuntimeError(
                f"line2d or line3d needs to have data before get_geometry "
                f"is called on line entity {self.__entity_name__} "
            )

        return LineStringCollection(coord_seq=line_data, indptr=line_ptr)


class PolygonEntity(GeometryEntity):
    polygon = field(Polygon, flags=INIT)

    def get_geometry(self) -> ClosedPolygonCollection:
        polygon2d = self.polygon.csr.data[:, 0:2]
        row_ptr = self.polygon.csr.row_ptr
        return ClosedPolygonCollection(coord_seq=polygon2d, indptr=row_ptr)


supported_geometry_types = {
    "point": PointEntity,
    "line": LineEntity,
    "polygon": PolygonEntity,
}
