from __future__ import annotations

import dataclasses
import typing as t

import numpy as np

from movici_simulation_core.ae_wrapper.collections import AssignmentResultCollection
from movici_simulation_core.ae_wrapper.project import AssignmentParameters, ProjectWrapper
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.arrays import TrackedCSRArray
from movici_simulation_core.core.attribute import UniformAttribute
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSpec, attributes_from_dict
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.common import ae_util, model_util
from movici_simulation_core.models.common.entity_groups import PointEntity, VirtualLinkEntity
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from . import dataset as ds


class Model(TrackedModel, name="traffic_assignment_calculation"):
    """
    Calculates traffic attributes on roads
    """

    vdf_alpha: t.Union[float, str]
    vdf_beta: float
    cargo_pcu: float
    project: t.Optional[ProjectWrapper] = None
    transport_segments: t.Optional[ds.TrafficTransportSegmentEntity] = None
    transport_nodes: t.Optional[PointEntity] = None
    demand_nodes: t.Optional[ds.DemandNodeEntity] = None
    demand_links: t.Optional[VirtualLinkEntity] = None
    modality: ModalityStrategy

    def __init__(self, model_config):
        model_config = ensure_valid_config(
            model_config,
            "2",
            {
                "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                "2": {"schema": MODEL_CONFIG_SCHEMA_PATH, "convert_from": {"1": convert_v1_v2}},
            },
        )
        super().__init__(model_config)

    def setup(self, state: TrackedState, settings: Settings, **_):
        transport_type, dataset_name = model_util.get_transport_info(self.config)
        self.modality = modalities[transport_type]()
        self.modality.setup_state(self, state, dataset_name)

        self.project = ProjectWrapper(settings.temp_dir)

    def initialize(self, **_):
        self.transport_segments.ensure_ready()

        ae_util.fill_project(
            self.project,
            demand_nodes=self.demand_nodes,
            demand_links=self.demand_links,
            transport_nodes=self.transport_nodes,
            transport_segments=self.transport_segments,
        )

        self.modality.initialize_parameters(self)
        self.modality.process_links(self, init=True)

    def update(self, **_) -> t.Optional[Moment]:
        self.modality.process_links(self)

        passenger_demand, cargo_demand = self.modality.get_demands(self)

        results = self.project.assign_traffic(
            od_matrix_passenger=passenger_demand,
            od_matrix_cargo=cargo_demand,
            parameters=AssignmentParameters(
                vdf_alpha=self.vdf_alpha, vdf_beta=self.vdf_beta, cargo_pcu=self.cargo_pcu
            ),
        )

        self.modality.publish_results(self, results)

        return None

    def shutdown(self, **_) -> None:
        if self.project:
            self.project.close()
            self.project = None

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(ds))


@dataclasses.dataclass(frozen=True)
class PublishAttribute:
    name: str
    target: t.Optional[str] = None
    correction_value: float = 0


