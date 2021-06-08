import typing as t
from abc import abstractmethod
from logging import Logger

import numba
import numpy as np
from model_engine import Config
from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.data_tracker.arrays import TrackedArray
from movici_simulation_core.data_tracker.property import UniformProperty
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common import ae_util
from movici_simulation_core.models.common.entities import (
    TransportSegmentEntity,
    PointEntity,
    VirtualLinkEntity,
    GeometryEntity,
)
from movici_simulation_core.models.common.model_util import try_get_geometry_type


class LocalEffectsCalculator:
    _logger: t.Optional[Logger]
    _elasticity: t.Optional[float]
    _indices: t.Optional[np.ndarray]
    _property: t.Optional[UniformProperty]

    def __init__(self):
        self._logger = None
        self._elasticity = None
        self._indices = None
        self._property = None

    @abstractmethod
    def setup(self, **kwargs):
        ...

    @abstractmethod
    def initialize(self, indices: np.ndarray):
        ...

    @abstractmethod
    def update_matrix(self, matrix: np.ndarray, force_update: bool = False):
        ...

    @abstractmethod
    def get_target_entity(self) -> GeometryEntity:
        ...

    def property_has_changes(self) -> bool:
        return self._property.has_changes()

    def shutdown(self):
        pass


class NearestValue(LocalEffectsCalculator):
    def __init__(self):
        super().__init__()
        self._old_prop_value: t.Optional[TrackedArray] = None
        self._target_entity: t.Optional[GeometryEntity] = None

    def setup(
        self,
        state: TrackedState,
        prop: UniformProperty,
        ds_name: str,
        entity_name: str,
        geom: str,
        elasticity: float,
        **kwargs,
    ):
        self._property = prop
        self._elasticity = elasticity
        self._logger = state.logger

        self._target_entity = state.register_entity_group(
            dataset_name=ds_name,
            entity=try_get_geometry_type(geom)(name=entity_name),
        )

    def initialize(self, indices: np.ndarray):
        self._indices = indices

    def update_matrix(self, matrix: np.ndarray, force_update: bool = False):
        if self._old_prop_value is None:
            self._old_prop_value = self._property.array.copy()
            return

        if not self._property.has_changes() and not force_update:
            return

        update_multiplication_factor_nearest(
            matrix,
            self._indices,
            self._property.array,
            self._old_prop_value,
            self._elasticity,
        )
        self._old_prop_value = self._property.array.copy()

    def get_target_entity(self) -> GeometryEntity:
        return self._target_entity


