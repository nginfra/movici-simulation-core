from collections import namedtuple

import numpy as np

from movici_simulation_core.core import DataType
from movici_simulation_core.types import DatasetData, EntityData

GEOMETRY_X = "geometry.x"
GEOMETRY_Y = "geometry.y"

GEOMETRY_ATTRIBUTES = [
    "geometry.linestring_2d",
    "geometry.linestring_3",
    "geometry.polygon",
    "geometry.polygon2d",
    "geometry.polygon3d",
]

BoundingBox = namedtuple("bounding_box", ("min_x", "min_y", "max_x", "max_y"))


def calculate_bounding_box_from_data(data: DatasetData):
    bounding_box = BoundingBox(1e20, 1e20, -1e20, -1e20)
    has_bounding_box = False
    for entity_data in data.values():
        if "geometry.x" in entity_data:
            min_x, max_x = DataType(float).get_min_max(_get_data(entity_data, "geometry.x"))
            _update_bounding_box(bounding_box, BoundingBox(min_x, None, max_x, None))
        if "geometry.y" in entity_data:
            min_y, max_y = DataType(float).get_min_max(_get_data(entity_data, "geometry.y"))
            _update_bounding_box(bounding_box, BoundingBox(None, min_y, None, max_y))
        for attr in GEOMETRY_ATTRIBUTES:
            if attr not in entity_data:
                continue
            data = _get_data(entity_data, attr)
            min_x, max_x = DataType(float).get_min_max()


def _get_data(entity_data: EntityData, key: str) -> np.ndarray:
    return entity_data["geometry.x"]["data"]


def _update_bounding_box(current: BoundingBox, new: BoundingBox) -> BoundingBox:
    return BoundingBox(
        min_x=min(current.min_x, new.min_x) if new.min_x is not None else current.min_x,
        min_y=min(current.min_y, new.min_y) if new.min_y is not None else current.min_y,
        max_x=max(current.max_x, new.max_x) if new.max_x is not None else current.max_x,
        max_y=max(current.max_y, new.max_y) if new.max_y is not None else current.max_y,
    )