class ModalityStrategy:
    transport_type: str
    transport_segment_entity: t.Type[
        ds.TrafficTransportSegmentEntity
    ] = ds.TrafficTransportSegmentEntity
    publish_attributes: t.Sequence[PublishAttribute] = (
        PublishAttribute("passenger_flow"),
        PublishAttribute("cargo_flow"),
        PublishAttribute("passenger_car_unit"),
        PublishAttribute("volume_to_capacity"),
        PublishAttribute("delay_factor", correction_value=1),
        PublishAttribute("congested_time", target="average_time", correction_value=1e9),
    )

    def initialize_parameters(self, model: Model):
        default_parameters = AssignmentParameters()
        model.vdf_alpha = model.config.get("vdf_alpha", default_parameters.vdf_alpha)
        model.vdf_beta = model.config.get("vdf_beta", default_parameters.vdf_beta)
        model.cargo_pcu = model.config.get("cargo_pcu", default_parameters.cargo_pcu)

    def setup_state(self, model: Model, state: TrackedState, dataset_name: str):

        model.transport_segments = state.register_entity_group(
            dataset_name,
            self.transport_segment_entity(
                name=model_util.modality_link_entities[self.transport_type]
            ),
        )
        model.transport_nodes = state.register_entity_group(
            dataset_name, PointEntity(name="transport_node_entities")
        )
        model.demand_nodes = state.register_entity_group(
            dataset_name,
            ds.DemandNodeEntity(name="virtual_node_entities"),
        )
        model.demand_links = state.register_entity_group(
            dataset_name, VirtualLinkEntity(name="virtual_link_entities")
        )

    def process_links(self, model: Model, init: bool = False) -> bool:
        changed = any(
            [
                meth(model, init=init)
                for meth in (
                    self.process_max_speed,
                    self.process_free_flow_time,
                    self.process_capacity,
                )
            ]
        )
        if changed:
            model.project.build_graph(cost_field="free_flow_time", block_centroid_flows=True)
        return changed

    def process_max_speed(self, model: Model, init=False) -> bool:
        changed = model.transport_segments.max_speed.has_changes()
        if changed:
            max_speeds = ae_util.get_max_speeds_from_attribute(model.transport_segments.max_speed)
            model.project.update_column("speed_ab", max_speeds)
            model.project.update_column("speed_ba", max_speeds)
        return changed

    def process_free_flow_time(self, model: Model, init=False) -> bool:
        changed = init or (
            model.transport_segments.max_speed.has_changes()
            or model.transport_segments.additional_time.has_changes()
        )
        meth = model.project.add_column if init else model.project.update_column

        if changed:
            meth("free_flow_time", self.free_flow_time(model))

        return changed

    def free_flow_time(self, model: Model) -> np.ndarray:
        free_flow_times = model.project.calculate_free_flow_times()
        free_flow_times[: len(model.transport_segments)] += np.nan_to_num(
            model.transport_segments.additional_time.array
        )
        return free_flow_times

    def process_capacity(self, model: Model, init=False) -> bool:
        changed = (
            model.transport_segments.capacity.has_changes()
            or model.transport_segments.layout.has_changes()
        )

        if changed:
            capacities = ae_util.get_capacities_from_attribute(
                model.transport_segments.capacity, model.transport_segments.layout
            )
            model.project.update_column("capacity_ab", capacities)
            model.project.update_column("capacity_ba", capacities)
        return changed

    def get_demands(self, model: Model) -> t.Tuple[np.ndarray, np.ndarray]:
        passenger_demand = model.demand_nodes.passenger_demand.csr.as_matrix()
        cargo_demand = model.demand_nodes.cargo_demand.csr.as_matrix()
        return passenger_demand, cargo_demand

    def publish_results(self, model: Model, results: AssignmentResultCollection):
        real_link_len = len(model.transport_segments.index.ids)

        # Aequilibrae does not like 0 capacity, so we have to post correct
        capacities = self.get_capacities(model)
        correction_indices = capacities <= ae_util.eps

        for attr in self.publish_attributes:
            target = getattr(model.transport_segments, attr.target or attr.name)
            target[:] = getattr(results, attr.name)[:real_link_len]
            target[correction_indices] = attr.correction_value

    def get_capacities(self, model: Model):
        return ae_util.get_capacities_from_attribute(model.transport_segments.capacity)


class RoadModality(ModalityStrategy):
    transport_type = "roads"
    pass


class WaterwayModality(ModalityStrategy):
    transport_type = "waterways"

    def initialize_parameters(self, model: Model):
        super().initialize_parameters(model)
        model.vdf_beta = 4.9
        model.vdf_alpha = "alpha"

        model.project.add_column(model.vdf_alpha, self.alpha(model))

    def free_flow_time(self, model: Model) -> np.ndarray:
        seconds_per_minute = 60
        s = 23 * seconds_per_minute
        segments_with_locks = np.where(~model.transport_segments.capacity.is_special())[0]
        t_ff_prime = super().free_flow_time(model)
        t_ff_prime[segments_with_locks] += s
        return t_ff_prime

    def alpha(self, model: Model) -> np.ndarray:
        """
        We want waterway segments with locks to have an additional waiting time t_wait
        We set the free_flow_times of these segments as

        t_ff' = t_ff + t_wait

        To convert it to vdf terms:

        t_ff' = t_ff + s'
        a = r / t_ff'
        b = 4.9

        With these aequilibrae can compute:
        vdf = t_ff' * (1 + a * volume_over_capacity**b)
        """
        seconds_per_minute = 60
        r = 344 * seconds_per_minute
        segments_with_locks = np.where(~model.transport_segments.capacity.is_special())[0]

        free_flow_times = self.free_flow_time(model)

        alpha_fill = np.full_like(free_flow_times, AssignmentParameters().vdf_alpha)
        alpha_fill[segments_with_locks] = r / free_flow_times[segments_with_locks]
        return alpha_fill


