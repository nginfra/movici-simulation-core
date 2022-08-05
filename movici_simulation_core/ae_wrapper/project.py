import shutil
import tempfile
import typing as t
import uuid
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import numpy as np
from aequilibrae import Graph, PathResults, Project, TrafficAssignment, TrafficClass
from pyproj import Transformer

from movici_simulation_core.csr import get_row

from .collections import AssignmentResultCollection, GraphPath, LinkCollection, NodeCollection
from .id_generator import IdGenerator
from .patches import AequilibraeMatrix
from .point_generator import PointGenerator

EPSILON = 1e-12

# 9 decimals of lat/lon accuracy means a precision < 1mm, which is necessary for nodes that have
# been shifted by ``PointGenerator`` to prevent duplicate nodes
GEOM_ACC = 9


class TransportMode:
    CAR = "c"


@dataclass
class AssignmentParameters:
    volume_delay_function: str = "BPR"  # one of ["BPR", "CONICAL"]
    vdf_alpha: float = 0.64
    vdf_beta: float = 4.0
    cargo_pcu: float = 1.9

    # Recommended: bfw. One of ["all-or-nothing", "msa", "fw", "cfw", "bfw"]
    algorithm: str = "bfw"
    max_iter: int = 1000
    rgap_target: float = 0.001


