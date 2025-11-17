import shutil
import sys
from pathlib import Path

import numpy as np
import pytest
from _pytest.fixtures import SubRequest
from aequilibrae import Graph

from movici_simulation_core.integrations.ae.collections import (
    AssignmentResultCollection,
    LinkCollection,
    NodeCollection,
)
from movici_simulation_core.integrations.ae.project import AssignmentParameters, ProjectWrapper


@pytest.fixture(autouse=True)
def patch_aquilibrae(patch_aequilibrae):
    return patch_aequilibrae


@pytest.fixture
def project_dir(tmp_path):
    return tmp_path


def delete_project_if_exists(project_dir):
    path = Path(project_dir, "ae_project_dir")
    if path.exists():
        shutil.rmtree(path)


@pytest.fixture
def project(project_dir):
    delete_project_if_exists(project_dir)
    with ProjectWrapper(project_dir, "ae_project_dir", delete_on_close=True) as project:
        yield project


def test_can_create_empty_project(project_dir):
    delete_project_if_exists(project_dir)
    with ProjectWrapper(project_dir, "ae_project_dir", delete_on_close=True) as project:
        assert len(project.get_nodes().ids) == 0
        assert len(project.get_links().ids) == 0


@pytest.mark.skipif(
    sys.platform.startswith("win32"), reason="Aequilbrae cleanup fails under windows"
)
def test_can_create_project_after_deletion(project_dir):
    delete_project_if_exists(project_dir)
    with ProjectWrapper(project_dir, "ae_project_dir", delete_on_close=True) as project:
        project.close()
    with ProjectWrapper(project_dir, "ae_project_dir", delete_on_close=True):
        pass


def test_closes_db_after_deletion(project_dir):
    delete_project_if_exists(project_dir)
    with ProjectWrapper(project_dir, "ae_project_dir", delete_on_close=True) as project:
        ae_project = project._project

    with pytest.raises(FileNotFoundError):
        with ae_project.db_connection:
            pass


def test_can_add_nodes(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1, 2], is_centroids=[1, 1, 0], geometries=[[1, 0], [0, 0], [0.5, 1.5]]
    )

    project.add_nodes(nodes)
    resulting_nodes = project.get_nodes()

    assert np.array_equal(resulting_nodes.ids, nodes.ids)
    assert np.array_equal(resulting_nodes.is_centroids, nodes.is_centroids)


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
        directions=[1, 0, -1],
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
    project.add_links(links)

    assert np.array_equal(project.get_nodes().ids, [0, 1])

    resulting_links = project.get_links()

    assert np.array_equal(resulting_links.from_nodes, links.from_nodes)
    assert np.array_equal(resulting_links.to_nodes, links.to_nodes)


def test_raises_if_mismatch_in_geometries(project: ProjectWrapper):
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
        geometries=[[[1, 0], [1.5, 2], [1, 0]]],
    )

    with pytest.raises(ValueError):
        project.add_links(links)

    links = LinkCollection(
        ids=[1],
        from_nodes=[0],
        to_nodes=[1],
        directions=[True],
        geometries=[[[0, 0], [1.5, 2], [0, 0]]],
    )

    with pytest.raises(ValueError):
        project.add_links(links)


