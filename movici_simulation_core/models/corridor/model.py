import typing as t
from logging import Logger

import numpy as np

from movici_simulation_core.ae_wrapper.collections import GraphPath
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core import (
    AttributeSpec,
    Index,
    Moment,
    TrackedCSRArray,
    TrackedState,
    attributes_from_dict,
)
from movici_simulation_core.json_schemas import SCHEMA_PATH
from movici_simulation_core.models.common import ae_util, model_util
from movici_simulation_core.models.common.entity_groups import PointEntity, VirtualLinkEntity
from movici_simulation_core.settings import Settings
from movici_simulation_core.validate import ensure_valid_config

from . import attributes
from .entities import CorridorEntity, CorridorTransportSegmentEntity, DemandNodeEntity


class Model(TrackedModel, name="corridor"):
    """Implementation of the corridor model"""

    epsilon = 1e-12

    def __init__(self, model_config: dict, validate_config=True):
        if validate_config:
            model_config = ensure_valid_config(
                model_config,
                "2",
                {
                    "1": {"schema": MODEL_CONFIG_SCHEMA_LEGACY_PATH},
                    "2": {
                        "schema": MODEL_CONFIG_SCHEMA_PATH,
                        "convert_from": {"1": convert_v1_v2},
                    },
                },
            )
        super().__init__(model_config)
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

    def setup(self, state: TrackedState, settings: Settings, **_) -> None:
        self._logger = state.logger
        self.cargo_pcu = self.config.get("cargo_pcu", self.cargo_pcu)
        self.publish_corridor_geometry = self.config.get(
            "publish_corridor_geometry", self.publish_corridor_geometry
        )

        self._project = ProjectWrapper(settings.temp_dir)

        self._corridor_entity = state.register_entity_group(
            dataset_name=self.config["corridors"], entity=CorridorEntity
        )
        self._register_transport_entities(state, self.config)

    def _register_transport_entities(self, state: TrackedState, config: dict) -> None:
        transport_type, transport_dataset_name = model_util.get_transport_info(config)

        self._transport_segments = state.register_entity_group(
            transport_dataset_name,
            CorridorTransportSegmentEntity(name=model_util.modality_link_entities[transport_type]),
        )

        self._transport_nodes = state.register_entity_group(
            transport_dataset_name, PointEntity(name="transport_node_entities")
        )

        self._demand_nodes = state.register_entity_group(
            transport_dataset_name,
            DemandNodeEntity(name="virtual_node_entities"),
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

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
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
                    self._calculate_attributes_for(
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

    def _calculate_attributes_for(
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

        self._add_node_attributes(corridor_index, passenger_demand, cargo_demand, pcu_demand)

        if path.links is None:
            return

        roads_indices = roads_index[path.links][1:-1]
        if len(roads_indices) == 0:
            return

        self._add_link_attributes(corridor_index, roads_indices, pcu_demand)

        if publish_corridor_geometry:
            self._calculate_geometry(corridor_index, roads_indices)

    def _add_node_attributes(
        self, corridor_index: int, passenger_demand: float, cargo_demand: float, pcu_demand: float
    ) -> None:
        self._corridor_entity.passenger_flow[corridor_index] += passenger_demand
        self._corridor_entity.cargo_flow[corridor_index] += cargo_demand
        self._corridor_entity.passenger_car_unit[corridor_index] += pcu_demand

    def _add_link_attributes(
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
        non_zero = road_pcu != 0
        weight_factors = np.ones(len(roads_indices), dtype=np.float64)
        weight_factors[non_zero] = np.minimum(pcu_demand / road_pcu[non_zero], 1)

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

    def shutdown(self, state: TrackedState) -> None:
        if self._project:
            self._project.close()
            self._project = None

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return attributes_from_dict(vars(attributes))


MODEL_CONFIG_SCHEMA_PATH = SCHEMA_PATH / "models/corridor.json"
MODEL_CONFIG_SCHEMA_LEGACY_PATH = SCHEMA_PATH / "models/legacy/corridor.json"


def convert_v1_v2(config):
    rv = {"corridors": config["corridors"][0]}
    for key in ("cargo_pcu", "publish_corridor_geometry"):
        if key in config:
            rv[key] = config[key]

    for key in ("roads", "waterways", "tracks"):
        if key in config:
            rv["dataset"] = config[key][0]
            rv["modality"] = key
            break

    return rv
