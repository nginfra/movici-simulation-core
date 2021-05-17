import typing as t

import numpy as np

from model_engine import TimeStamp, Config, DataFetcher
from movici_simulation_core.ae_wrapper.collections import (
    AssignmentResultCollection,
)
from movici_simulation_core.ae_wrapper.project import ProjectWrapper, AssignmentParameters
from movici_simulation_core.base_model.base import TrackedBaseModel
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common import model_util, ae_util
from movici_simulation_core.models.common.entities import (
    PointEntity,
    VirtualLinkEntity,
)
from .dataset import (
    DemandNodeEntity,
    TrafficTransportSegmentEntity,
)


class Model(TrackedBaseModel):
    """
    Calculates traffic properties on roads
    """

    vdf_alpha: float
    vdf_beta: float
    cargo_pcu: float

    def __init__(self):
        self.project: t.Optional[ProjectWrapper] = None
        self._transport_segments: t.Optional[TrafficTransportSegmentEntity] = None
        self._transport_nodes: t.Optional[PointEntity] = None
        self._demand_nodes: t.Optional[DemandNodeEntity] = None
        self._demand_links: t.Optional[VirtualLinkEntity] = None

    def setup(
        self, state: TrackedState, config: dict, scenario_config: Config, data_fetcher: DataFetcher
    ):
        transport_type = model_util.get_transport_type(config)
        transport_dataset_name = config[transport_type][0]

        self._transport_segments = state.register_entity_group(
            transport_dataset_name,
            TrafficTransportSegmentEntity(name=model_util.dataset_to_segments[transport_type]),
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

        self.project = ProjectWrapper(scenario_config.TEMP_DIR)

        default_parameters = AssignmentParameters()
        self.vdf_alpha = config.get("vdf_alpha", default_parameters.vdf_alpha)
        self.vdf_beta = config.get("vdf_beta", default_parameters.vdf_beta)
        self.cargo_pcu = config.get("cargo_pcu", default_parameters.cargo_pcu)

    def initialize(self, state: TrackedState):
        self._transport_segments.ensure_ready()

        ae_util.fill_project(
            self.project,
            demand_nodes=self._demand_nodes,
            demand_links=self._demand_links,
            transport_nodes=self._transport_nodes,
            transport_segments=self._transport_segments,
        )

        self.project.add_column("free_flow_time", self.project.calculate_free_flow_times())
        self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)

    def update(self, state: TrackedState, time_stamp: TimeStamp) -> t.Optional[TimeStamp]:
        self._process_link_changes()

        passenger_demand = self._get_matrix(self._demand_nodes.passenger_demand.csr)
        cargo_demand = self._get_matrix(self._demand_nodes.cargo_demand.csr)

        results = self.project.assign_traffic(
            passenger_demand,
            cargo_demand,
            AssignmentParameters(
                vdf_alpha=self.vdf_alpha, vdf_beta=self.vdf_beta, cargo_pcu=self.cargo_pcu
            ),
        )

        self._publish_results(results)

        return None

    def shutdown(self):
        if self.project:
            self.project.close()
            self.project = None

    @staticmethod
    def _get_matrix(csr_array: TrackedCSRArray):
        matrix = []
        for i in range(csr_array.size):
            matrix.append(csr_array.get_row(i))
        return np.stack(matrix)

    def _publish_results(self, results: AssignmentResultCollection):
        real_link_len = len(self._transport_segments.index.ids)
        self._transport_segments.passenger_flow[:] = results.passenger_flow[:real_link_len]
        self._transport_segments.cargo_flow[:] = results.cargo_flow[:real_link_len]
        self._transport_segments.average_time[:] = results.congested_time[:real_link_len]
        self._transport_segments.delay_factor[:] = results.delay_factor[:real_link_len]
        self._transport_segments.passenger_car_unit[:] = results.passenger_car_unit[:real_link_len]

        # Calculate volume_to_capacity ourselves because aequilibrae is broken
        # self.road_segments.volume_to_capacity[:] = results.volume_to_capacity[:real_link_len]
        self._transport_segments.volume_to_capacity[:] = results.passenger_car_unit[
            :real_link_len
        ] / ae_util.calculate_capacities(
            self._transport_segments.capacity.array, self._transport_segments.layout.array
        )

        # Aequilibrae does not like 0 capacity, so we have to post correct
        correction_indices = self._transport_segments.capacity.array <= ae_util.eps
        self._transport_segments.passenger_flow[correction_indices] = 0
        self._transport_segments.cargo_flow[correction_indices] = 0
        self._transport_segments.passenger_car_unit[correction_indices] = 0
        self._transport_segments.average_time[correction_indices] = 1e9
        self._transport_segments.delay_factor[correction_indices] = 1
        self._transport_segments.volume_to_capacity[correction_indices] = 0

    def _process_link_changes(self):
        changed = False
        if self._transport_segments.max_speed.has_changes():
            self.project.update_column("speed_ab", self._transport_segments.max_speed)
            self.project.update_column("speed_ba", self._transport_segments.max_speed)
            changed = True

        if (
            self._transport_segments.capacity.has_changes()
            or self._transport_segments.layout.has_changes()
        ):
            new_capacities = ae_util.calculate_capacities(
                self._transport_segments.capacity.array, self._transport_segments.layout.array
            )
            self.project.update_column("capacity_ab", new_capacities)
            self.project.update_column("capacity_ba", new_capacities)

            changed = True

        if changed:
            self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)