class TransportPathingValueSum(LocalEffectsCalculator):
    def __init__(self):
        super().__init__()
        self._property: t.Optional[UniformProperty] = None
        self._transport_segments: t.Optional[TransportSegmentEntity] = None
        self._transport_nodes: t.Optional[PointEntity] = None
        self._demand_nodes: t.Optional[PointEntity] = None
        self._demand_links: t.Optional[VirtualLinkEntity] = None
        self._project: t.Optional[ProjectWrapper] = None
        self._old_summed_values: t.Optional[np.ndarray] = None

    def setup(
        self,
        state: TrackedState,
        prop: UniformProperty,
        ds_name: str,
        entity_name: str,
        geom: str,
        elasticity: float,
        scenario_config: Config,
        **kwargs,
    ):
        self._project = ProjectWrapper(scenario_config.TEMP_DIR)
        self._property = prop
        self._elasticity = elasticity

        if geom != "line":
            raise RuntimeError(f"Local property routing has to have line type, not {geom}")

        self._transport_segments = state.register_entity_group(
            ds_name,
            TransportSegmentEntity(name=entity_name),
        )

        self._transport_nodes = state.register_entity_group(
            ds_name, PointEntity(name="transport_node_entities")
        )

        self._demand_nodes = state.register_entity_group(
            ds_name,
            PointEntity(name="virtual_node_entities"),
        )

        self._demand_links = state.register_entity_group(
            ds_name, VirtualLinkEntity(name="virtual_link_entities")
        )

        self._logger = state.logger

    def initialize(self, indices: np.ndarray):
        self._transport_segments.ensure_ready()
        self._indices = indices

        ae_util.fill_project(
            self._project,
            demand_nodes=self._demand_nodes,
            demand_links=self._demand_links,
            transport_nodes=self._transport_nodes,
            transport_segments=self._transport_segments,
        )

        self._project.add_column("cost_field")

    def update_matrix(self, matrix: np.ndarray, force_update: bool = False):
        updated = self.update_graph(force_update=force_update)

        if not updated:
            return

        (
            new_values_matrix,
            old_values_matrix,
        ) = self.get_new_and_old_summed_value_along_paths()
        update_multiplication_factor_matrix(
            matrix, new_values_matrix, old_values_matrix, self._elasticity
        )

    def update_graph(self, force_update: bool = False) -> bool:
        if self._old_summed_values is None:
            self._update_graph()
            self._old_summed_values = self._get_new_summed_values_along_paths()
            return False

        if self._property.has_changes() or force_update:
            self._update_graph()
            return True

        return False

    def _update_graph(self):
        self._project.update_column("cost_field", self._property.array)
        self._project.build_graph(
            cost_field="cost_field",
            block_centroid_flows=True,
        )

    def _get_new_summed_values_along_paths(self) -> np.ndarray:
        """
        For N _demand_nodes, these have N nearest, with possible duplicates
        We get M unique nearest, calculate MxM routes from all to all
        Then we sample that back to N nearest
        """
        ids = self._demand_nodes.index.ids
        segment_index = self._transport_segments.index

        unique_indices = np.unique(self._indices)
        nb_unique_nodes = len(unique_indices)
        summed_values = np.full(shape=(nb_unique_nodes, nb_unique_nodes), fill_value=np.inf)
        for i, from_idx in enumerate(unique_indices):
            paths = self._project.get_shortest_paths(ids[from_idx], ids[unique_indices])
            for j, (to_idx, path) in enumerate(zip(unique_indices, paths)):
                if i == j:
                    summed_values[i][j] = 0
                    continue
                if path is None:
                    self._logger.warning(
                        f"Nodes {ids[from_idx]}-{ids[to_idx]} "
                        f"do not have a valid path between them."
                    )
                    continue

                roads_indices = segment_index[path.links][1:-1]
                summed_values[i][j] = self._property[roads_indices].sum()

        # rebuild requested sized matrix of shape=(len(self._closest_idx), len(self._closest_idx))
        orig_idx = self._array_index_in_array(unique_indices, self._indices)
        return summed_values[:, orig_idx][orig_idx, :]

    def get_new_and_old_summed_value_along_paths(self) -> (np.ndarray, np.ndarray):
        old = self._old_summed_values
        new = self._get_new_summed_values_along_paths()
        self._old_summed_values = new
        return new, old

    @staticmethod
    def _array_index_in_array(x: np.ndarray, y: np.ndarray):
        """
        find position of y in x, from https://stackoverflow.com/a/8251757
        """
        index = np.argsort(x)
        sorted_x = x[index]
        sorted_index = np.searchsorted(sorted_x, y)
        return sorted_index

    def get_target_entity(self) -> PointEntity:
        return self._demand_nodes

    def shutdown(self):
        if self._project:
            self._project.close()
            self._project = None


@numba.njit(cache=True)
def update_multiplication_factor_matrix(
    multiplication_factor: np.ndarray, matrix: np.ndarray, matrix_old: np.ndarray, elasticity
):
    dim_i, dim_j = multiplication_factor.shape
    for i in range(dim_i):
        for j in range(dim_j):
            numerator = matrix[i][j]
            denominator = matrix_old[i][j]
            if denominator == 0:
                if numerator != 0:
                    raise RuntimeError("Cost-value became zero, can't divide by 0")
                continue
            multiplication_factor[i][j] *= (numerator / denominator) ** elasticity


@numba.njit(cache=True)
def update_multiplication_factor_nearest(
    multiplication_factor: np.ndarray, closest_entity_index, prop, old_prop, elasticity
):
    dim_i, dim_j = multiplication_factor.shape
    for i in range(dim_i):
        for j in range(dim_j):
            i_closest = closest_entity_index[i]
            j_closest = closest_entity_index[j]

            prop_i = prop[i_closest]
            old_prop_i = old_prop[i_closest]

            prop_j = prop[j_closest]
            old_prop_j = old_prop[j_closest]

            if old_prop_i != 0:
                multiplication_factor[i][j] *= (prop_i / old_prop_i) ** elasticity
            if old_prop_j != 0:
                multiplication_factor[i][j] *= (prop_j / old_prop_j) ** elasticity
