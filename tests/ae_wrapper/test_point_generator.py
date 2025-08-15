import numpy as np

from movici_simulation_core.integrations.ae.point_generator import PointGenerator


def test_can_add_points():
    point_set = PointGenerator()
    point_set.add_points(np.array([[0.0, 0.0], [1.0, 1.0]]))

    assert point_set.point_count == 2


def test_can_generate_points():
    point_set = PointGenerator()
    point_set.add_points(np.array([[0.0, 0.0], [1.0, 1.0]]))

    assert np.array_equal(point_set.generate_and_add([2.0, 2.0]), [2.0, 2.0])
    assert np.array_equal(point_set.generate_and_add([3.0, 3.0]), [3.0, 3.0])
    assert point_set.point_count == 4


def test_can_generate_without_adding():
    point_set = PointGenerator()

    assert np.array_equal(point_set.generate_and_add([2.0, 2.0]), [2.0, 2.0])
    assert np.array_equal(point_set.generate_and_add([3.0, 3.0]), [3.0, 3.0])
    assert point_set.point_count == 2


def test_can_generate_points_with_overlap_1_point():
    point_set = PointGenerator(increment=0.1)
    point_set.add_points(np.array([[0, 0], [1, 1]]))

    assert np.array_equal(point_set.generate_and_add([0.0, 0.0]), [0.1, 0.1])
    assert np.array_equal(point_set.generate_and_add([0.0, 0.0]), [0.2, 0.2])
    assert point_set.point_count == 4


def test_can_generate_points_with_overlap_2_points():
    point_set = PointGenerator(increment=0.5)
    point_set.add_points(np.array([[0, 0], [1, 1]]))

    assert np.array_equal(point_set.generate_and_add([0.0, 0.0]), [0.5, 0.5])
    assert np.array_equal(point_set.generate_and_add([0.0, 0.0]), [1.5, 1.5])
    assert point_set.point_count == 4
