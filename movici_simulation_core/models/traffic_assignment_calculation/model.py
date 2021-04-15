import typing as t

import numpy as np

from model_engine import TimeStamp, Config, DataFetcher
from movici_simulation_core.ae_wrapper.collections import (
    NodeCollection,
    LinkCollection,
    AssignmentResultCollection,
)
from movici_simulation_core.ae_wrapper.point_generator import PointGenerator
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.exceptions import NotReady
from .dataset import (
    TransportSegmentEntity,
    TransportNodeEntity,
    DemandNodeEntity,
    DemandLinkEntity,
)


class Model(TrackedBaseModel):
    """
    Calculates traffic properties on roads
    """

    dataset_to_segments = {
        "roads": "road_segment_entities",
        "waterways": "waterway_segment_entities",
        "tracks": "track_segment_entities",
    }

    def __init__(self):
        self.project: t.Optional[ProjectWrapper] = None
        self.transport_segments: t.Optional[TransportSegmentEntity] = None
        self.transport_nodes: t.Optional[TransportNodeEntity] = None
        self.demand_nodes: t.Optional[DemandNodeEntity] = None
        self.demand_links: t.Optional[DemandLinkEntity] = None

    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
    ):

        transport_type = self._get_transport_type(config)

        transport_dataset_name = config[transport_type][0]

        self.transport_segments = state.register_entity_group(
            transport_dataset_name,
            TransportSegmentEntity(name=self.dataset_to_segments[transport_type]),
        )

        self.transport_nodes = state.register_entity_group(
            transport_dataset_name, TransportNodeEntity(name="transport_node_entities")
        )

        self.demand_nodes = state.register_entity_group(
            transport_dataset_name, DemandNodeEntity(name="virtual_node_entities")
        )

        self.demand_links = state.register_entity_group(
            transport_dataset_name, DemandLinkEntity(name="virtual_link_entities")
        )

        self.project = ProjectWrapper(scenario_config.TEMP_DIR, remove_existing=True)

    def initialize(self, state: TrackedState):
        self.ensure_ready()

        demand_nodes = self._get_demand_nodes(self.demand_nodes, self.project.point_generator)
        self.project.add_nodes(demand_nodes)

        nodes = self._get_nodes(self.transport_nodes, self.project.point_generator)
        self.project.add_nodes(nodes)

        links = self._get_links(self.transport_segments)
        self.project.add_links(links)

        demand_links = self._get_demand_links(self.demand_links)
        self.project.add_links(demand_links, raise_on_geometry_mismatch=False)

        self.project.add_column("free_flow_time", self.project.calculate_free_flow_times())
        self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)

    def ensure_ready(self) -> bool:
        try:
            return self.transport_segments.linestring.is_initialized()
        except RuntimeError as e:
            raise NotReady(e)

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        passenger_demand = self._get_matrix(self.demand_nodes.passenger_demand.csr)
        cargo_demand = self._get_matrix(self.demand_nodes.cargo_demand.csr)

        results = self.project.assign_traffic(passenger_demand, cargo_demand)

        self._publish_results(results)

        return None

    def shutdown(self):
        if self.project:
            self.project.close()
            self.project = None

    @classmethod
    def _get_transport_type(cls, config: t.Dict[str, t.Optional[t.List[str]]]) -> str:
        return_dataset_type = ""
        dataset_count = 0

        for dataset_type in ["roads", "waterways", "tracks"]:
            dataset_name_list = config.get(dataset_type, [])
            if dataset_name_list:
                if len(dataset_name_list) > 1:
                    raise RuntimeError("You can only have one dataset in config")
                return_dataset_type = dataset_type
                dataset_count += 1

        if dataset_count != 1:
            raise RuntimeError(
                "There should be exactly one of [roads, waterways, tracks] in config"
            )

        return return_dataset_type

    @staticmethod
    def _get_nodes(
        vertices: TransportNodeEntity, point_generator: PointGenerator
    ) -> NodeCollection:

        geometries = []
        for node_x, node_y in zip(vertices.x, vertices.y):
            geometry = point_generator.generate_and_add([node_x, node_y])
            geometries.append(geometry)

        return NodeCollection(
            ids=vertices.index.ids,
            is_centroids=np.zeros(len(vertices), dtype=bool),
            geometries=geometries,
        )

    @staticmethod
    def _get_links(segments: TransportSegmentEntity) -> LinkCollection:
        geometries = []
        linestring_csr = segments.linestring.csr
        for i in range(len(linestring_csr.row_ptr) - 1):
            geometries.append(linestring_csr.get_row(i)[:, :2])

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
            max_speeds=segments.max_speed.array,
            capacities=segments.capacity.array * lanes,
        )

    @staticmethod
    def _get_demand_nodes(
        demand_nodes: DemandNodeEntity, point_generator: PointGenerator
    ) -> NodeCollection:
        geometries = []
        for node_x, node_y in zip(demand_nodes.x, demand_nodes.y):
            geometry = point_generator.generate_and_add([node_x, node_y])
            geometries.append(geometry)

        return NodeCollection(
            ids=demand_nodes.index.ids,
            is_centroids=np.ones(len(geometries), dtype=bool),
            geometries=geometries,
        )

    @staticmethod
    def _get_demand_links(segments: DemandLinkEntity) -> LinkCollection:
        geometries = []
        linestring_csr = segments.linestring.csr
        for i in range(len(linestring_csr.row_ptr) - 1):
            geometries.append(linestring_csr.get_row(i)[:, :2])

        return LinkCollection(
            ids=segments.index.ids,
            from_nodes=segments.from_node_id.array,
            to_nodes=segments.to_node_id.array,
            directions=np.zeros(len(geometries)),
            geometries=geometries,
            max_speeds=np.full(len(geometries), float("inf")),
            capacities=np.full(len(geometries), float("inf")),
        )

    @staticmethod
    def _get_matrix(csr_array: TrackedCSRArray):
        matrix = []
        for i in range(len(csr_array.row_ptr) - 1):
            matrix.append(csr_array.get_row(i))
        return np.stack(matrix)

    def _publish_results(self, results: AssignmentResultCollection):
        real_link_len = len(self.transport_segments.index.ids)
        self.transport_segments.passenger_flow[:] = results.passenger_flow[:real_link_len]
        self.transport_segments.cargo_flow[:] = results.cargo_flow[:real_link_len]
        self.transport_segments.average_time[:] = results.congested_time[:real_link_len]
        self.transport_segments.delay_factor[:] = results.delay_factor[:real_link_len]
        self.transport_segments.passenger_car_unit[:] = results.passenger_car_unit[:real_link_len]

        # Calculate volume_to_capacity ourselves because aequilibrae is broken
        # self.road_segments.volume_to_capacity[:] = results.volume_to_capacity[:real_link_len]
        self.transport_segments.volume_to_capacity[:] = (
            results.passenger_car_unit[:real_link_len]
            / self.transport_segments.capacity[:]
            / np.sum(self.transport_segments.layout, axis=1)
        )
