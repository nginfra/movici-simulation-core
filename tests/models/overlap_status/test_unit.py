import numpy as np
import pytest

from movici_simulation_core.models.overlap_status.overlap_status import (
    OverlapStatus,
    OverlapPropertiesToPublish,
)
from spatial_mapper.geometry import PointCollection, LineStringCollection


@pytest.mark.parametrize(
    ["geometry_collection1", "geometry_collection2", "index1", "index2", "overlap_point"],
    [
        (
            PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]]),
            PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]]),
            0,
            0,
            (0, 0),
        ),
        (
            PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]]),
            PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]]),
            0,
            1,
            (0, 0.5),
        ),
        (
            PointCollection([[0, 0], [0, 1], [1, 0], [1, 1]]),
            LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            0,
            0,
            (0, 0),
        ),
        (
            PointCollection([[0, 0], [0, 1], [1, 0.5], [1, 1]]),
            LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            2,
            1,
            (1, 0.5),
        ),
        (
            PointCollection([[0, 0], [0, 1], [2, 0.5], [1, 1]]),
            LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            2,
            1,
            (1.5, 0.5),
        ),
        (
            LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            LineStringCollection([[0.5, 0.5], [-0.5, 0.5], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            0,
            0,
            (0, 0.5),
        ),
        (
            LineStringCollection([[0, 0], [0, 1], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            LineStringCollection([[0.5, 0.5], [0.4, 0.5], [1, 0], [1, 1]], indptr=[0, 2, 4]),
            0,
            0,
            (0.2, 0.5),
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
    ],
)
def test_can_calculate_overlap_point(
    geometry_collection1, geometry_collection2, index1, index2, overlap_point
):
    assert (
        OverlapStatus._calculate_overlap_point(
            geometry_collection1, index1, geometry_collection2, index2
        )
        == overlap_point
    )


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
            np.array([1, 1, 1, 1], dtype=np.bool),
            np.array([1, 0, 0, 0], dtype=np.bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            np.array([1, 1, 0], dtype=np.bool),
        ),
        (
            np.array([1, 1, 1, 1], dtype=np.bool),
            np.array([1, 0, 0, 0], dtype=np.bool),
            np.array([], dtype=np.int),
            np.array([], dtype=np.int),
            -128,
            np.array([], dtype=np.bool),
        ),
        (
            None,
            np.array([1, 0, 0, 0], dtype=np.bool),
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            np.array([1, 1, 0], dtype=np.bool),
        ),
        (
            np.array([1, 0, 1, 1], dtype=np.bool),
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            np.array([1, 0, 0], dtype=np.bool),
        ),
        (
            None,
            None,
            np.array([0, 1, 1]),
            np.array([0, 0, 1]),
            -128,
            np.array([1, 1, 1], dtype=np.bool),
        ),
        (
            None,
            None,
            np.array([], dtype=np.int),
            np.array([], dtype=np.int),
            -128,
            np.array([], dtype=np.bool),
        ),
        (
            np.array([-128, 1, 1, 1], dtype=np.int8),
            np.array([1, -128, 0, 0], dtype=np.int8),
            np.array([0, 0, 1, 1]),
            np.array([0, 1, 0, 1]),
            -128,
            np.array([-128, -128, 1, -128], dtype=np.int8),
        ),
    ],
    ids=[
        "Can calculate overlap status",
        "Works without any connections",
        "Works without from overlap info",
        "Works without to overlap info",
        "Works without any overlap info",
        "Works without any overlap info or connections",
        "Works with undefined bools",
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
    assert np.all(
        OverlapStatus._calculate_active_overlaps(
            from_active_status=from_entities_active_status,
            connection_from_indices=connection_from_indices,
            to_active_status=to_entities_active_status,
            connection_to_indices=connection_to_indices,
            undefined_value=undefined_value,
        )
        == expected_status
    )


@pytest.mark.parametrize(
    [
        "from_entities_overlap_status",
        "overlap_active",
        "from_indices",
        "undefined_value",
        "expected_status",
    ],
    [
        (
            np.array([0, 0, 0], dtype=np.bool),
            np.array([1, 0, 0, 0, 0, 0, 0, 0, 1], dtype=np.bool),
            np.array([0, 0, 0, 1, 1, 1, 2, 2, 2]),
            -128,
            np.array([1, 0, 1], dtype=np.bool),
        ),
        (
            np.array([1, 1, 1], dtype=np.bool),
            np.array([1, 0, 0, 0, 0, 0, 0, 0, 1], dtype=np.bool),
            np.array([0, 0, 0, 1, 1, 1, 2, 2, 2]),
            -128,
            np.array([1, 1, 1], dtype=np.bool),
        ),
        (
            np.array([-128, -128, -128], dtype=np.int8),
            np.array([1, 0, 0, 0, 0, 0, 0, 0, 1], dtype=np.bool),
            np.array([0, 0, 0, 1, 1, 1, 2, 2, 2]),
            -128,
            np.array([1, 0, 1], dtype=np.bool),
        ),
        (
            np.array([-128, -128, -128], dtype=np.int8),
            np.array([-128, -128, 0, -128, -128, -128, 0, 0, 1], dtype=np.int8),
            np.array([0, 0, 0, 1, 1, 1, 2, 2, 2]),
            -128,
            np.array([0, 0, 1], dtype=np.int8),
        ),
    ],
    ids=[
        "Can calculate from entities overlap status",
        "Doesn't override preexisting overlaps",
        "Can calculate when initial from is undefined",
        "Can calculate when both are undefined",
    ],
)
def test_can_calculate_from_entities_overlap_status(
    from_entities_overlap_status,
    overlap_active,
    from_indices,
    undefined_value,
    expected_status,
):
    OverlapStatus._calculate_from_entities_overlap_status(
        overlap_active=overlap_active,
        from_indices=from_indices,
        overlap_undefined_value=undefined_value,
        from_entities_overlap_status=from_entities_overlap_status,
    )

    assert np.all(from_entities_overlap_status == expected_status)


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


@pytest.mark.parametrize(
    ["n", "expected"],
    [(0, 1), (1, 2), (2, 4), (3, 4), (4, 8), (6, 8), (7, 8), (8, 16), (789, 1024)],
)
def test_nearest_power_of_two(n, expected):
    assert OverlapPropertiesToPublish._get_next_power_of_two(n) == expected
