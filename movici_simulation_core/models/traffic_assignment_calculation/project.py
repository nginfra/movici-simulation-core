import shutil
from collections import Sequence
from contextlib import closing
from dataclasses import dataclass
from pathlib import Path
from typing import Tuple, Dict, Optional

import numpy as np
from aequilibrae import Project, Graph, AequilibraeMatrix, TrafficAssignment, TrafficClass
from pyproj import Transformer

from .collections import NodeCollection, LinkCollection, AssignmentResultCollection
from .id_generator import IdGenerator

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

    # TODO(baris) maybe use contextmanager
    def __init__(self, project_dir: str, remove_existing: bool = False) -> None:
        project_dir = Path(project_dir, "project_dir")
        if remove_existing and project_dir.exists():
            shutil.rmtree(project_dir)
        self.project_dir = project_dir
        self._project = Project()
        self._project.new(str(self.project_dir))
        self._db = self._project.conn

        self._node_id_to_point: Dict[int, Tuple[float, float]] = {}

        # Aequilibrae makes assumptions on how ids should look.
        # We don't have these assumptions in model_engine,
        #   so we have to map them to new ids.
        self._node_id_generator = IdGenerator()
        self._link_id_generator = IdGenerator()

    def __del__(self) -> None:
        self.close()

    def close(self) -> None:
        try:
            self._project.close()
        except AttributeError as e:
            print(e)

    def add_nodes(self, nodes: NodeCollection) -> None:
        transformer = Transformer.from_crs(28992, 4326)

        new_node_ids = self._node_id_generator.get_new_ids(nodes.ids)

        point_strs = []
        for node_id, (node_x, node_y) in zip(new_node_ids, nodes.geometries):
            lat, lon = transformer.transform(node_x, node_y)
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

    def get_nodes(self) -> NodeCollection:
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT node_id, is_centroid FROM nodes")
            results = cursor.fetchall()
        if not results:
            return NodeCollection()
        node_id, is_centroids = zip(*results)
        node_id = self._node_id_generator.query_original_ids(node_id)
        return NodeCollection(ids=node_id, is_centroids=is_centroids)

    def add_links(self, links: LinkCollection) -> None:
        transformer = Transformer.from_crs(28992, 4326)

        new_link_ids = self._link_id_generator.get_new_ids(links.ids)
        new_from_nodes = self._node_id_generator.query_new_ids(links.from_nodes)
        new_to_nodes = self._node_id_generator.query_new_ids(links.to_nodes)

        linestring_strs = []
        for from_node, to_node, linestring in zip(new_from_nodes, new_to_nodes, links.geometries):
            linestring_strs.append(
                self._get_linestring_string(linestring, from_node, to_node, transformer)
            )

        directions = [1 if d else -1 for d in links.directions]
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

    def get_links(self) -> LinkCollection:
        with closing(self._db.cursor()) as cursor:
            cursor.execute("SELECT link_id, a_node, b_node, direction FROM links")
            results = cursor.fetchall()
        if not results:
            return LinkCollection()
        link_id, a_node, b_node, direction = zip(*results)
        direction = np.array([True if d == 1 else False for d in direction], dtype=bool)
        link_id = self._link_id_generator.query_original_ids(link_id)
        a_node = self._node_id_generator.query_original_ids(a_node)
        b_node = self._node_id_generator.query_original_ids(b_node)
        return LinkCollection(
            ids=link_id, from_nodes=a_node, to_nodes=b_node, directions=direction
        )

    def _get_linestring_string(
        self, linestring: Sequence, from_node, to_node, transformer: Transformer
    ) -> str:
        linestring2d = []

        for i, point in enumerate(linestring):
            # We have to change beginning and end points of links
            #  to the corresponding node points, because aequilibrae
            #  indexes points by geometries.
            # So if there are rounding errors it will generate new nodes
            #  regardless of the node id specified
            if i == 0:
                point = self._node_id_to_point[from_node]
            if i == len(linestring) - 1:
                point = self._node_id_to_point[to_node]
            lat, lon = transformer.transform(point[0], point[1])
            linestring2d.append(f"{lon} {lat}")
        linestring_str = ",".join(linestring2d)
        return f"LINESTRING({linestring_str})"

    def add_free_flow_times(self) -> np.ndarray:
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

        with closing(self._db.cursor()) as cursor:
            cursor.execute(
                "ALTER TABLE links ADD COLUMN free_flow_time REAL(32)"
            )  # TODO(baris) add column only if not exists, need workaround for sqlite

            cursor.executemany(
                "UPDATE links SET free_flow_time=? WHERE link_id=?", zip(free_flow_times, ids)
            )
        return np.array(free_flow_times)

    def build_graph(self) -> Graph:
        self.add_free_flow_times()
        self._project.network.build_graphs(modes=[TransportMode.CAR])
        graph = self._project.network.graphs[TransportMode.CAR]
        graph.set_graph("free_flow_time")
        graph.set_blocked_centroid_flows(
            False
        )  # TODO(baris) put this to True, needs changes in tests
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
        parameters: Optional[AssignmentParameters] = None,
    ) -> AssignmentResultCollection:
        if parameters is None:
            parameters = AssignmentParameters()

        graph = self._project.network.graphs[TransportMode.CAR]

        assignment = TrafficAssignment()

        od_matrix_passenger = self.convert_od_matrix(od_matrix_passenger, "passenger_demand")
        tc_passenger = TrafficClass(graph, od_matrix_passenger)

        od_matrix_cargo = self.convert_od_matrix(od_matrix_cargo, "cargo_demand")
        tc_cargo = TrafficClass(graph, od_matrix_cargo)
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