def test_raises_if_wrong_connecting_node_ids(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[0, 1],
        is_centroids=[1, 1],
        geometries=[[0, 0], [1, 0]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[1],
        from_nodes=[3],
        to_nodes=[0],
        directions=[1],
        geometries=[[[3, 0], [0, 0]]],
    )

    with pytest.raises(ValueError):
        project.add_links(links)

    links = LinkCollection(
        ids=[1],
        from_nodes=[1],
        to_nodes=[2],
        directions=[1],
        geometries=[[[1, 0], [2, 0]]],
    )

    with pytest.raises(ValueError):
        project.add_links(links)


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

    graph = project.build_graph("speed")
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
    free_flow_times = project.calculate_free_flow_times()
    assert np.allclose(free_flow_times, [0.1, 0.08, 0.05], rtol=1e-2)


class TestTrafficAssignment:
    @pytest.fixture
    def project(self, project):
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
            directions=[1, 1, -1, -1],
            geometries=[
                [[97701, 434000], [97700, 434000]],
                [[97700, 434000], [97702, 434000]],
                [[97701, 434000], [97704, 434000], [97702, 434000]],
                [[97700, 434000], [97701, 434000]],
            ],
            max_speeds=[10, 25, 100, 10],
            capacities=[50, 100, 50, 10],
        )
        project.add_links(links)
        project.add_column("free_flow_time", project.calculate_free_flow_times())
        project.build_graph("free_flow_time", block_centroid_flows=False)
        return project

    @pytest.fixture
    def od_passenger(self):
        return np.array([[0, 20, 0], [5, 0, 0], [0, 100, 0]])

    @pytest.fixture
    def od_cargo(self):
        return np.array([[0, 10, 10], [10, 0, 10], [10, 10, 0]])

    def test_can_assign_traffic(self, project: ProjectWrapper, od_passenger, od_cargo):
        results = project.assign_traffic(
            od_passenger, od_cargo, AssignmentParameters(vdf_alpha=0.15)
        )

        assert isinstance(results, AssignmentResultCollection)
        assert np.array_equal(results.ids, [1, 102, 103, 104])
        assert np.allclose(results.passenger_flow, [4.1667, 20, 120, 0.8333], atol=0.01)
        assert np.allclose(results.cargo_flow, [25, 30, 30, 5], atol=0.01)
        assert np.allclose(results.congested_time, [[0.117, 0.084, 1.227, 0.117]], atol=5e-3)
        assert np.allclose(results.delay_factor, [1.17102242, 1.05272956, 24.55614978, 1.17102232])
        assert np.allclose(results.volume_to_capacity, [1.03333336, 0.77, 3.54, 1.0333332])
        assert np.allclose(results.passenger_car_unit, [51.66666798, 77, 177, 10.33333202])

    @pytest.mark.parametrize("parameters", [AssignmentParameters(vdf_alpha=0.64)])
    def test_assign_traffic_with_different_parameters(
        self, project: ProjectWrapper, od_passenger, od_cargo, parameters
    ):

        results = project.assign_traffic(od_passenger, od_cargo, parameters)

        assert np.array_equal(results.ids, [1, 102, 103, 104])
        assert np.allclose(
            results.delay_factor, [1.72969568, 1.22497946, 101.50623908, 1.72969523]
        )

    def test_assign_traffic_with_links_excluded(self, project: ProjectWrapper):
        od_passenger = np.array([[0, 0, 0], [1, 0, 0], [0, 0, 0]], dtype=float)
        od_cargo = np.zeros_like(od_passenger)
        project.exclude_segments([104])
        results = project.assign_traffic(od_passenger, od_cargo, AssignmentParameters())
        assert np.allclose(results.passenger_flow, [1, 0, 0, 0], atol=0.01)


@pytest.fixture
def p(request: SubRequest):
    """
    Chooser for project parametrization
    """
    return request.getfixturevalue(request.param)