class TrackModality(ModalityStrategy):
    transport_type = "tracks"
    transport_segment_entity = ds.TrackSegmentEntity
    publish_attributes: t.Sequence[PublishAttribute] = (
        PublishAttribute("passenger_flow"),
        PublishAttribute("cargo_flow"),
        PublishAttribute("congested_time", target="average_time", correction_value=1e9),
    )

    def initialize_parameters(self, model: Model):
        super().initialize_parameters(model)
        model.vdf_alpha = 0


class PassengerTrackModality(TrackModality):
    transport_type = "passenger_tracks"
    transport_segment_entity = ds.PassengerTrackSegmentEntity

    publish_attributes: t.Sequence[PublishAttribute] = (
        PublishAttribute("passenger_flow"),
        PublishAttribute("congested_time", target="passenger_average_time", correction_value=1e9),
    )

    def get_demands(self, model: Model) -> t.Tuple[np.ndarray, np.ndarray]:
        passenger_demand = model.demand_nodes.passenger_demand.csr.as_matrix()
        cargo_demand = np.zeros_like(passenger_demand)
        return passenger_demand, cargo_demand


class CargoTrackModality(TrackModality):
    transport_type = "cargo_tracks"
    transport_segment_entity = ds.CargoTrackSegmentEntity

    publish_attributes: t.Sequence[PublishAttribute] = (
        PublishAttribute("cargo_flow"),
        PublishAttribute("congested_time", target="cargo_average_time", correction_value=1e9),
    )

    def cargo_allowed(self, model: Model) -> t.Optional[UniformAttribute]:
        attr = getattr(model.transport_segments, "cargo_allowed", None)
        if isinstance(attr, UniformAttribute) and attr.has_data():
            return attr
        return None

    def initialize_parameters(self, model: Model):
        super().initialize_parameters(model)

        model.vdf_alpha = AssignmentParameters.vdf_alpha

    def process_capacity(self, model: Model, init=False) -> bool:
        attr = self.cargo_allowed(model)
        changed = init or (attr is not None and attr.has_changes())

        if changed:
            capacities = self.get_capacities(model)
            model.project.update_column("capacity_ab", capacities)
            model.project.update_column("capacity_ba", capacities)
        return changed

    def get_capacities(self, model: Model):
        attr = self.cargo_allowed(model)
        if attr is None:
            return super().get_capacities(model)
        cargo_allowed = ae_util.get_cargo_allowed_from_attribute(attr)

        capacities = np.full_like(
            model.transport_segments.capacity, fill_value=np.inf, dtype=float
        )
        capacities[np.nonzero(~cargo_allowed)] = ae_util.eps
        return capacities

    def get_demands(self, model: Model) -> t.Tuple[np.ndarray, np.ndarray]:
        cargo_demand = model.demand_nodes.cargo_demand.csr.as_matrix()
        passenger_demand = np.zeros_like(cargo_demand)
        return passenger_demand, cargo_demand


modalities: t.Dict[str, t.Type[ModalityStrategy]] = {
    "roads": RoadModality,
    "waterways": WaterwayModality,
    "tracks": TrackModality,
    "cargo_tracks": CargoTrackModality,
    "passenger_tracks": PassengerTrackModality,
}


def get_matrix(csr_array: TrackedCSRArray):
    if len(csr_array.data) != csr_array.size**2:
        raise ValueError("Array is not a valid demand matrix")
    return csr_array.data.copy().reshape((csr_array.size, csr_array.size))


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/traffic_assignment_calculation.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/traffic_assignment_calculation.json"


def convert_v1_v2(config):
    modality, dataset = model_util.get_transport_info(config)
    rv = {
        "modality": modality,
        "dataset": dataset,
    }
    for key in ("vdf_beta", "cargo_pcu", "vdf_alpha"):
        if key in config:
            rv[key] = config[key]
    return rv
