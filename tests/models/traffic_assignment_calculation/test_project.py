import os
import sqlite3

import numpy as np
import pytest
from aequilibrae import Graph

from movici_simulation_core.models.traffic_assignment_calculation.collections import (
    NodeCollection,
    LinkCollection,
    AssignmentResultCollection,
)
from movici_simulation_core.models.traffic_assignment_calculation.project import (
    ProjectWrapper,
    AssignmentParameters,
)


@pytest.fixture
def project_dir():
    return os.path.dirname(__file__)


@pytest.fixture
def project(project_dir):
    project = ProjectWrapper(project_dir, remove_existing=True)
    try:
        yield project
    finally:
        project.close()


def test_can_create_empty_project(project_dir):
    project = ProjectWrapper(project_dir, remove_existing=True)
    assert len(project.get_nodes().ids) == 0
    assert len(project.get_links().ids) == 0


def test_can_create_project_after_deletion(project_dir):
    project = ProjectWrapper(project_dir, remove_existing=True)
    project.close()
    ProjectWrapper(project_dir, remove_existing=True)


def test_closes_db_after_deletion(project_dir):
    project = ProjectWrapper(project_dir, remove_existing=True)
    db = project._db
    del project

    with pytest.raises(sqlite3.ProgrammingError):
        db.cursor()


def test_can_add_nodes(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2], is_centroids=[1, 1, 0], geometries=[[1, 0], [0, 0], [0.5, 1.5]]
    )

    project.add_nodes(nodes)
    resulting_nodes = project.get_nodes()

    assert np.array_equal(resulting_nodes.ids, nodes.ids)
    assert np.array_equal(resulting_nodes.is_centroids, nodes.is_centroids)


# TODO add multiple nodes, add multiple links


def test_can_add_links(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2, 3, 4],
        is_centroids=[1, 1, 1, 1, 1],
        geometries=[[0, 0], [1, 0], [1, 1], [0.5, 0.5], [10, 10]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1, 2, 3],
        from_nodes=[1, 0, 0],
        to_nodes=[0, 2, 3],
        directions=[True, True, False],
        geometries=[[[1, 0], [0, 0]], [[0, 0], [1, 1]], [[0, 0], [0.1, 1.0], [0.5, 0.5]]],
    )
    project.add_links(links)

    resulting_links = project.get_links()

    assert np.array_equal(resulting_links.ids, links.ids)
    assert np.array_equal(resulting_links.from_nodes, links.from_nodes)
    assert np.array_equal(resulting_links.to_nodes, links.to_nodes)
    assert np.array_equal(resulting_links.directions, links.directions)


def test_can_multiple_nodes_and_links(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1],
        is_centroids=[1, 1],
        geometries=[[0, 0], [1, 0]],
    )
    project.add_nodes(nodes)

    nodes = NodeCollection(
        ids=[2, 3, 4],
        is_centroids=[1, 1, 1],
        geometries=[[1, 1], [0.5, 0.5], [10, 10]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1, 2],
        from_nodes=[1, 0],
        to_nodes=[0, 2],
        directions=[True, True],
        geometries=[[[1, 0], [0, 0]], [[0, 0], [1, 1]]],
    )
    project.add_links(links)

    links = LinkCollection(
        ids=[3],
        from_nodes=[0],
        to_nodes=[3],
        directions=[False],
        geometries=[[[0, 0], [0.1, 1.0], [0.5, 0.5]]],
    )
    project.add_links(links)

    resulting_links = project.get_links()

    assert np.array_equal(resulting_links.ids, [1, 2, 3])
    assert np.array_equal(resulting_links.from_nodes, [1, 0, 0])
    assert np.array_equal(resulting_links.to_nodes, [0, 2, 3])
    assert np.array_equal(resulting_links.directions, [True, True, False])


def test_can_add_numpy_collections(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=np.array([0, 1, 2, 3, 4]),
        is_centroids=np.array([1, 1, 1, 1, 1]),
        geometries=[[0, 0], [1, 0], [1, 1], [0.5, 0.5], [10, 10]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=np.array([1, 2, 3]),
        from_nodes=np.array([1, 0, 0]),
        to_nodes=np.array([0, 2, 3]),
        directions=np.array([True, True, False], dtype=bool),
        geometries=[[[1, 0], [0, 0]], [[0, 0], [1, 1]], [[0, 0], [0.1, 1.0], [0.5, 0.5]]],
    )
    project.add_links(links)

    resulting_links = project.get_links()

    assert np.array_equal(resulting_links.ids, links.ids)
    assert np.array_equal(resulting_links.from_nodes, links.from_nodes)
    assert np.array_equal(resulting_links.to_nodes, links.to_nodes)
    assert np.array_equal(resulting_links.directions, links.directions)


def test_can_correct_rounding_error_in_geometries(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1],
        is_centroids=[1, 1],
        geometries=[[0, 0], [1, 0]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1],
        from_nodes=[0],
        to_nodes=[1],
        directions=[True],
        geometries=[[[0.0000001, 0], [1.5, 2], [1.0000001, 0]]],
    )
    # todo add warning if geometries are wildly different
    project.add_links(links)

    assert np.array_equal(project.get_nodes().ids, [0, 1])

    resulting_links = project.get_links()

    assert np.array_equal(resulting_links.from_nodes, links.from_nodes)
    assert np.array_equal(resulting_links.to_nodes, links.to_nodes)


