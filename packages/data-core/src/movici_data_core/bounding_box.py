import numpy as np

from movici_data_core.domain_model import BoundingBox
from movici_simulation_core import DataType
from movici_simulation_core.types import DatasetData, EntityData

GEOMETRY_X = "geometry.x"
GEOMETRY_Y = "geometry.y"

GEOMETRY_ATTRIBUTES = [
    "geometry.linestring_2d",
    "geometry.linestring_3d",
    "geometry.polygon",
    "geometry.polygon_2d",
    "geometry.polygon_3d",
]


def calculate_bounding_box_from_data(data: DatasetData) -> BoundingBox:
    bounding_box = BoundingBox.empty()
    for entity_data in data.values():
        if "geometry.x" in entity_data:
            min_x, max_x = DataType(float).get_min_max(_get_data(entity_data, "geometry.x"))
            bounding_box = calculate_new_bounding_box(
                bounding_box, BoundingBox(min_x, None, max_x, None)
            )
        if "geometry.y" in entity_data:
            min_y, max_y = DataType(float).get_min_max(_get_data(entity_data, "geometry.y"))
            bounding_box = calculate_new_bounding_box(
                bounding_box, BoundingBox(None, min_y, None, max_y)
            )
        for attr in GEOMETRY_ATTRIBUTES:
            if attr not in entity_data:
                continue
            data_array = _get_data(entity_data, attr)
            min_x, max_x = DataType(float).get_min_max(data_array[:, 0])
            min_y, max_y = DataType(float).get_min_max(data_array[:, 1])

            bounding_box = calculate_new_bounding_box(
                bounding_box, BoundingBox(min_x, min_y, min_y, max_y)
            )
    return bounding_box


def _get_data(entity_data: EntityData, key: str) -> np.ndarray:
    return entity_data[key]["data"]


def calculate_new_bounding_box(*bboxes: BoundingBox) -> BoundingBox:
    return BoundingBox(
        min_x=min((bbox.min_x for bbox in bboxes if bbox.min_x is not None), default=None),
        min_y=min((bbox.min_y for bbox in bboxes if bbox.min_y is not None), default=None),
        max_x=max((bbox.max_x for bbox in bboxes if bbox.max_x is not None), default=None),
        max_y=max((bbox.max_y for bbox in bboxes if bbox.max_y is not None), default=None),
    )
