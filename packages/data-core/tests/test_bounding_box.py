import typing as t

from movici_data_core.bounding_box import (
    calculate_bounding_box_from_data,
    calculate_new_bounding_box,
)
from movici_data_core.domain_model import BoundingBox
from movici_simulation_core.testing import dataset_data_to_numpy
from movici_simulation_core.types import DatasetData


def test_get_bounding_box_from_data():
    dataset_data = dataset_data_to_numpy(
        {
            "some_entities": {
                "geometry.x": [1, 2, 3],
                "geometry.y": [3, 4, 5],
            },
            "more_entities": {
                "geometry.polygon_2d": [
                    [-1, -2],
                    [-1, 0],
                    [-1, 0],
                    [-1, 0],
                ],
                "geometry.linestring_3d": [
                    [-1, -3, 4],
                    [-1, -4, 5],
                    [-1, -4, 5],
                    [-1, -4, 5],
                    [-1, -4, 5],
                ],
            },
        }
    )
    assert calculate_bounding_box_from_data(t.cast(DatasetData, dataset_data)) == BoundingBox(
        -1, -4, 3, 5
    )


def test_calculate_new_bounding_box():
    assert calculate_new_bounding_box(
        BoundingBox(0, 0, 1, 1),
        BoundingBox(-1, -1, 0, 0),
    ) == BoundingBox(-1, -1, 1, 1)
