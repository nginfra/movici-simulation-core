import shutil
import typing as t
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from types import TracebackType

import numpy as np
from aequilibrae import (
    Project,
    Graph,
    AequilibraeMatrix,
    TrafficAssignment,
    TrafficClass,
    PathResults,
    NetworkSkimming,
)
from pyproj import Transformer

from movici_simulation_core.ae_wrapper.collections import (
    NodeCollection,
    LinkCollection,
    AssignmentResultCollection,
    GraphPath,
)
from movici_simulation_core.ae_wrapper.id_generator import IdGenerator
from movici_simulation_core.ae_wrapper.point_generator import PointGenerator

EPSILON = 1e-12


class TransportMode:
    CAR = "c"


@dataclass
class AssignmentParameters:
    volume_delay_function: str = "BPR"  # one of ["BPR", "CONICAL"]
    vdf_alpha: float = 0.15
    vdf_beta: float = 4.0
    cargo_pcu: float = 1.9
    algorithm: str = (
        "bfw"  # Recommended: bfw. One of ["all-or-nothing", "msa", "fw", "cfw", "bfw"]
    )
    max_iter: int = 1000
    rgap_target: float = 0.001


class ProjectWrapper:
    """
    This class wraps Aequilibrae methods with sensible methods and bugfixes
    """

    transformer = Transformer.from_crs(28992, 4326)

    def __init__(self, project_dir: str, remove_existing: bool = False) -> None:
        project_dir = Path(project_dir, "ae_project_dir")
        if remove_existing and project_dir.exists():
            shutil.rmtree(project_dir)
        self.project_dir = project_dir
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

    def __enter__(self) -> "ProjectWrapper":
        return self

    def __exit__(self, exc_type: t.Type, exc_val: Exception, exc_tb: TracebackType) -> None:
        self._project.close()

    def close(self) -> None:
        try:
            self._project.close()
        except AttributeError as e:
            print(e)

    def add_nodes(self, nodes: NodeCollection) -> None:
        new_node_ids = self._node_id_generator.get_new_ids(nodes.ids)

        point_strs = []
        for node_id, (node_x, node_y) in zip(new_node_ids, nodes.geometries):
            lat, lon = self.transformer.transform(node_x, node_y)
            point_strs.append(f"POINT({lon} {lat})")
            self._node_id_to_point[node_id] = (node_x, node_y)

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
        for from_node, to_node, linestring in zip(new_from_nodes, new_to_nodes, links.geometries):
            linestring_strs.append(
                self._get_linestring_string(
                    linestring, from_node, to_node, self.transformer, raise_on_geometry_mismatch
                )
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
        linestring: t.Sequence,
        from_node: int,
        to_node: int,
        transformer: Transformer,
        raise_on_geometry_mismatch: bool = True,
    ) -> str:
        linestring2d = []

        for i, point in enumerate(linestring):
            # We have to change beginning and end points of links
            #  to the corresponding node points, because aequilibrae
            #  indexes points by geometries.
            # So if there are rounding errors it will generate new nodes
            #  regardless of the node id specified
            if i == 0:
                from_node_point = self._node_id_to_point[from_node]
                if raise_on_geometry_mismatch and not np.allclose(
                    point, from_node_point, atol=0.1
                ):
                    raise ValueError(
                        f"Mismatch in data:"
                        f" Linestring beginning has point {point} but"
                        f" from_node has point {from_node_point}"
                    )
                point = from_node_point
            if i == len(linestring) - 1:
                to_node_point = self._node_id_to_point[to_node]
                if raise_on_geometry_mismatch and not np.allclose(point, to_node_point, atol=0.1):
                    raise ValueError(
                        f"Mismatch in data:"
                        f" Linestring end has point {point} but"
                        f" to_node has point {to_node_point}"
                    )
                point = to_node_point
            lat, lon = transformer.transform(point[0], point[1])
            linestring2d.append(f"{lon} {lat}")
        linestring_str = ",".join(linestring2d)
        return f"LINESTRING({linestring_str})"

    def calculate_free_flow_times(self) -> np.ndarray:
        """
        Aequilibrae calculates distances automatically,
         but does not compute free flow time.
        So we have to calculate them manually
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

    def add_column(self, column_name: str, values: t.Sequence) -> None:
        with closing(self._db.cursor()) as cursor:
            cursor.execute(f"ALTER TABLE links ADD COLUMN {column_name} REAL(32)")

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
        skim_fields: t.Optional[t.List[str]] = None,
        block_centroid_flows: bool = True,
    ) -> Graph:
        self._project.network.build_graphs(modes=[TransportMode.CAR])
        graph = self._graph
        graph.set_graph(cost_field)
        if skim_fields:
            graph.set_skimming(skim_fields)
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

        assignment = TrafficAssignment()

        od_matrix_passenger = self.convert_od_matrix(od_matrix_passenger, "passenger_demand")
        tc_passenger = TrafficClass("passenger", graph, od_matrix_passenger)

        od_matrix_cargo = self.convert_od_matrix(od_matrix_cargo, "cargo_demand")
        tc_cargo = TrafficClass("cargo", graph, od_matrix_cargo)
        tc_cargo.set_pce(parameters.cargo_pcu)

        assignment.set_classes([tc_passenger, tc_cargo])
        assignment.set_vdf(parameters.volume_delay_function)
        assignment.set_vdf_parameters({"alpha": parameters.vdf_alpha, "beta": parameters.vdf_beta})

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
            ids=ids,
            passenger_flow=passenger_flow,
            cargo_flow=cargo_flow,
            congested_time=congested_time,
            delay_factor=results.Delay_factor_Max,
            volume_to_capacity=results.VOC_max,
            passenger_car_unit=results.PCE_tot,
        )

    def get_shortest_path(self, from_node: int, to_node: int) -> t.Optional[GraphPath]:
        ae_from_node, ae_to_node = self._node_id_generator.query_new_ids(
            [from_node, to_node]
        ).tolist()

        graph = self._graph
        skim_fields = graph.skim_fields
        graph.set_skimming([])

        path_results = PathResults()
        path_results.prepare(graph)

        path_results.compute_path(ae_from_node, ae_from_node)
        path_results.update_trace(ae_to_node)

        ae_path_nodes, ae_path_links = path_results.path_nodes, path_results.path

        graph.set_skimming(skim_fields)

        if ae_path_nodes is None:
            return None

        path_nodes, path_links = (
            self._node_id_generator.query_original_ids(ae_path_nodes),
            self._link_id_generator.query_original_ids(ae_path_links),
        )

        return GraphPath(path_nodes, path_links)

    def calculate_skims(self) -> AequilibraeMatrix:
        graph = self._graph
        skimming = NetworkSkimming(graph)
        skimming.execute()

        return skimming.results.skims