class ProjectWrapper:
    """
    This class wraps Aequilibrae methods with sensible methods and bugfixes
    """

    transformer = Transformer.from_crs(28992, 4326)

    def __init__(
        self,
        project_path: t.Union[str, Path, None] = None,
        project_name: t.Optional[str] = None,
        delete_on_close: bool = True,
    ) -> None:

        self._delete_on_close = delete_on_close

        if project_path is None:
            project_path = tempfile.gettempdir()

        if project_name is None:
            project_name = str(uuid.uuid4())

        project_dir = Path(project_path, "ae_project")
        project_dir.mkdir(parents=True, exist_ok=True)
        project_dir = Path(project_dir, project_name)

        self.project_dir = project_dir

        try:
            self._project = Project()
            self._project.new(str(self.project_dir))
            self._db = self._project.conn

            self._node_id_to_point: t.Dict[int, t.Tuple[float, float]] = {}

            # Aequilibrae makes assumptions on how ids should look.
            # We don't have these assumptions in model_engine,
            #   so we have to map them to new ids.
            self._node_id_generator = IdGenerator()
            self._link_id_generator = IdGenerator()
            self.point_generator = PointGenerator()
        except Exception as e:
            self.close()
            raise e

    def __enter__(self) -> "ProjectWrapper":
        return self

    def __exit__(self, exc_type: t.Type, exc_val: Exception, exc_tb: TracebackType) -> None:
        self.close()

    def close(self) -> None:
        try:
            if self._project is not None:
                for handler in self._project.logger.handlers:
                    handler.flush()
                    handler.close()
                self._project.close()
                self._project = None
            if self._delete_on_close and self.project_dir.exists():
                shutil.rmtree(self.project_dir)
        except IOError:
            pass

    def add_nodes(self, nodes: NodeCollection) -> None:
        new_node_ids = self._node_id_generator.get_new_ids(nodes.ids)

        point_strs = []
        lats, lons = self.transformer.transform(nodes.geometries[:, 0], nodes.geometries[:, 1])
        lats = np.round(lats, decimals=GEOM_ACC)
        lons = np.round(lons, decimals=GEOM_ACC)
        for node_id, xy, lat, lon in zip(new_node_ids, nodes.geometries, lats, lons):
            point_strs.append(f"POINT({lon:.{GEOM_ACC}f} {lat:.{GEOM_ACC}f})")
            self._node_id_to_point[node_id] = (lat, lon)

        sql = (
            "INSERT INTO nodes "  # nosec
            "(node_id, is_centroid, modes, link_types, geometry)  VALUES "
            f"(?, ?, '{TransportMode.CAR}', 'y', GeomFromText(?, 4326))"
        )

        with closing(self._db.cursor()) as cursor:
            cursor.executemany(
                sql,
                zip(new_node_ids.tolist(), nodes.is_centroids.tolist(), point_strs),
            )

            self._db.commit()

    def get_nodes(self) -> NodeCollection:
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT node_id, is_centroid FROM nodes")
            results = cursor.fetchall()
        if not results:
            return NodeCollection()
        node_id, is_centroids = zip(*results)
        node_id = self._node_id_generator.query_original_ids(node_id)
        return NodeCollection(ids=node_id, is_centroids=is_centroids)

    def add_links(self, links: LinkCollection, raise_on_geometry_mismatch: bool = True) -> None:
        try:
            new_from_nodes = self._node_id_generator.query_new_ids(links.from_nodes)
        except ValueError:
            raise ValueError(f"From nodes {links.from_nodes} does not exist in node ids")

        try:
            new_to_nodes = self._node_id_generator.query_new_ids(links.to_nodes)
        except ValueError:
            raise ValueError(f"To nodes {links.to_nodes} does not exist in node ids")

        linestring_strs = []
        geometries = np.round(
            np.column_stack(
                self.transformer.transform(
                    links.geometries.data[:, 0], links.geometries.data[:, 1]
                )
            ),
            decimals=GEOM_ACC,
        )

        for row_idx, (from_node, to_node) in enumerate(zip(new_from_nodes, new_to_nodes)):
            row = get_row(geometries, links.geometries.row_ptr, row_idx)
            linestring_strs.append(
                self._get_linestring_string(row, from_node, to_node, raise_on_geometry_mismatch)
            )

        new_link_ids = self._link_id_generator.get_new_ids(links.ids)
        directions = links.directions.tolist()
        max_speeds = links.max_speeds.tolist()
        capacities = links.capacities.tolist()

        sql = (
            "INSERT INTO links "  # nosec
            "(link_id, a_node, b_node, direction, speed_ab, speed_ba, "
            "capacity_ab, capacity_ba, modes, link_type, geometry)  VALUES "
            f"(?, ?, ?, ?, ?, ?, ?, ?, '{TransportMode.CAR}', 'default', GeomFromText(?, 4326))"
        )

        with closing(self._db.cursor()) as cursor:
            cursor.executemany(
                sql,
                zip(
                    new_link_ids.tolist(),
                    new_from_nodes.tolist(),
                    new_to_nodes.tolist(),
                    directions,
                    max_speeds,
                    max_speeds,
                    capacities,
                    capacities,
                    linestring_strs,
                ),
            )

            self._db.commit()

    def get_links(self) -> LinkCollection:
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT link_id, a_node, b_node, direction FROM links")
            results = cursor.fetchall()
        if not results:
            return LinkCollection()
        link_id, a_node, b_node, direction = zip(*results)
        direction = np.array(direction)
        link_id = self._link_id_generator.query_original_ids(link_id)
        a_node = self._node_id_generator.query_original_ids(a_node)
        b_node = self._node_id_generator.query_original_ids(b_node)
        return LinkCollection(
            ids=link_id, from_nodes=a_node, to_nodes=b_node, directions=direction
        )

    def _get_linestring_string(
        self,
        linestring: np.ndarray,
        from_node: int,
        to_node: int,
        raise_on_geometry_mismatch: bool = True,
    ) -> str:
        def assert_point_matches(point, expected):
            if raise_on_geometry_mismatch and not np.allclose(
                point, expected, atol=1e-6, rtol=1e-6
            ):
                raise ValueError(
                    f"Mismatch in data:"
                    f" Linestring beginning has point {point} but"
                    f" from_node has point {expected}"
                )

        if len(linestring) < 2:
            raise ValueError("Linestring must be at least of length 2")

        from_node_point = self._node_id_to_point[from_node]
        to_node_point = self._node_id_to_point[to_node]
        assert_point_matches(linestring[0], from_node_point)
        assert_point_matches(linestring[-1], to_node_point)
        linestring[0] = from_node_point
        linestring[-1] = to_node_point

        linestring2d = [f"{lon:.{GEOM_ACC}f} {lat:.{GEOM_ACC}f}" for lat, lon in linestring]
        linestring_str = ",".join(linestring2d)
        return f"LINESTRING({linestring_str})"

    def calculate_free_flow_times(self) -> np.ndarray:
        """
        Aequilibrae calculates distances automatically but does not compute free flow time, so we
        have to calculate them manually
        """
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT link_id, distance, speed_ab FROM links")
            results = cursor.fetchall()
        free_flow_times = []
        ids = []
        for link_id, distance, speed in results:
            time = max(distance / speed, EPSILON)
            free_flow_times.append(time)
            ids.append(link_id)

        return np.array(free_flow_times)

    def add_column(self, column_name: str, values: t.Optional[t.Sequence] = None) -> None:
        with closing(self._db.cursor()) as cursor:
            cursor.execute(f"ALTER TABLE links ADD COLUMN {column_name} REAL(32) DEFAULT 0")

        if values is not None:
            self.update_column(column_name, values)

    def update_column(self, column_name: str, values: t.Sequence) -> None:
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT link_id FROM links")
            ids = (row[0] for row in cursor.fetchall())

            if isinstance(values, np.ndarray):
                values = values.tolist()

            cursor.executemany(
                f"UPDATE links SET {column_name}=? WHERE link_id=?", zip(values, ids)  # nosec
            )

            self._db.commit()

    @property
    def _graph(self) -> Graph:
        return self._project.network.graphs[TransportMode.CAR]

    def build_graph(
        self,
        cost_field: str,
        block_centroid_flows: bool = True,
    ) -> Graph:
        self._project.network.build_graphs(modes=[TransportMode.CAR])
        graph = self._graph
        graph.set_graph(cost_field)
        graph.set_blocked_centroid_flows(block_centroid_flows)
        return graph

    def convert_od_matrix(self, od_matrix: np.ndarray, matrix_name: str) -> AequilibraeMatrix:
        nodes = self.get_nodes()
        node_ids = self._node_id_generator.query_new_ids(nodes.ids)
        node_ids = node_ids[np.array(nodes.is_centroids, dtype=bool)]

        matrix = AequilibraeMatrix()
        # We have to give a filename to the matrix
        #  because aequilibrae creates memmap based on a file
        # Therefore it is highly recommended that this file is in ram

        matrix.create_empty(
            file_name=Path(self.project_dir, f"{matrix_name}.aem"),
            zones=len(node_ids),
            matrix_names=[matrix_name],
            index_names=["index"],
        )
        matrix.index[:] = node_ids
        matrix.matrix[matrix_name][:] = od_matrix[:]

        matrix.computational_view([matrix_name])

        return matrix

    def assign_traffic(
        self,
        od_matrix_passenger: np.ndarray,
        od_matrix_cargo: np.ndarray,
        parameters: t.Optional[AssignmentParameters] = None,
    ) -> AssignmentResultCollection:
        if parameters is None:
            parameters = AssignmentParameters()

        graph = self._graph
        assignment = TrafficAssignment(self._project)

        od_matrix_passenger = self.convert_od_matrix(od_matrix_passenger, "passenger_demand")
        od_matrix_cargo = self.convert_od_matrix(od_matrix_cargo, "cargo_demand")
        try:
            tc_passenger = TrafficClass("passenger", graph, od_matrix_passenger)

            tc_cargo = TrafficClass("cargo", graph, od_matrix_cargo)
            tc_cargo.set_pce(parameters.cargo_pcu)

            assignment.set_classes([tc_passenger, tc_cargo])
            assignment.set_vdf(parameters.volume_delay_function)
            assignment.set_vdf_parameters(
                {"alpha": parameters.vdf_alpha, "beta": parameters.vdf_beta}
            )

            assignment.set_capacity_field("capacity")
            assignment.set_time_field("free_flow_time")

            assignment.set_algorithm(parameters.algorithm)
            assignment.max_iter = parameters.max_iter
            assignment.rgap_target = parameters.rgap_target

            assignment.execute()

            results = assignment.results()
            ids = self._link_id_generator.query_original_ids(results.index)
            passenger_flow, cargo_flow = results.passenger_demand_tot, results.cargo_demand_tot
            congested_time = results.Congested_Time_Max

            return AssignmentResultCollection(
                ids=ids.copy(),
                passenger_flow=passenger_flow.copy(),
                cargo_flow=cargo_flow.copy(),
                congested_time=congested_time.copy(),
                delay_factor=results.Delay_factor_Max.copy(),
                volume_to_capacity=results.VOC_max.copy(),
                passenger_car_unit=results.PCE_tot.copy(),
            )
        finally:
            od_matrix_cargo.close()
            od_matrix_passenger.close()

    def get_shortest_path(
        self, from_node: int, to_node: int, path_results: t.Optional[PathResults] = None
    ) -> t.Optional[GraphPath]:
        ae_from_node, ae_to_node = self._node_id_generator.query_new_ids(
            [from_node, to_node]
        ).tolist()

        graph = self._graph

        if not path_results:
            path_results = PathResults()
            path_results.prepare(graph)
            path_results.compute_path(ae_from_node, ae_to_node)
        else:
            path_results.update_trace(ae_to_node)

        ae_path_nodes, ae_path_links = path_results.path_nodes, path_results.path

        if ae_path_nodes is None:
            return None

        path_nodes, path_links = (
            self._node_id_generator.query_original_ids(ae_path_nodes),
            self._link_id_generator.query_original_ids(ae_path_links),
        )

        return GraphPath(path_nodes, path_links, path_results)

    def get_shortest_paths(
        self, from_node: int, to_nodes: t.List[int]
    ) -> t.List[t.Optional[GraphPath]]:
        results: t.List[t.Optional[GraphPath]] = []
        path_results: t.Optional[PathResults] = None
        for i, to_node in enumerate(to_nodes):
            if not path_results:
                result = self.get_shortest_path(from_node, to_node)
                if result:
                    path_results = result.path_results
                results.append(result)
            else:
                results.append(
                    self.get_shortest_path(from_node, to_node, path_results=path_results)
                )
        return results
