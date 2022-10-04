import numpy as np
import pytest
from movici_geo_query.geometry import ClosedPolygonGeometry, LinestringGeometry, PointGeometry

from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.attribute import UniformAttribute
from movici_simulation_core.core.data_type import UNDEFINED, DataType
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.common.entity_groups import (
    LineEntity,
    PointEntity,
    PolygonEntity,
)
from movici_simulation_core.models.overlap_status.overlap_status import OverlapStatus


def get_point_entity(point_collection: PointGeometry) -> PointEntity:
    state = TrackedState()
    point = state.register_entity_group("ds", PointEntity("entity"))

    nb_points = len(point_collection.points)
    point.x.initialize(nb_points)
    point.y.initialize(nb_points)

    point.x[:] = point_collection.points[:, 0]
    point.y[:] = point_collection.points[:, 1]
    return point


def get_line_entity(line_collection: LinestringGeometry) -> LineEntity:
    state = TrackedState()
    line = state.register_entity_group("ds", LineEntity("entity"))
    line._linestring2d.initialize(len(line_collection.row_ptr) - 1)
    line._linestring2d.csr = TrackedCSRArray(line_collection.points, line_collection.row_ptr)
    return line


def get_polygon_entity(polygon_collection: ClosedPolygonGeometry) -> PolygonEntity:
    state = TrackedState()
    polygon = state.register_entity_group("ds", PolygonEntity("entity"))
    polygon._polygon_legacy.initialize(len(polygon_collection.row_ptr) - 1)
    polygon._polygon_legacy.csr = TrackedCSRArray(
        polygon_collection.points, polygon_collection.row_ptr
    )
    return polygon


