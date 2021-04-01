from abc import abstractmethod

from shapely.geometry import LineString, Point, Polygon
import model_engine.dataset_manager.entity_definition as ed
import numpy as np
from model_engine.dataset_manager.property_definition import (
    DisplayName,
    ConnectionProperties,
    Reference,
    Overlap_Active,
    PointProperties,
    ShapeProperties,
)
from movici_simulation_core.base_model.config_helpers import to_spec
from movici_simulation_core.data_tracker.entity_group import EntityGroup
from movici_simulation_core.data_tracker.property import field, PUB, INIT, OPT
from shapely.geometry.base import BaseGeometry
from spatial_mapper.geometry import (
    PointCollection,
    LineStringCollection,
    GeometryCollection,
    ClosedPolygonCollection,
)


class OverlapEntity(EntityGroup, name=ed.Overlap):
    display_name = field(to_spec(DisplayName), flags=PUB)
    overlap_active = field(to_spec(Overlap_Active), flags=PUB)
    connection_from_id = field(to_spec(ConnectionProperties.FromId), flags=PUB)
    connection_to_id = field(to_spec(ConnectionProperties.ToId), flags=PUB)
    connection_from_reference = field(to_spec(ConnectionProperties.FromReference), flags=PUB)
    connection_to_reference = field(to_spec(ConnectionProperties.ToReference), flags=PUB)
    connection_from_dataset = field(to_spec(ConnectionProperties.FromDataset), flags=PUB)
    connection_to_dataset = field(to_spec(ConnectionProperties.ToDataset), flags=PUB)
    x = field(to_spec(PointProperties.PositionX), flags=PUB)
    y = field(to_spec(PointProperties.PositionY), flags=PUB)


class GeometryEntity(EntityGroup):
    reference = field(to_spec(Reference), flags=OPT)

    @abstractmethod
    def get_geometry(self) -> GeometryCollection:
        ...

    @abstractmethod
    def get_single_geometry(self, index: int) -> BaseGeometry:
        ...


class PointEntity(GeometryEntity):
    x = field(to_spec(PointProperties.PositionX), flags=INIT)
    y = field(to_spec(PointProperties.PositionY), flags=INIT)

    def get_geometry(self) -> PointCollection:
        return PointCollection(coord_seq=np.stack((self.x.array, self.y.array), axis=-1))

    def get_single_geometry(self, index: int) -> Point:
        return Point(self.x.array[index], self.y.array[index])


class LineEntity(GeometryEntity):
    line2d = field(to_spec(ShapeProperties.Linestring2d), flags=OPT)
    line3d = field(to_spec(ShapeProperties.Linestring3d), flags=OPT)

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

    def get_single_geometry(self, index: int) -> LineString:
        if self.line3d.is_initialized():
            csr = self.line3d.csr
        elif self.line2d.is_initialized():
            csr = self.line2d.csr
        else:
            raise RuntimeError(
                f"line2d or line3d needs to have data before get_geometry "
                f"is called on line entity {self.__entity_name__} "
            )
        return LineString(csr.slice([index]).data[:, 0:2])


class PolygonEntity(GeometryEntity):
    polygon = field(to_spec(ShapeProperties.Polygon), flags=INIT)

    def get_geometry(self) -> ClosedPolygonCollection:
        return ClosedPolygonCollection(
            coord_seq=self.polygon.csr.data, indptr=self.polygon.csr.row_ptr
        )

    def get_single_geometry(self, index: int) -> Polygon:
        return Polygon(self.polygon.csr.slice([index]).data[:, 0:2])


supported_geometry_types = {
    "point": PointEntity,
    "line": LineEntity,
    "polygon": PolygonEntity,
}
