import numpy as np
import pytest
from movici_geo_query import ClosedPolygonGeometry, OpenPolygonGeometry

from movici_simulation_core import TrackedState
from movici_simulation_core.models.common.entity_groups import (
    GridCellEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.testing import create_entity_group_with_data


@pytest.fixture
def grid_data():
    """

    4---3---6
    | 7 | 8 |
    1---2---5

    """
    return {
        "points": {
            "id": [1, 2, 3, 4, 5, 6],
            "geometry.x": [0, 1, 1, 0, 2, 2],
            "geometry.y": [0, 0, 1, 1, 0, 1],
        },
        "cells": {
            "id": [7, 8],
            "grid.grid_points": [
                [1, 2, 3, 4],
                [2, 5, 6, 3],
            ],
        },
    }


class TestGridCellEntity:
    @pytest.fixture
    def cells(self, grid_data):
        state = TrackedState()
        cells = create_entity_group_with_data(
            GridCellEntity("cells"), grid_data["cells"], state=state
        )
        points = create_entity_group_with_data(
            PointEntity("points"), grid_data["points"], state=state
        )
        cells.set_points(points)
        return cells

    def test_get_geometry(self, cells: GridCellEntity):
        geom = cells.get_geometry()
        assert isinstance(geom, OpenPolygonGeometry)

    def test_geometry_has_polygon_data(self, cells):
        geom: OpenPolygonGeometry = cells.get_geometry()
        np.testing.assert_array_equal(
            geom.points, [[0, 0], [1, 0], [1, 1], [0, 1], [1, 0], [2, 0], [2, 1], [1, 1]]
        )
        np.testing.assert_array_equal(geom.row_ptr, [0, 4, 8])


class TestPolygonEntity:
    polygon_data = {
        "2d": [
            [[0, 0], [1, 0], [1, 1], [0, 0]],
            [[2, 0], [3, 0], [3, 1], [2, 0]],
        ],
        "3d": [
            [[0, 0, 0], [1, 0, 1], [1, 1, 1], [0, 0, 0]],
            [[2, 0, 0], [3, 0, 1], [3, 1, 1], [2, 0, 0]],
        ],
    }

    @pytest.mark.parametrize(
        "attribute, data, dimensions",
        [
            ("geometry.polygon", polygon_data["2d"], 2),
            ("geometry.polygon_2d", polygon_data["2d"], 2),
            ("geometry.polygon_3d", polygon_data["3d"], 3),
        ],
    )
    def test_get_polygon_at_certain_dimensions(self, attribute, data, dimensions):
        entity_group = create_entity_group_with_data(
            PolygonEntity("polygons"), {"id": [10, 11], attribute: data}
        )
        assert entity_group.dimensions() == dimensions

    @pytest.mark.parametrize(
        "attribute, data",
        [
            ("geometry.polygon", polygon_data["2d"]),
            ("geometry.polygon_2d", polygon_data["2d"]),
            ("geometry.polygon_3d", polygon_data["3d"]),
        ],
    )
    def test_get_polygon_geometry(self, attribute, data):
        entity_group = create_entity_group_with_data(
            PolygonEntity("polygons"), {"id": [10, 11], attribute: data}
        )
        geom = entity_group.get_geometry()

        assert isinstance(geom, ClosedPolygonGeometry)

        np.testing.assert_array_equal(
            geom.points, [[0, 0], [1, 0], [1, 1], [0, 0], [2, 0], [3, 0], [3, 1], [2, 0]]
        )
        np.testing.assert_array_equal(geom.row_ptr, [0, 4, 8])

    @pytest.mark.parametrize(
        "attribute, data",
        [
            ("geometry.polygon", polygon_data["2d"]),
            ("geometry.polygon_2d", polygon_data["2d"]),
            ("geometry.polygon_3d", polygon_data["3d"]),
        ],
    )
    def test_get_single_geometry(self, attribute, data):
        entity_group = create_entity_group_with_data(
            PolygonEntity("polygons"), {"id": [10, 11], attribute: data}
        )
        geom = entity_group.get_single_geometry(0)
        assert geom.bounds == (0.0, 0.0, 1.0, 1.0)

    def test_geometry_slice(self):
        polygon_data = self.polygon_data["2d"]
        entity_group = create_entity_group_with_data(
            PolygonEntity("polygons"),
            {"id": [10, 11], "geometry.polygon_2d": polygon_data},
        )
        np.testing.assert_array_equal(entity_group.get_geometry([1]).points, polygon_data[1])
