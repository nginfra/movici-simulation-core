import typing as t

import pytest

from movici_data_core.bounding_box import (
    calculate_bounding_box_from_data,
    calculate_new_bounding_box,
)
from movici_data_core.domain_model import BoundingBox
from movici_simulation_core import (
    AttributeSchema,
    AttributeSpec,
    DataType,
    EntityInitDataFormat,
)
from movici_simulation_core.types import DatasetData


@pytest.fixture
def serializer():
    return EntityInitDataFormat(
        AttributeSchema(
            [
                AttributeSpec("geometry.x", float),
                AttributeSpec("geometry.y", float),
                AttributeSpec("geometry.z", float),
                AttributeSpec("geometry.polygon_2d", data_type=DataType(float, (2,), csr=True)),
                AttributeSpec("geometry.polygon_3d", data_type=DataType(float, (3,), csr=True)),
                AttributeSpec("geometry.linestring_2d", data_type=DataType(float, (2,), csr=True)),
                AttributeSpec("geometry.linestring_3d", data_type=DataType(float, (3,), csr=True)),
            ]
        )
    )


@pytest.mark.parametrize(
    "data, expected",
    [
        ({"geometry.x": [1, 2, 3], "geometry.y": [4, 4, 5]}, BoundingBox(1, 4, 3, 5)),
        (
            {
                "geometry.polygon_2d": [[[-1, 2], [1, -2]]],
            },
            BoundingBox(-1, -2, 1, 2),
        ),
        (
            {
                "geometry.polygon_3d": [[[-1, 2, -3], [1, -2, 5]]],
            },
            BoundingBox(-1, -2, 1, 2),
        ),
        (
            {
                "geometry.polygon_3d": [],
            },
            BoundingBox(None, None, None, None),
        ),
        (
            {
                "geometry.polygon_2d": [None, None],
            },
            BoundingBox(None, None, None, None),
        ),
    ],
)
def test_get_bounding_box_from_data(data, expected, serializer: EntityInitDataFormat):
    dataset_data = serializer.load_data_section({"some_entities": data})
    assert calculate_bounding_box_from_data(t.cast(DatasetData, dataset_data)) == expected


def test_get_bounding_box_from_data_from_multiple_entity_groups(serializer: EntityInitDataFormat):
    dataset_data = serializer.load_data_section(
        {
            "some_entities": {
                "geometry.x": [1, 2, 3],
                "geometry.y": [3, 4, 5],
            },
            "more_entities": {
                "geometry.polygon_2d": [
                    [
                        [-1, -2],
                        [-1, 0],
                        [-1, 0],
                        [-1, 0],
                    ]
                ],
                "geometry.linestring_3d": [
                    [
                        [-1, -3, 4],
                        [-1, -4, 5],
                        [-1, -4, 5],
                        [-1, -4, 5],
                        [-1, -4, 5],
                    ]
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
