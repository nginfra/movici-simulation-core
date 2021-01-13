from abc import abstractmethod
from collections import Iterable
from typing import Type, Optional, cast

import numpy as np

import model_engine.dataset_manager.dataset_definition as dd
import model_engine.dataset_manager.entity_definition as ed
import model_engine.dataset_manager.property_definition as pd
from model_engine.dataset_manager import Property
from model_engine.dataset_manager.dataset_handler import DataSet, DataEntityHandler
from model_engine.dataset_manager.numba_functions import slice_compressed_data
from model_engine.dataset_manager.property_definition import (
    DisplayName,
    ConnectionProperties,
    Reference,
    Overlap_Active,
    PointProperties,
    ShapeProperties,
)
from spatial_mapper.geometry import PointCollection, LineStringCollection, GeometryCollection


class OverlapEntity(DataEntityHandler):
    entity_group_name = ed.Overlap
    init = True
    calc = False
    display_name = DisplayName(init=False, pub=True)
    overlap_active = Overlap_Active(init=False, pub=True)
    connection_from_id = ConnectionProperties.FromId(init=False, pub=True)
    connection_to_id = ConnectionProperties.ToId(init=False, pub=True)
    connection_from_reference = ConnectionProperties.FromReference(init=False, pub=True)
    connection_to_reference = ConnectionProperties.ToReference(init=False, pub=True)
    connection_from_dataset = ConnectionProperties.FromDataset(init=False, pub=True)
    connection_to_dataset = ConnectionProperties.ToDataset(init=False, pub=True)
    x = PointProperties.PositionX(init=False, pub=True)
    y = PointProperties.PositionY(init=False, pub=True)


class OverlapDataset(DataSet):
    data_entity_types = [OverlapEntity]
    dataset_type = dd.Overlap


class GeometryEntity(DataEntityHandler):
    entity_group_name: str = None
    init = True
    calc = True
    reference = Reference(init=True)
    overlap_active = Overlap_Active(init=False, pub=True)
    active_status: Property = None


class PointEntity(GeometryEntity):
    x = PointProperties.PositionX(sub=True)
    y = PointProperties.PositionY(sub=True)


class Line3dEntity(GeometryEntity):
    line3d = ShapeProperties.Linestring3d(sub=True)


class GeometryDataset(DataSet):
    dataset_type = ""
    geometry: GeometryCollection
    data_entity_types = []

    @abstractmethod
    def get_geometry(self, indices=None) -> GeometryCollection:
        pass

    @property
    def entity(self) -> GeometryEntity:
        return cast(GeometryEntity, list(self.data.values())[0])


class PointDataset(GeometryDataset):
    def get_geometry(self, indices=None) -> PointCollection:
        entity_cls = self.data_entity_types[0]
        point_entity = cast(PointEntity, self.data[entity_cls])
        x = point_entity.x.data
        y = point_entity.y.data
        if indices is not None:
            if not isinstance(indices, Iterable):
                indices = [indices]
            x = x[indices]
            y = y[indices]
        return PointCollection(coord_seq=np.stack((x, y), axis=-1))


class LineDataset(GeometryDataset):
    def get_geometry(self, indices=None):
        entity_cls = self.data_entity_types[0]
        line_entity = cast(Line3dEntity, self.data[entity_cls])
        line3d = line_entity.line3d
        line2d_data = line3d.data[:, 0:2]
        indptr = line3d.indptr
        if indices is not None:
            if not isinstance(indices, Iterable):
                indices = [indices]
                data, ptr = slice_compressed_data(line2d_data, indptr, np.array(indices), (2,))
                return LineStringCollection(coord_seq=data, indptr=ptr)
        return LineStringCollection(coord_seq=line2d_data, indptr=indptr)


def get_geometry_entity_cls(
    entity_name: str,
    entity_base: Type[GeometryEntity],
    active_property: str,
    active_component: Optional[str] = None,
) -> Type[GeometryEntity]:

    return cast(
        Type[GeometryEntity],
        type(
            entity_name,
            (entity_base,),
            {
                "entity_group_name": entity_name,
                "active_status": get_dynamic_property(active_property, active_component)(
                    init=False, sub=True
                ),
            },
        ),
    )


def get_geometry_dataset_cls(
    class_name: str,
    entity_name: str,
    geom_type: str,
    active_property: str,
    active_component: Optional[str] = None,
) -> Type[DataSet]:

    base_classes = {
        "points": (PointDataset, PointEntity),
        "lines": (LineDataset, Line3dEntity),
    }
    dataset_base, entity_base = base_classes[geom_type]
    entity_cls = get_geometry_entity_cls(
        entity_name, entity_base, active_property, active_component
    )

    return cast(
        Type[DataSet],
        type(
            class_name,
            (dataset_base,),
            {"dataset_type": "", "data_entity_types": [entity_cls]},
        ),
    )


def get_field_name(property_name: str) -> str:
    return property_name.replace("_", " ").title().replace(" ", "").replace(".", "_")


def get_dynamic_property(
    property_name: str, component_name: Optional[str] = None
) -> Type[Property]:

    root_obj = pd
    if component_name is not None:
        root_obj = getattr(root_obj, get_field_name(component_name))

    property_class_name = get_field_name(property_name)
    return getattr(root_obj, property_class_name)
