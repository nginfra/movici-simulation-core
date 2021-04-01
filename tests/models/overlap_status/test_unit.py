import numpy as np
import pytest
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.property import UniformProperty, DataType
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.overlap_status.dataset import (
    PointEntity,
    LineEntity,
    PolygonEntity,
)

from movici_simulation_core.models.overlap_status.overlap_status import (
    OverlapStatus,
)
from spatial_mapper.geometry import (
    PointCollection,
    LineStringCollection,
    ClosedPolygonCollection,
)


def get_point_entity(point_collection: PointCollection) -> PointEntity:
    state = TrackedState()
    point = state.register_entity_group("ds", PointEntity("entity"))

    nb_points = len(point_collection.coord_seq)
    point.x.initialize(nb_points)
    point.y.initialize(nb_points)

    point.x[:] = point_collection.coord_seq[:, 0]
    point.y[:] = point_collection.coord_seq[:, 1]
    return point


def get_line_entity(line_collection: LineStringCollection) -> LineEntity:
    state = TrackedState()
    line = state.register_entity_group("ds", LineEntity("entity"))
    line.line2d.initialize(len(line_collection.indptr) - 1)
    line.line2d.csr = TrackedCSRArray(line_collection.coord_seq, line_collection.indptr)
    return line


def get_polygon_entity(polygon_collection: ClosedPolygonCollection) -> PolygonEntity:
    state = TrackedState()
    polygon = state.register_entity_group("ds", PolygonEntity("entity"))
    polygon.polygon.initialize(len(polygon_collection.indptr) - 1)
    polygon.polygon.csr = TrackedCSRArray(polygon_collection.coord_seq, polygon_collection.indptr)
    return polygon


@pytest.mark.parametrize(
    ["geometry_entity1", "geometry_entity2", "index1", "index2", "overlap_point"],
    [
        (
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]])),
            0,
            0,
            (0, 0),
        ),
        (
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]])),
            0,
            1,
            (0, 0.5),
        ),
        (
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]])),
            get_line_entity(
                LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            0,
            0,
            (0, 0),
        ),
        (
            get_point_entity(PointCollection([[0, 0], [0, 1], [1, 0.5], [1, 1]])),
            get_line_entity(
                LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            2,
            1,
            (1, 0.5),
        ),
        (
            get_point_entity(PointCollection([[0, 0], [0, 1], [2, 0.5], [1, 1]])),
            get_line_entity(
                LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            2,
            1,
            (1.5, 0.5),
        ),
        (
            get_line_entity(
                LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            get_line_entity(
                LineStringCollection([[0.5, 0.5], [-0.5, 0.5], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            0,
            0,
            (0, 0.5),
        ),
        (
            get_line_entity(
                LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            get_line_entity(
                LineStringCollection([[0.5, 0.5], [0.4, 0.5], [1, 0], [1, 1]], indptr=[0, 2, 4])
            ),
            0,
            0,
            (0.2, 0.5),
        ),
        (
            get_point_entity(PointCollection([[0.5, 2]])),
            get_polygon_entity(
                ClosedPolygonCollection([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]], indptr=[0, 5])
            ),
            0,
            0,
            (0.5, 1.5),
        ),
        (
            get_polygon_entity(
                ClosedPolygonCollection([[0, 0], [0, 1], [1, 1], [1, 0], [0, 0]], indptr=[0, 5])
            ),
            get_polygon_entity(
                ClosedPolygonCollection(
                    [[-10, -10], [-10, 10], [10, 10], [10, -10], [-10, -10]], indptr=[0, 5]
                )
            ),
            0,
            0,
            (0, 0),
        ),
        (
            get_polygon_entity(
                ClosedPolygonCollection([[0, 0], [0, 1], [1, 1], [0, 0]], indptr=[0, 4])
            ),
            get_polygon_entity(
                ClosedPolygonCollection([[10, 0], [10, 1], [11, 1], [10, 0]], indptr=[0, 4])
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


def uniform_property(array, dtype):
    return UniformProperty(array, DataType(dtype, (), False))


@pytest.mark.parametrize(
    [
        "from_entities_active_status",
        "to_entities_active_status",
        "connection_from_indices",
        "connection_to_indices",
        "undefined_value",
        "expected_status",
    ],
    [
        (
            uniform_property([1, 1, 1, 1], dtype=bool),
            uniform_property([1, 0, 0, 0], dtype=bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            uniform_property([1, 1, 0], dtype=bool),
        ),
        (
            uniform_property([1, 1, 1, 1], dtype=bool),
            uniform_property([1, 0, 0, 0], dtype=bool),
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            -128,
            uniform_property([], dtype=bool),
        ),
        (
            None,
            uniform_property([1, 0, 0, 0], dtype=bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            uniform_property([1, 1, 0], dtype=bool),
        ),
        (
            uniform_property([1, 0, 1, 1], dtype=bool),
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            uniform_property([1, 0, 0], dtype=bool),
        ),
        (
            None,
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            uniform_property([1, 1, 1], dtype=bool),
        ),
        (
            None,
            None,
            np.array([], dtype=np.int64),
            np.array([], dtype=np.int64),
            -128,
            uniform_property([], dtype=bool),
        ),
        (
            uniform_property([-128, 1, 1, 1], dtype=bool),
            uniform_property([1, -128, 0, 0], dtype=bool),
            np.array([0, 0, 1, 1]),
            np.array([0, 1, 0, 1]),
            -128,
            uniform_property([-128, -128, 1, -128], dtype=bool),
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
    undefined_value,
    expected_status,
):
    output = OverlapStatus._calculate_active_overlaps(
        from_active_status=from_entities_active_status,
        connection_from_indices=connection_from_indices,
        to_active_status=to_entities_active_status,
        connection_to_indices=connection_to_indices,
        undefined_value=undefined_value,
    )

    assert np.all(output == expected_status)


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
