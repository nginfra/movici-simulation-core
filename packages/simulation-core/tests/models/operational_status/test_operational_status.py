import numpy as np
import pytest

from movici_simulation_core import DataType, TrackedState, UniformAttribute
from movici_simulation_core.core.attribute import AttributeOptions
from movici_simulation_core.models.common.entity_groups import (
    GridCellEntity,
    LineEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.models.operational_status.operational_status import (
    FloodingStatusModule,
    OperationalStatus,
)
from movici_simulation_core.testing import create_entity_group_with_data
from movici_simulation_core.testing.helpers import data_mask_compare


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


@pytest.fixture
def point_target_data():
    return {
        "id": [10, 11, 12],
        "geometry.x": [0.5, 1.5, 2.5],
        "geometry.y": [0.5, 0.5, 0.5],
        "geometry.z": [1, 2, -1],
    }


@pytest.fixture
def line_target_data():
    return {
        "id": [20, 21, 22, 23],
        "geometry.linestring_3d": [
            [[0.1, 0.5, 0.5], [0.2, 0.5, 1]],  # inside grid cell 0
            [[1.1, 0.5, 2], [1.2, 0.5, 2.5]],  # inside grid cell 1
            [[0.1, 0.5, 1], [1.2, 0.5, 0.5]],  # inside both grid cells
            [[0, 3, 0], [1, 3, 0]],  # outside both grid cells
        ],
    }


@pytest.fixture
def polygon_target_data():
    return {
        "id": [30],
        "geometry.polygon_3d": [
            [[0.1, 0.8, 0.5], [0.1, 0.1, 1], [1.2, 0.1, 2.5], [0.1, 0.8, 0.5]],
        ],
    }


@pytest.fixture
def state():
    return TrackedState()


@pytest.fixture
def flooding_cells(state, grid_data):
    cells = create_entity_group_with_data(
        GridCellEntity("grid_cells"), grid_data["cells"], state=state
    )
    points = create_entity_group_with_data(
        PointEntity("grid_points"), grid_data["points"], state=state
    )
    cells.set_points(points)
    return cells


@pytest.fixture
def points(state, point_target_data):
    return create_entity_group_with_data(
        PointEntity("target_points"), point_target_data, state=state
    )


@pytest.fixture
def lines(state, line_target_data):
    return create_entity_group_with_data(LineEntity("target_lines"), line_target_data, state=state)


@pytest.fixture
def polygons(state, polygon_target_data):
    return create_entity_group_with_data(
        PolygonEntity("target_polygons"), polygon_target_data, state=state
    )


class BaseTestFloodingStatusModule:
    @pytest.fixture
    def water_height(self, flooding_cells):
        return UniformAttribute(
            np.full((len(flooding_cells),), -9999, dtype=float),
            data_type=DataType(float),
            options=AttributeOptions(special=-9999),
        )

    @pytest.fixture
    def water_depth(self, target):
        rv = UniformAttribute(data=None, data_type=DataType(float))
        rv.initialize(len(target))
        return rv

    @pytest.fixture
    def module(self, flooding_cells, target, water_height, water_depth):
        rv = FloodingStatusModule(
            cells=flooding_cells, water_height=water_height, target=target, water_depth=water_depth
        )
        rv.initialize()
        return rv


class TestFloodingStatusModulePoints(BaseTestFloodingStatusModule):
    @pytest.fixture
    def target(self, points):
        return points

    def test_creates_mapping_on_initialize(self, module: FloodingStatusModule):
        np.testing.assert_array_equal(module.mapping.indices, [0, 1])
        np.testing.assert_array_equal(module.mapping.row_ptr, [0, 1, 2, 2])

    @pytest.mark.parametrize(
        "wh, wd",
        [
            (0, [0, 0, 0]),
            (1, [0, 0, 0]),
            (1.5, [0.5, 0, 0]),
            (2.5, [1.5, 0.5, 0]),
        ],
    )
    def test_calculates_water_depth(
        self, module: FloodingStatusModule, water_height, water_depth, wh, wd
    ):
        water_height[:] = wh
        module.update()
        np.testing.assert_array_equal(water_depth.array, wd)


class TestFloodingStatusModuleLines(BaseTestFloodingStatusModule):
    @pytest.fixture
    def target(self, lines):
        return lines

    def test_creates_mapping_on_initialize(self, module: FloodingStatusModule):
        np.testing.assert_array_equal(module.mapping.indices, [0, 0, 1, 1, 0, 1])
        np.testing.assert_array_equal(module.mapping.row_ptr, [0, 1, 2, 3, 4, 5, 6, 6, 6])

    @pytest.mark.parametrize(
        "wh, wd",
        [
            ([0, 0], [0, 0, 0, 0]),
            ([1, 1], [0.5, 0, 0.5, 0]),
            ([1.5, 1.5], [1.0, 0, 1.0, 0]),
            ([2.5, 2.5], [2.0, 0.5, 2.0, 0]),
            ([1.5, 2.5], [1.0, 0.5, 2.0, 0]),
        ],
    )
    def test_calculates_water_depth(
        self, module: FloodingStatusModule, water_height, water_depth, wh, wd
    ):
        water_height[:] = wh
        module.update()
        np.testing.assert_array_equal(water_depth.array, wd)


class TestFloodingStatusModulePolygons(BaseTestFloodingStatusModule):
    @pytest.fixture
    def target(self, polygons):
        return polygons

    def test_creates_mapping_on_initialize(self, module: FloodingStatusModule):
        np.testing.assert_array_equal(module.mapping.indices, [0, 0, 1, 0])
        np.testing.assert_array_equal(module.mapping.row_ptr, [0, 1, 2, 3, 4])

    @pytest.mark.parametrize(
        "wh, wd",
        [
            ([0, 0], [0]),
            ([1, 1], [0.5]),
            ([0, 3], [0.5]),
        ],
    )
    def test_calculates_water_depth(
        self, module: FloodingStatusModule, water_height, water_depth, wh, wd
    ):
        water_height[:] = wh
        module.update()
        np.testing.assert_array_equal(water_depth.array, wd)


class TestOperationalStatusModel:
    @pytest.fixture
    def init_data(self, polygon_target_data, grid_data):
        return [
            ["flooding_grid", {"flooding_grid": grid_data}],
            ["buildings", {"buildings": {"building_entities": polygon_target_data}}],
        ]

    @pytest.fixture
    def config(self):
        return {
            "entity_group": ["buildings", "building_entities"],
            "geometry": "polygon",
            "flooding": {
                "flooding_cells": ["flooding_grid", "cells"],
                "flooding_points": ["flooding_grid", "points"],
            },
        }

    @pytest.fixture
    def tester(self, create_model_tester, config):
        return create_model_tester(OperationalStatus, config)

    def test_data_mask(self, tester):
        data_mask = tester.initialize()
        assert data_mask_compare(data_mask) == data_mask_compare(
            {
                "pub": {
                    "buildings": {
                        "building_entities": ["flooding.water_depth"],
                    }
                },
                "sub": {
                    "flooding_grid": {
                        "cells": [
                            "grid.grid_points",
                            "reference",
                            "flooding.water_height",
                        ],
                        "points": [
                            "geometry.x",
                            "geometry.y",
                            "geometry.z",
                            "reference",
                        ],
                    },
                    "buildings": {
                        "building_entities": [
                            "geometry.polygon",
                            "geometry.polygon_2d",
                            "geometry.polygon_3d",
                            "reference",
                        ]
                    },
                },
            }
        )

    @pytest.mark.parametrize(
        "wh, wd",
        [
            ([-9999, -9999], [0]),
            ([1, 1], [0.5]),
            ([0, 3], [0.5]),
        ],
    )
    def test_update_model(self, tester, wh, wd):
        tester.initialize()
        result, _ = tester.update(
            0,
            {"flooding_grid": {"cells": {"id": [7, 8], "flooding.water_height": wh}}},
        )
        assert result == {
            "buildings": {"building_entities": {"id": [30], "flooding.water_depth": wd}}
        }