@pytest.mark.parametrize(
    ["geometry_entity1", "geometry_entity2", "index1", "index2", "overlap_point"],
    [
        (
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0], [1, 1]])),
            0,
            0,
            (0, 0),
        ),
        (
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0], [1, 1]])),
            0,
            1,
            (0, 0.5),
        ),
        (
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_line_entity(
                LinestringGeometry([[0, 0], [0, 1], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            0,
            0,
            (0, 0),
        ),
        (
            get_point_entity(PointGeometry([[0, 0], [0, 1], [1, 0.5], [1, 1]])),
            get_line_entity(
                LinestringGeometry([[0, 0], [0, 1], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            2,
            1,
            (1, 0.5),
        ),
        (
            get_point_entity(PointGeometry([[0, 0], [0, 1], [2, 0.5], [1, 1]])),
            get_line_entity(
                LinestringGeometry([[0, 0], [0, 1], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            2,
            1,
            (1.5, 0.5),
        ),
        (
            get_line_entity(
                LinestringGeometry([[0, 0], [0, 1], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            get_line_entity(
                LinestringGeometry([[0.5, 0.5], [-0.5, 0.5], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            0,
            0,
            (0, 0.5),
        ),
        (
            get_line_entity(
                LinestringGeometry([[0, 0], [0, 1], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            get_line_entity(
                LinestringGeometry([[0.5, 0.5], [0.4, 0.5], [1, 0], [1, 1]], row_ptr=[0, 2, 4])
            ),
            0,
            0,
            (0.2, 0.5),
        ),
        (
            get_point_entity(PointGeometry([[0.5, 2]])),
            get_polygon_entity(
                ClosedPolygonGeometry([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]], row_ptr=[0, 5])
            ),
            0,
            0,
            (0.5, 1.5),
        ),
        (
            get_polygon_entity(
                ClosedPolygonGeometry([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]], row_ptr=[0, 5])
            ),
            get_polygon_entity(
                ClosedPolygonGeometry(
                    [[-10, -10], [-10, 10], [10, 10], [10, -10], [-10, -10]], row_ptr=[0, 5]
                )
            ),
            0,
            0,
            (0, 0),
        ),
        (
            get_polygon_entity(
                ClosedPolygonGeometry([[0, 0], [0, 1], [1, 1], [0, 0]], row_ptr=[0, 4])
            ),
            get_polygon_entity(
                ClosedPolygonGeometry([[10, 0], [10, 1], [11, 1], [10, 0]], row_ptr=[0, 4])
            ),
            0,
            0,
            (5.5, 1),
        ),
    ],
    ids=[
        "Two points at same position",
        "Middle of two points",
        "Point to vertex in line",
        "Point in middle of line",
        "Point near line",
        "Intersecting lines",
        "Line near line",
        "Point near polygon",
        "Point inside polygon",
        "Polygon to polygon",
    ],
)
def test_can_calculate_overlap_point(
    geometry_entity1, geometry_entity2, index1, index2, overlap_point
):
    assert (
        OverlapStatus._calculate_overlap_point(geometry_entity1, index1, geometry_entity2, index2)
        == overlap_point
    )


def uniform_attribute(array, dtype):
    return UniformAttribute(array, DataType(dtype, (), False))


@pytest.mark.parametrize(
    [
        "from_entities_active_status",
        "to_entities_active_status",
        "connection_from_indices",
        "connection_to_indices",
        "expected_status",
    ],
    [
        (
            uniform_attribute([1, 1, 1, 1], dtype=bool),
            uniform_attribute([1, 0, 0, 0], dtype=bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            uniform_attribute([1, 1, 0], dtype=bool),
        ),
        (
            uniform_attribute([1, 1, 1, 1], dtype=bool),
            uniform_attribute([1, 0, 0, 0], dtype=bool),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            uniform_attribute([], dtype=bool),
        ),
        (
            None,
            uniform_attribute([1, 0, 0, 0], dtype=bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            uniform_attribute([1, 1, 0], dtype=bool),
        ),
        (
            uniform_attribute([1, 0, 1, 1], dtype=bool),
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            uniform_attribute([1, 0, 0], dtype=bool),
        ),
        (
            None,
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            uniform_attribute([1, 1, 1], dtype=bool),
        ),
        (
            None,
            None,
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            uniform_attribute([], dtype=bool),
        ),
        (
            uniform_attribute([UNDEFINED[bool], 1, 1, 1], dtype=bool),
            uniform_attribute([1, UNDEFINED[bool], 0, 0], dtype=bool),
            np.array([0, 0, 1, 1]),
            np.array([0, 1, 0, 1]),
            uniform_attribute([UNDEFINED[bool], UNDEFINED[bool], 1, UNDEFINED[bool]], dtype=bool),
        ),
    ],
    ids=[
        "Can calculate overlap status",
        "Works without any connections",
        "Works without from overlap info",
        "Works without to overlap info",
        "Works without any overlap info",
        "Works without any overlap info or connections",
        "Works with undefined booleans",
    ],
)
def test_can_calculate_overlap_status(
    from_entities_active_status,
    to_entities_active_status,
    connection_from_indices,
    connection_to_indices,
    expected_status,
):
    output = OverlapStatus._calculate_active_overlaps(
        from_active_status=from_entities_active_status,
        connection_from_indices=connection_from_indices,
        to_active_status=to_entities_active_status,
        connection_to_indices=connection_to_indices,
        undefined_value=UNDEFINED[bool],
    )

    np.testing.assert_array_equal(output, expected_status)


@pytest.mark.parametrize(
    [
        "from_dataset_name",
        "to_dataset_name",
        "from_reference",
        "to_reference",
        "from_id",
        "to_id",
        "display_config",
        "expected",
    ],
    [
        (
            "ds a",
            "ds b",
            "ref x",
            "ref y",
            1,
            2,
            None,
            "Overlap from ds a reference ref x to ds b reference ref y",
        ),
        (
            "ds a",
            "ds b",
            "ref x",
            "ref y",
            1,
            2,
            "{from_dataset_name} {to_dataset_name} {from_reference} {to_reference}",
            "ds a ds b ref x ref y",
        ),
        (
            "ds a",
            "ds b",
            "ref x",
            "ref y",
            1,
            2,
            "{from_dataset_name} {to_dataset_name} {from_id} {to_id}",
            "ds a ds b 1 2",
        ),
    ],
    ids=[
        "Works without display_name_template",
        "Works with display_name_template",
        "Works with ids instead of references",
    ],
)
def test_can_generate_display_name(
    from_dataset_name,
    to_dataset_name,
    from_reference,
    to_reference,
    from_id,
    to_id,
    display_config,
    expected,
):
    assert (
        OverlapStatus._generate_display_name(
            from_dataset_name,
            [from_reference],
            [from_id],
            to_dataset_name,
            [to_reference],
            [to_id],
            display_config,
        )
        == expected
    )