@pytest.fixture
def p_triangle(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[5, 6, 7],
        is_centroids=[1, 1, 1],
        geometries=[[97700, 434000], [97701, 434000], [97702, 434000]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[102, 103, 104],
        from_nodes=[5, 6, 5],
        to_nodes=[7, 7, 6],
        directions=[1, -1, -1],
        geometries=[
            [[97700, 434000], [97702, 434000]],
            [[97701, 434000], [97704, 434000], [97702, 434000]],
            [[97700, 434000], [97701, 434000]],
        ],
        max_speeds=[25, 100, 10],
        capacities=[100, 50, 10],
    )
    project.add_links(links)
    project.add_column("free_flow_time", project.calculate_free_flow_times())
    project.add_column("custom_field", [10, 11, 12])
    project.build_graph(
        cost_field="free_flow_time",
        block_centroid_flows=False,
    )
    return project


@pytest.fixture
def p_triangle_block(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[5, 6, 7, 15, 16, 17],
        is_centroids=[0, 0, 0, 1, 1, 1],
        geometries=[
            [97700, 434000],
            [97701, 434000],
            [97702, 434000],
            [97700.01, 434000.01],
            [97701.01, 434000.01],
            [97702.01, 434000.01],
        ],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[102, 103, 104, 15, 16, 17],
        from_nodes=[5, 6, 5, 5, 6, 7],
        to_nodes=[7, 7, 6, 15, 16, 17],
        directions=[1, -1, -1, 0, 0, 0],
        geometries=[
            [[97700, 434000], [97702, 434000]],
            [[97701, 434000], [97704, 434000], [97702, 434000]],
            [[97700, 434000], [97701, 434001]],
            [[97700, 434000], [97700.01, 434000.01]],
            [[97701, 434000], [97701.01, 434000.01]],
            [[97702, 434000], [97702.01, 434000.01]],
        ],
        max_speeds=[
            25,
            100,
            10,
            float("inf"),
            float("inf"),
            float("inf"),
        ],
        capacities=[
            100,
            50,
            10,
            float("inf"),
            float("inf"),
            float("inf"),
        ],
    )
    project.add_links(links)
    project.add_column("free_flow_time", project.calculate_free_flow_times())
    project.add_column("custom_field", [10, 11, 12, 0, 0, 0])
    project.build_graph(
        cost_field="free_flow_time",
        block_centroid_flows=True,
    )
    return project


def test_shortest_path(p_triangle: ProjectWrapper):
    path = p_triangle.get_shortest_path(5, 6)
    assert np.array_equal(path.nodes, [5, 7, 6])
    assert np.array_equal(path.links, [102, 103])

    path = p_triangle.get_shortest_path(6, 5)
    assert np.array_equal(path.nodes, [6, 5])
    assert np.array_equal(path.links, [104])

    path = p_triangle.get_shortest_path(7, 5)
    assert np.array_equal(path.nodes, [7, 6, 5])
    assert np.array_equal(path.links, [103, 104])

    path = p_triangle.get_shortest_path(7, 6)
    assert np.array_equal(path.nodes, [7, 6])
    assert np.array_equal(path.links, [103])

    path = p_triangle.get_shortest_path(5, 7)
    assert np.array_equal(path.nodes, [5, 7])
    assert np.array_equal(path.links, [102])

    path = p_triangle.get_shortest_path(6, 7)
    assert np.array_equal(path.nodes, [6, 5, 7])
    assert np.array_equal(path.links, [104, 102])


def test_shortest_path_blocking(p_triangle_block: ProjectWrapper):
    path = p_triangle_block.get_shortest_path(15, 16)
    assert np.array_equal(path.nodes, [15, 5, 7, 6, 16])
    assert np.array_equal(path.links, [15, 102, 103, 16])

    path = p_triangle_block.get_shortest_path(16, 15)
    assert np.array_equal(path.nodes, [16, 6, 5, 15])
    assert np.array_equal(path.links, [16, 104, 15])

    path = p_triangle_block.get_shortest_path(17, 15)
    assert np.array_equal(path.nodes, [17, 7, 6, 5, 15])
    assert np.array_equal(path.links, [17, 103, 104, 15])

    path = p_triangle_block.get_shortest_path(17, 16)
    assert np.array_equal(path.nodes, [17, 7, 6, 16])
    assert np.array_equal(path.links, [17, 103, 16])

    path = p_triangle_block.get_shortest_path(15, 17)
    assert np.array_equal(path.nodes, [15, 5, 7, 17])
    assert np.array_equal(path.links, [15, 102, 17])

    path = p_triangle_block.get_shortest_path(16, 17)
    assert np.array_equal(path.nodes, [16, 6, 5, 7, 17])
    assert np.array_equal(path.links, [16, 104, 102, 17])


def test_shortest_paths(p_triangle_block: ProjectWrapper):
    paths = p_triangle_block.get_shortest_paths(15, [16, 17])
    assert np.array_equal(paths[0].nodes, [15, 5, 7, 6, 16])
    assert np.array_equal(paths[0].links, [15, 102, 103, 16])

    assert np.array_equal(paths[1].nodes, [15, 5, 7, 17])
    assert np.array_equal(paths[1].links, [15, 102, 17])


def test_shortest_paths_some_without_path(project: ProjectWrapper):
    nodes = NodeCollection(
        ids=[5, 6, 7],
        is_centroids=[1, 1, 1],
        geometries=[[97700, 434000], [97701, 434000], [97702, 434000]],
    )
    project.add_nodes(nodes)

    links = LinkCollection(
        ids=[102, 103, 104],
        from_nodes=[5, 6, 7],
        to_nodes=[7, 7, 5],
        directions=[1, 1, 1],
        geometries=[
            [[97700, 434000], [97702, 434000]],
            [[97701, 434000], [97704, 434000], [97702, 434000]],
            [[97702, 434000], [97700, 434000]],
        ],
        max_speeds=[25, 100, 10],
        capacities=[100, 50, 10],
    )
    project.add_links(links)
    project.add_column("free_flow_time", project.calculate_free_flow_times())
    project.add_column("custom_field", [10, 11, 12])
    project.build_graph(
        cost_field="free_flow_time",
        block_centroid_flows=False,
    )

    paths = project.get_shortest_paths(5, [6, 7])
    assert paths[0] is None

    assert np.array_equal(paths[1].nodes, [5, 7])
    assert np.array_equal(paths[1].links, [102])
