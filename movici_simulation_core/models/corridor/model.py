import typing as t
from logging import Logger

import numpy as np

from model_engine import TimeStamp, Config, DataFetcher
from movici_simulation_core.ae_wrapper.collections import GraphPath
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.index import Index
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common import model_util, ae_util
from movici_simulation_core.models.common.entities import PointEntity, VirtualLinkEntity
from .entities import (
    CorridorEntity,
    CorridorTransportSegmentEntity,
    DemandNodeEntity,
)


class Model(TrackedBaseModel):
    """
    Implementation of the corridor model
    """

    epsilon = 1e-12

    def __init__(self) -> None:
        super().__init__()
        self._corridor_entity: t.Optional[CorridorEntity] = None
        self._transport_segments: t.Optional[CorridorTransportSegmentEntity] = None
        self._transport_nodes: t.Optional[PointEntity] = None
        self._demand_nodes: t.Optional[DemandNodeEntity] = None
        self._demand_links: t.Optional[VirtualLinkEntity] = None
        self._free_flow_times: t.Optional[np.ndarray] = None
        self._transport_directions: t.Optional[np.ndarray] = None
        self._project: t.Optional[ProjectWrapper] = None
        self._logger: t.Optional[Logger] = None
        self.cargo_pcu = 2.0
        self.publish_corridor_geometry = False

    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
    ) -> None:
        self._logger = state.logger
        self.cargo_pcu = config.get("cargo_pcu", self.cargo_pcu)
        self.publish_corridor_geometry = config.get(
            "publish_corridor_geometry", self.publish_corridor_geometry
        )

        self._project = ProjectWrapper(scenario_config.TEMP_DIR)

        self._corridor_entity = state.register_entity_group(
            dataset_name=config["corridors"][0], entity=CorridorEntity
        )
        self._register_transport_entities(state, config)

    def _register_transport_entities(self, state: TrackedState, config: dict) -> None:
        transport_type = model_util.get_transport_type(config)
        transport_dataset_name = config[transport_type][0]

        self._transport_segments = state.register_entity_group(
            transport_dataset_name,
            CorridorTransportSegmentEntity(name=model_util.dataset_to_segments[transport_type]),
        )

        self._transport_nodes = state.register_entity_group(
            transport_dataset_name, PointEntity(name="transport_node_entities")
        )

        self._demand_nodes = state.register_entity_group(
            transport_dataset_name,
            DemandNodeEntity(name=model_util.dataset_to_virtual_nodes[transport_type]),
        )

        self._demand_links = state.register_entity_group(
            transport_dataset_name, VirtualLinkEntity(name="virtual_link_entities")
        )

    def initialize(self, state: TrackedState) -> None:
        self._transport_segments.ensure_ready()

        ae_util.fill_project(
            self._project,
            demand_nodes=self._demand_nodes,
            demand_links=self._demand_links,
            transport_nodes=self._transport_nodes,
            transport_segments=self._transport_segments,
        )

        self._project.add_column("congested_time")
        self._transport_directions = ae_util.get_transport_directions(self._transport_segments)
        self._free_flow_times = self._project.calculate_free_flow_times()[
            : len(self._transport_segments.index.ids)
        ]

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        if self._transport_segments.travel_time.has_changes():
            self._project.update_column(
                "congested_time", self._transport_segments.travel_time.array
            )

            self._project.build_graph(
                cost_field="congested_time",
                block_centroid_flows=True,
            )

        self._calculate_updates()
        return None

    def _calculate_updates(self) -> None:
        self._reset_values()

        roads_index = self._transport_segments.index
        demand_nodes_index = self._demand_nodes.index
        num_connections = np.zeros_like(self._corridor_entity.index.ids)

        for corridor_index in range(len(self._corridor_entity.index.ids)):
            from_ids = self._corridor_entity.from_nodes.csr.get_row(corridor_index)
            to_ids = self._corridor_entity.to_nodes.csr.get_row(corridor_index)
            num_connections[corridor_index] += len(from_ids) * len(to_ids)
            publish_geometry = self.publish_corridor_geometry

            for from_id in from_ids:
                paths = self._project.get_shortest_paths(from_id, to_ids)
                for to_id, path in zip(to_ids, paths):
                    if path is None:
                        self._logger.warning(
                            f"Nodes {from_id}-{to_id} doesnt have a valid path between them."
                        )
                        continue
                    self._calculate_properties_for(
                        corridor_index,
                        from_id,
                        to_id,
                        path,
                        roads_index,
                        demand_nodes_index,
                        publish_geometry,
                    )
                    publish_geometry = False

        self._calculate_average_travel_time(num_connections)

    def _calculate_properties_for(
        self,
        corridor_index: int,
        from_id: int,
        to_id: int,
        path: GraphPath,
        roads_index: Index,
        demand_nodes_index: Index,
        publish_corridor_geometry: bool,
    ):
        from_idx = demand_nodes_index[[from_id]][0]
        to_idx = demand_nodes_index[[to_id]][0]
        passenger_demand = self._demand_nodes.passenger_demand.csr.get_row(from_idx)[to_idx]
        cargo_demand = self._demand_nodes.cargo_demand.csr.get_row(from_idx)[to_idx]
        pcu_demand = self.cargo_pcu * cargo_demand + passenger_demand

        self._add_node_properties(corridor_index, passenger_demand, cargo_demand, pcu_demand)

        if path.links is None:
            return

        roads_indices = roads_index[path.links][1:-1]
        if len(roads_indices) == 0:
            return

        self._add_link_properties(corridor_index, roads_indices, pcu_demand)

        if publish_corridor_geometry:
            self._calculate_geometry(corridor_index, roads_indices)

    def _add_node_properties(
        self, corridor_index: int, passenger_demand: float, cargo_demand: float, pcu_demand: float
    ) -> None:
        self._corridor_entity.passenger_flow[corridor_index] += passenger_demand
        self._corridor_entity.cargo_flow[corridor_index] += cargo_demand
        self._corridor_entity.passenger_car_unit[corridor_index] += pcu_demand

    def _add_link_properties(
        self, corridor_index: int, roads_indices: np.ndarray, pcu_demand: float
    ) -> None:
        self._calculate_energy_kpis(corridor_index, roads_indices, pcu_demand)
        self._calculate_weighted_travel_time(corridor_index, roads_indices, pcu_demand)
        self._calculate_max_delay_factor(corridor_index, roads_indices)
        self._calculate_max_volume_to_capacity(corridor_index, roads_indices)

    def _calculate_energy_kpis(
        self, corridor_index: int, roads_indices: np.ndarray, pcu_demand: float
    ) -> None:
        road_pcu = self._transport_segments.passenger_car_unit[roads_indices]
        weight_factors = np.minimum(pcu_demand / road_pcu, 1)

        self._corridor_entity.co2_emission[corridor_index] += self._weighted_sum(
            self._transport_segments.co2_emission[roads_indices], weight_factors
        )
        self._corridor_entity.nox_emission[corridor_index] += self._weighted_sum(
            self._transport_segments.nox_emission[roads_indices], weight_factors
        )
        self._corridor_entity.energy_consumption[corridor_index] += self._weighted_sum(
            self._transport_segments.energy_consumption[roads_indices], weight_factors
        )

    def _calculate_weighted_travel_time(
        self, corridor_index: int, roads_indices: np.ndarray, pcu_demand: float
    ) -> None:
        self._corridor_entity.travel_time[corridor_index] += (
            pcu_demand + self.epsilon
        ) * self._transport_segments.travel_time[roads_indices].sum()

    def _calculate_average_travel_time(self, num_connections: np.ndarray) -> None:
        self._corridor_entity.travel_time.array /= (
            self._corridor_entity.passenger_car_unit.array + num_connections * self.epsilon
        )

    def _calculate_max_delay_factor(self, corridor_index: int, roads_indices: np.ndarray) -> None:
        self._corridor_entity.delay_factor[corridor_index] = np.maximum(
            self._corridor_entity.delay_factor[corridor_index],
            (
                self._transport_segments.travel_time[roads_indices].sum()
                / self._free_flow_times[roads_indices].sum()
            ),
        )

    def _calculate_max_volume_to_capacity(
        self, corridor_index: int, roads_indices: np.ndarray
    ) -> None:
        self._corridor_entity.max_volume_to_capacity[corridor_index] = np.maximum(
            self._corridor_entity.max_volume_to_capacity[corridor_index],
            (
                self._transport_segments.passenger_car_unit[roads_indices]
                / ae_util.calculate_capacities(
                    self._transport_segments.capacity[roads_indices],
                    self._transport_segments.layout[roads_indices],
                )
            ).max(),
        )

    def _calculate_geometry(self, corridor_index, roads_indices):
        linestring_data = []
        linestring_row_ptr = [0]

        roads_linestring_csr = self._transport_segments.linestring.csr

        for i, road_index in enumerate(roads_indices):
            line = roads_linestring_csr.get_row(road_index)[:, :2]
            line_list = line.tolist()
            if self._transport_directions[road_index] == -1:
                line_list = list(reversed(line_list))
            if i > 0:
                line_list = line_list[1:]
            linestring_data += line_list
        linestring_row_ptr.append(len(linestring_data))

        existing_road_geometry = self._corridor_entity.line2d.csr.get_row(corridor_index)
        if not np.array_equal(existing_road_geometry, linestring_data):
            corridor_linestring_csr = TrackedCSRArray(linestring_data, linestring_row_ptr)
            self._corridor_entity.line2d.csr.update(
                corridor_linestring_csr, np.array([corridor_index])
            )

    @staticmethod
    def _weighted_sum(array: np.ndarray, weights: np.ndarray) -> float:
        return (array * weights).sum()

    def _reset_values(self) -> None:
        self._corridor_entity.passenger_flow[:] = 0
        self._corridor_entity.cargo_flow[:] = 0
        self._corridor_entity.passenger_car_unit[:] = 0
        self._corridor_entity.travel_time[:] = 0
        self._corridor_entity.co2_emission[:] = 0
        self._corridor_entity.nox_emission[:] = 0
        self._corridor_entity.energy_consumption[:] = 0
        self._corridor_entity.max_volume_to_capacity[:] = 0
        self._corridor_entity.delay_factor[:] = 0

    def shutdown(self) -> None:
        if self._project:
            self._project.close()
            self._project = None
