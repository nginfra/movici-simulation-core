import typing as t

import numpy as np

from model_engine import TimeStamp, Config, DataFetcher
from movici_simulation_core.ae_wrapper.collections import (
    NodeCollection,
    LinkCollection,
    AssignmentResultCollection,
)
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.state import TrackedState
from .dataset import (
    SegmentEntity,
    VertexEntity,
    VirtualNodeEntity,
)
from ...ae_wrapper.point_generator import PointGenerator
from ...exceptions import NotReady


class Model(TrackedBaseModel):
    """
    Calculates traffic properties on roads
    """

    def __init__(self):
        self.project: t.Optional[ProjectWrapper] = None
        self.road_segments: t.Optional[SegmentEntity] = None
        self.road_vertices: t.Optional[VertexEntity] = None
        self.virtual_nodes: t.Optional[VirtualNodeEntity] = None

    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
    ):
        dataset_name, entity_group_name = config["transport_network_segments"][0]
        self.road_segments = state.register_entity_group(
            dataset_name, SegmentEntity(name=entity_group_name)
        )

        dataset_name, entity_group_name = config["transport_network_vertices"][0]
        self.road_vertices = state.register_entity_group(
            dataset_name, VertexEntity(name=entity_group_name)
        )

        dataset_name, entity_group_name = config["demand_nodes"][0]
        self.virtual_nodes = state.register_entity_group(
            dataset_name, VirtualNodeEntity(name=entity_group_name)
        )

        self.project = ProjectWrapper(scenario_config.TEMP_DIR, remove_existing=True)

    def initialize(self, state: TrackedState):
        self.ensure_ready()
        nodes = self._get_nodes(self.road_vertices)
        self.project.point_generator.add_points(
            np.stack([self.road_vertices.x.array, self.road_vertices.y.array]).T
        )
        self.project.add_nodes(nodes)

        links = self._get_links(self.road_segments)
        self.project.add_links(links)

        virtual_nodes, virtual_links = self._get_virtual_nodes_links(
            self.virtual_nodes,
            self.road_vertices,
            self.road_segments,
            self.project.point_generator,
        )
        self.project.add_nodes(virtual_nodes)
        self.project.add_links(virtual_links)

        self.project.add_column("free_flow_time", self.project.calculate_free_flow_times())
        self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)

    def ensure_ready(self) -> bool:
        try:
            return self.road_segments.linestring.is_initialized()
        except RuntimeError as e:
            raise NotReady(e)

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:

        passenger_demand = self._get_matrix(self.virtual_nodes.passenger_demand.csr)
        cargo_demand = self._get_matrix(self.virtual_nodes.cargo_demand.csr)

        results = self.project.assign_traffic(passenger_demand, cargo_demand)

        self._publish_results(results)

        return None

    def shutdown(self):
        if self.project:
            self.project.close()
            self.project = None

    @staticmethod
    def _get_nodes(vertices: VertexEntity) -> NodeCollection:
        return NodeCollection(
            ids=vertices.index.ids,
            is_centroids=np.zeros(len(vertices), dtype=bool),
            geometries=np.stack([vertices.x.array, vertices.y.array]).T,
        )

    @staticmethod
    def _get_links(segments: SegmentEntity) -> LinkCollection:
        geometries = []
        for i in range(len(segments.linestring.csr.row_ptr) - 1):
            geometries.append(segments.linestring.csr.get_row(i)[:, :2])

        directions = []
        for layout in segments.layout:
            forward = layout[0] > 0
            backward = layout[1] > 0
            other = np.any(layout[2:] > 0)

            direction = 0
            if not other:
                if forward and not backward:
                    direction = 1
                if backward and not forward:
                    direction = -1

            directions.append(direction)

        lanes = np.sum(segments.layout, axis=1)

        return LinkCollection(
            ids=segments.index.ids,
            from_nodes=segments.from_node_id.array,
            to_nodes=segments.to_node_id.array,
            directions=directions,
            geometries=geometries,
            max_speeds=segments.max_speed.array / 3.6,  # convert km/h to m/s
            capacities=segments.capacity.array * lanes,
        )

    @staticmethod
    def _get_virtual_nodes_links(
        virtual_nodes: VirtualNodeEntity,
        vertices: VertexEntity,
        segments: SegmentEntity,
        point_generator: PointGenerator,
    ) -> t.Tuple[NodeCollection, LinkCollection]:
        # TODO(baris) refactor this function, maybe numpyfy
        current_link_id = np.max(segments.index.ids) + 1
        link_ids = []
        link_from_nodes = []
        link_to_nodes = []
        link_directions = []

        geometries = []
        link_geometries = []
        for node_index, node_id in enumerate(virtual_nodes.index.ids):
            connected_node_ids = virtual_nodes.to_nodes.csr.get_row(node_index)
            connected_node_indices = vertices.index[connected_node_ids]
            xs = vertices.x[connected_node_indices]
            ys = vertices.y[connected_node_indices]

            connected_node_geometries = np.stack([xs, ys]).T

            geometry = np.mean(connected_node_geometries, axis=0)
            geometry = point_generator.generate_and_add(geometry)
            geometries.append(geometry)

            link_ids_to_add = list(
                range(current_link_id, current_link_id + len(connected_node_geometries))
            )
            current_link_id += len(connected_node_geometries)

            link_ids += link_ids_to_add
            link_from_nodes += [node_id] * len(link_ids_to_add)
            link_to_nodes += connected_node_ids.tolist()
            link_directions += [0] * len(link_ids_to_add)

            for connected_node_geometry in connected_node_geometries:
                link_geometries += [[geometry, connected_node_geometry]]

        return (
            NodeCollection(
                ids=virtual_nodes.index.ids,
                is_centroids=np.ones(len(vertices), dtype=bool),
                geometries=geometries,
            ),
            LinkCollection(
                ids=link_ids,
                from_nodes=link_from_nodes,
                to_nodes=link_to_nodes,
                directions=link_directions,
                geometries=link_geometries,
                max_speeds=np.full(len(link_ids), float("inf")),
                capacities=np.full(len(link_ids), float("inf")),
            ),
        )

    @staticmethod
    def _get_matrix(csr_array: TrackedCSRArray):
        matrix = []
        for i in range(len(csr_array.row_ptr) - 1):
            matrix.append(csr_array.get_row(i))
        return np.stack(matrix)

    def _publish_results(self, results: AssignmentResultCollection):
        real_link_len = len(self.road_segments.index.ids)
        self.road_segments.passenger_flow[:] = results.passenger_flow[:real_link_len]
        self.road_segments.cargo_flow[:] = results.cargo_flow[:real_link_len]
        self.road_segments.average_time[:] = results.congested_time[:real_link_len]
        self.road_segments.delay_factor[:] = results.delay_factor[:real_link_len]
        self.road_segments.passenger_car_unit[:] = results.passenger_car_unit[:real_link_len]

        # Calculate ourselves because aequilibrae is broken
        # self.road_segments.volume_to_capacity[:] = results.volume_to_capacity[:real_link_len]
        self.road_segments.volume_to_capacity[:] = (
            results.passenger_car_unit[:real_link_len]
            / self.road_segments.capacity[:]
            / np.sum(self.road_segments.layout, axis=1)
        )
