import typing as t

import numpy as np

from movici_simulation_core.ae_wrapper.collections import (
    AssignmentResultCollection,
)
from movici_simulation_core.ae_wrapper.project import ProjectWrapper, AssignmentParameters
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.schema import AttributeSpec, attributes_from_dict
from movici_simulation_core.data_tracker.arrays import TrackedCSRArray
from movici_simulation_core.data_tracker.state import TrackedState
from ...model_connector.init_data import InitDataHandler
from movici_simulation_core.models.common import model_util, ae_util
from movici_simulation_core.models.common.entities import (
    PointEntity,
    VirtualLinkEntity,
)
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings
from . import dataset as ds


class Model(TrackedModel, name="traffic_assignment_calculation"):
    """
    Calculates traffic attributes on roads
    """

    vdf_alpha: t.Union[float, str]
    vdf_beta: float
    cargo_pcu: float
    project: t.Optional[ProjectWrapper] = None
    _transport_segments: t.Optional[ds.TrafficTransportSegmentEntity] = None
    _transport_nodes: t.Optional[PointEntity] = None
    _demand_nodes: t.Optional[ds.DemandNodeEntity] = None
    _demand_links: t.Optional[VirtualLinkEntity] = None
    _free_flow_times: t.Optional[np.ndarray] = None
    _use_waterway_parameters = False

    def setup(
        self, state: TrackedState, settings: Settings, init_data_handler: InitDataHandler, **_
    ):
        transport_type = model_util.get_transport_type(self.config)
        transport_dataset_name = self.config[transport_type][0]

        self._transport_segments = state.register_entity_group(
            transport_dataset_name,
            ds.TrafficTransportSegmentEntity(name=model_util.dataset_to_segments[transport_type]),
        )
        self._transport_nodes = state.register_entity_group(
            transport_dataset_name, PointEntity(name="transport_node_entities")
        )
        self._demand_nodes = state.register_entity_group(
            transport_dataset_name,
            ds.DemandNodeEntity(name="virtual_node_entities"),
        )
        self._demand_links = state.register_entity_group(
            transport_dataset_name, VirtualLinkEntity(name="virtual_link_entities")
        )

        if transport_type == "waterways":
            self._use_waterway_parameters = True

        self.project = ProjectWrapper(settings.temp_dir)

        default_parameters = AssignmentParameters()
        self.vdf_alpha = self.config.get("vdf_alpha", default_parameters.vdf_alpha)
        self.vdf_beta = self.config.get("vdf_beta", default_parameters.vdf_beta)
        self.cargo_pcu = self.config.get("cargo_pcu", default_parameters.cargo_pcu)

    def initialize(self, state: TrackedState):
        self._transport_segments.ensure_ready()

        ae_util.fill_project(
            self.project,
            demand_nodes=self._demand_nodes,
            demand_links=self._demand_links,
            transport_nodes=self._transport_nodes,
            transport_segments=self._transport_segments,
        )

        self._free_flow_times = self._calculate_free_flow_times()
        self.project.add_column("free_flow_time", self._free_flow_times)

        if self._use_waterway_parameters:
            self._initialize_waterway_parameters()

        self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        self._process_link_changes()

        passenger_demand = self._get_matrix(self._demand_nodes.passenger_demand.csr)
        cargo_demand = self._get_matrix(self._demand_nodes.cargo_demand.csr)

        results = self.project.assign_traffic(
            od_matrix_passenger=passenger_demand,
            od_matrix_cargo=cargo_demand,
            parameters=AssignmentParameters(
                vdf_alpha=self.vdf_alpha, vdf_beta=self.vdf_beta, cargo_pcu=self.cargo_pcu
            ),
        )

        self._publish_results(results)

        return None

    def shutdown(self, state: TrackedState) -> None:
        if self.project:
            self.project.close()
            self.project = None

    @staticmethod
    def _get_matrix(csr_array: TrackedCSRArray):
        if len(csr_array.data) != csr_array.size ** 2:
            raise ValueError("Array is not a valid demand matrix")
        return csr_array.data.copy().reshape((csr_array.size, csr_array.size))

    def _publish_results(self, results: AssignmentResultCollection):
        real_link_len = len(self._transport_segments.index.ids)
        self._transport_segments.passenger_flow[:] = results.passenger_flow[:real_link_len]
        self._transport_segments.cargo_flow[:] = results.cargo_flow[:real_link_len]
        self._transport_segments.passenger_car_unit[:] = results.passenger_car_unit[:real_link_len]
        self._transport_segments.volume_to_capacity[:] = results.volume_to_capacity[:real_link_len]
        self._transport_segments.delay_factor[:] = results.delay_factor[:real_link_len]
        self._transport_segments.average_time[:] = results.congested_time[:real_link_len]

        # Aequilibrae does not like 0 capacity, so we have to post correct
        capacities = ae_util.get_capacities_from_attribute(self._transport_segments.capacity)
        correction_indices = capacities <= ae_util.eps
        self._transport_segments.passenger_flow[correction_indices] = 0
        self._transport_segments.cargo_flow[correction_indices] = 0
        self._transport_segments.passenger_car_unit[correction_indices] = 0
        self._transport_segments.average_time[correction_indices] = 1e9
        self._transport_segments.delay_factor[correction_indices] = 1
        self._transport_segments.volume_to_capacity[correction_indices] = 0

    def _process_link_changes(self):
        changed = False
        if self._transport_segments.max_speed.has_changes():
            max_speeds = ae_util.get_max_speeds_from_attribute(self._transport_segments.max_speed)
            self.project.update_column("speed_ab", max_speeds)
            self.project.update_column("speed_ba", max_speeds)
            changed = True

        if (
            self._transport_segments.max_speed.has_changes()
            or self._transport_segments.additional_time.has_changes()
        ):
            self._free_flow_times = self._calculate_free_flow_times()
            self.project.update_column("free_flow_time", self._free_flow_times)
            changed = True

        if (
            self._transport_segments.capacity.has_changes()
            or self._transport_segments.layout.has_changes()
        ):
            capacities = ae_util.get_capacities_from_attribute(
                self._transport_segments.capacity, self._transport_segments.layout
            )
            self.project.update_column("capacity_ab", capacities)
            self.project.update_column("capacity_ba", capacities)
            changed = True

        if changed:
            self.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)

    def _initialize_waterway_parameters(self):
        """
        We want waterway segments with locks to have an additional waiting time t_wait
        We set the free_flow_times of these roads as

        t_ff' = t_ff + t_wait

        To convert it to vdf terms:

        t_ff' = t_ff + s'
        a = r / t_ff'
        b = 4.9

        With these aequilibrae can compute:
        vdf = t_ff' * (1 + a * volume_over_capacity**b)
        """
        seconds_per_minute = 60
        s = 23 * seconds_per_minute
        r = 344 * seconds_per_minute
        self.vdf_beta = 4.9

        segments_with_locks = np.where(~self._transport_segments.capacity.is_special())[0]

        total_free_flow_times = self._calculate_waterway_free_flow_times(segments_with_locks, s)
        self.project.update_column("free_flow_time", total_free_flow_times)

        self.vdf_alpha = "alpha"
        alpha = self._calculate_waterway_alpha(segments_with_locks, total_free_flow_times, r)
        self.project.add_column(self.vdf_alpha, alpha)

    def _calculate_waterway_free_flow_times(
        self, finite_indices: np.ndarray, s: float
    ) -> np.ndarray:

        t_ff_prime = self._free_flow_times.copy()
        t_ff_prime[finite_indices] += s
        return t_ff_prime

    def _calculate_free_flow_times(self) -> np.ndarray:
        free_flow_times = self.project.calculate_free_flow_times()
        free_flow_times[: len(self._transport_segments)] += np.nan_to_num(
            self._transport_segments.additional_time.array
        )
        return free_flow_times

    @staticmethod
    def _calculate_waterway_alpha(
        finite_indices: np.ndarray, free_flow_times: np.ndarray, r: float
    ) -> np.ndarray:
        default_alpha = AssignmentParameters().vdf_alpha
        alpha_fill = np.full_like(free_flow_times, default_alpha)
        alpha_fill[finite_indices] = r / free_flow_times[finite_indices]
        return alpha_fill

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(ds))