def test_can_build_graph(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2, 3],
        is_centroids=[1, 1, 1, 1],
        geometries=[[0, 0], [1, 0], [1, 1], [0.5, 0.5]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1, 102, 103],
        from_nodes=[1, 0, 0],
        to_nodes=[0, 2, 3],
        directions=[True, True, False],
        geometries=[[[1, 0], [0, 0]], [[0, 0], [1, 1]], [[0, 0], [0.1, 1.0], [0.5, 0.5]]],
        max_speeds=[0.1, 0.25, 1],
        capacities=[1, 10, 5],
    )
    project.add_links(links)

    graph = project.build_graph()
    assert isinstance(graph, Graph)


def test_can_convert_od_matrix(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2],
        is_centroids=[1, 1, 1],
        geometries=[[0, 0], [1, 0], [1, 1]],
    )
    project.add_nodes(nodes)

    od_matrix = np.array([[0, 5, 4], [1.5, 0, 1], [0, 0, 0]])

    ae_matrix = project.convert_od_matrix(od_matrix, "car_demand")

    assert ae_matrix.zones == 3
    assert np.array_equal(ae_matrix.index, [1, 2, 3])
    assert np.array_equal(ae_matrix.matrix_view, od_matrix)


def test_can_convert_partial_od_matrix(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2],
        is_centroids=[1, 0, 1],
        geometries=[[0, 0], [1, 0], [1, 1]],
    )
    project.add_nodes(nodes)

    od_matrix = np.array([[0, 5], [0, 0]])

    ae_matrix = project.convert_od_matrix(od_matrix, "matrix_name")

    assert ae_matrix.zones == 2
    assert np.array_equal(ae_matrix.index, [1, 3])
    assert np.array_equal(ae_matrix.matrix_view, od_matrix)


def test_can_calculate_free_flow_time(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2, 3],
        is_centroids=[1, 1, 1, 1],
        geometries=[[97700, 434000], [97701, 434000], [97702, 434000], [97703, 434000]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1, 102, 103],
        from_nodes=[1, 0, 0],
        to_nodes=[0, 2, 3],
        directions=[True, True, False],
        geometries=[
            [[97701, 434000], [97700, 434000]],
            [[97700, 434000], [97702, 434000]],
            [[97700, 434000], [97704, 434000], [97703, 434000]],
        ],
        max_speeds=[10, 25, 100],
        capacities=[1, 10, 5],
    )

    project.add_links(links)
    free_flow_times = (
        project.add_free_flow_times()
    )  # todo rename to calculate_* and return early if already called
    assert np.allclose(free_flow_times, [0.1, 0.08, 0.05], rtol=1e-2)


def test_can_assign_traffic(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2],
        is_centroids=[1, 1, 1],
        geometries=[[97700, 434000], [97701, 434000], [97702, 434000]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1, 102, 103, 104],
        from_nodes=[1, 0, 1, 0],
        to_nodes=[0, 2, 2, 1],
        directions=[True, True, False, False],
        geometries=[
            [[97701, 434000], [97700, 434000]],
            [[97700, 434000], [97702, 434000]],
            [[97702, 434000], [97704, 434000], [97700, 434000]],
            [[97700, 434000], [97700, 434000]],
        ],
        max_speeds=[10, 25, 100, 10],
        capacities=[50, 100, 50, 10],
    )
    project.add_links(links)
    project.build_graph()

    od_matrix_passenger = np.array([[0, 20, 0], [5, 0, 0], [0, 100, 0]])
    od_matrix_cargo = np.array([[0, 10, 10], [10, 0, 10], [10, 10, 0]])

    results = project.assign_traffic(od_matrix_passenger, od_matrix_cargo, AssignmentParameters())

    assert isinstance(results, AssignmentResultCollection)
    assert np.array_equal(results.ids, [1, 102, 103, 104])
    assert np.allclose(results.passenger_flow, [4.1667, 20, 120, 0.8333], atol=0.01)
    assert np.allclose(results.cargo_flow, [25, 30, 30, 5], atol=0.01)
    assert np.all(results.congested_time > 0)
    assert np.all(results.delay_factor > 0)
    assert np.all(results.volume_to_capacity > 0)
    assert np.all(results.passenger_car_unit > 0)
