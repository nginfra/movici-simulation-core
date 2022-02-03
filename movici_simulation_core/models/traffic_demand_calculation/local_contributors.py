from pathlib import Path
import dataclasses
import functools
import logging
import typing as t

from movici_simulation_core.ae_wrapper.project import ProjectWrapper
from movici_simulation_core.core.schema import AttributeSchema, DataType
from movici_simulation_core.data_tracker.attribute import (
    INIT,
    AttributeObject,
    CSRAttribute,
    UniformAttribute,
)
from movici_simulation_core.data_tracker.index import Index
from movici_simulation_core.data_tracker.state import TrackedState
from movici_simulation_core.models.common import ae_util
from movici_simulation_core.models.common.entities import (
    GeometryEntity,
    PointEntity,
    TransportSegmentEntity,
    VirtualLinkEntity,
)
from movici_simulation_core.models.common.model_util import (
    find_y_in_x,
    safe_divide,
    try_get_geometry_type,
)
from movici_simulation_core.models.common.network import Network, NetworkEntities
from movici_simulation_core.utils.moment import Moment
from movici_simulation_core.utils.settings import Settings
import numba
import numpy as np

from .common import LocalContributor, LocalMapper


@dataclasses.dataclass
class LocalParameterInfo:
    target_dataset: str
    target_entity_group: str
    target_geometry: str
    target_attribute: AttributeObject
    elasticity: float


class LocalEffectsContributor(LocalContributor):
    _indices: t.Optional[np.ndarray] = None
    old_value: t.Optional[np.ndarray] = None

    def __init__(self, info: LocalParameterInfo):
        self.info = info
        self._attribute = info.target_attribute
        self._elasticity = info.elasticity

    def update_demand(self, matrix: np.ndarray, force_update: bool = False, **_) -> np.ndarray:
        if self.old_value is None:
            self.old_value = self.calculate_values()
            return matrix

        if not self.has_changes() and not force_update:
            return matrix

        new_values = self.calculate_values()

        factor = self.calculate_contribution(new_values, self.old_value)
        self.old_value = new_values
        return factor * matrix

    def has_changes(self) -> bool:
        return self._attribute.has_changes()

    def calculate_values(self):
        """Calculate parameter values P[] so that P_ij can be reconstructed, this can be a 1d-array
        which together with self._indices can reconstruct P_ij (See eg. `NearestValue`) or a
        2d-array containing every P_ij (See `RouteCostFactor`). P_ij will then be used to calculate
        the contribution (P_ij/P_ij_old)**elasticity to the demand change factor
        """
        raise NotImplementedError

    def calculate_contribution(self, new_values, old_values):
        """Calculate the contribution (P_ij/P_ij_old)**elasticity to the demand change factor"""
        rv = safe_divide(new_values, old_values, fill_value=1)
        nonzero = np.nonzero(rv)
        rv[nonzero] = rv[nonzero] ** self._elasticity
        return rv


class NearestValue(LocalEffectsContributor):
    _target_entity: t.Optional[GeometryEntity] = None

    def __init__(self, info: LocalParameterInfo):
        super().__init__(info)
        self._is_csr = isinstance(self._attribute, CSRAttribute)

    def setup(
        self,
        state: TrackedState,
        **_,
    ):
        ds_name = self.info.target_dataset
        geom = self.info.target_geometry
        entity_name = self.info.target_entity_group

        self._target_entity = state.register_entity_group(
            dataset_name=ds_name,
            entity=try_get_geometry_type(geom)(name=entity_name),
        )

    def initialize(self, mapper: LocalMapper):
        self._indices = mapper.get_nearest(self._target_entity)

    def calculate_values(self):
        if self._is_csr:
            return self._calculate_values_csr()

        return self._caculate_values_uniform()

    def _caculate_values_uniform(self):
        return self._attribute.array.copy()

    def _calculate_values_csr(self):
        matrix = self._attribute.csr.as_matrix()
        if matrix.shape[0] != matrix.shape[1]:
            raise ValueError(
                "Only square CSR matrices are supported for nearest value calculation"
            )
        return matrix[:, self._indices][self._indices, :]

    def calculate_contribution(self, new_values, old_values):
        if self._is_csr:
            return super().calculate_contribution(new_values, old_values)

        return calculate_localized_contribution_1d(
            new_values, old_values, self._indices, self._elasticity
        )


@numba.njit(cache=True)
def calculate_localized_contribution_1d(values, old_values, indices, elasticity):
    size = len(indices)
    rv = np.ones((size, size), np.float64)
    for i in range(size):
        for j in range(size):
            # symmetry: factor for ij == ji so we only need to iterate through half of the ij_pairs
            # and fill up both ij and ji at the same time
            if i < j:
                continue
            ratio_i = get_ratio_for_node(i, values, old_values, indices)
            ratio_j = get_ratio_for_node(j, values, old_values, indices)
            factor = (ratio_i * ratio_j) ** elasticity
            rv[i][j] = rv[j][i] = factor
    return rv


@numba.njit(cache=True)
def get_ratio_for_node(node_i, values, old_values, indices):
    closest = indices[node_i]

    val = values[closest]
    old_val = old_values[closest]
    if val == 0 or old_val == 0:
        return 1
    return val / old_val


class ShortestPathMixin:
    _network: t.Optional[Network] = None
    _network_entities: t.Optional[NetworkEntities] = None

    def setup_state(self, state: TrackedState, info: LocalParameterInfo):
        ds_name = info.target_dataset
        entity_name = info.target_entity_group
        geom = info.target_geometry

        if geom != "line":
            raise RuntimeError(
                f"Local entity group for shortest path calculations have line type, not {geom}"
            )
        self._network_entities = Network.register_required_attributes(
            state, dataset_name=ds_name, transport_segments_name=entity_name
        )

    def initialize_network(self):
        self._network_entities["transport_links"].ensure_ready()

        self._network = Network(**self._network_entities)

    @staticmethod
    def deduplicate_nodes(meth):
        """When mapping a demand OD matrix onto a target network, such as the effect of travel time
        on roads (target network) on the waterway demand (demand OD matrix). There may be duplicate
        mapped road virtual nodes, since this is an N -> M mapping, where M <= N. As an
        optimization, these duplicates can be detected by this decorator, and only the unique
        indices are passed to the decorated method as the first positional argument after `self`.
        The decorated method is expected to return a MxM matrix and this decorator expands it back
        to NxN

        This only works for methods in classes that inherit from `LocalEffectsContributor`

        """

        @functools.wraps(meth)
        def wrapper(self: LocalEffectsContributor, *args, **kwargs):
            if self._indices is None:
                raise ValueError("indices not set")
            unique_indices = np.unique(self._indices)
            result = meth(self, unique_indices, *args, **kwargs)
            orig_idx = find_y_in_x(unique_indices, self._indices)
            return result[:, orig_idx][orig_idx, :]

        return wrapper


class RouteCostFactor(LocalEffectsContributor, ShortestPathMixin):
    """
    This effect calculator computes the paths between pairs of demand nodes
    connected by a route.
    It calculates the sum of the given _attribute on this route and returns that.
    """

    _logger: logging.Logger = None

    @property
    def _demand_nodes(self):
        return self._network_entities["virtual_nodes"]

    def setup(
        self,
        *,
        state: TrackedState,
        logger: logging.Logger,
        **_,
    ):
        self.setup_state(state, self.info)
        self._logger = logger

    def initialize(self, mapper: LocalMapper):
        self._indices = mapper.get_nearest(self._demand_nodes)
        self.initialize_network()

    def calculate_values(self):
        self._network.update_cost_factor(self._attribute.array)
        return self._get_local_route_cost()

    @ShortestPathMixin.deduplicate_nodes
    def _get_local_route_cost(self, unique_indices) -> np.ndarray:
        """
        For N _demand_nodes, these have N nearest, with possible duplicates
        We get M unique nearest, calculate MxM routes from all to all
        Then we sample that back to N nearest
        """
        ids = self._demand_nodes.index.ids

        dists = self._network.all_shortest_paths(ids[unique_indices])
        for (x, y) in zip(*np.where(dists == np.inf)):
            self._logger.debug(
                f"Nodes {ids[x]}-{ids[y]} " f"do not have a valid path between them."
            )
        dists[np.where(dists == np.inf)] = 1e14
        return dists


class InducedDemand(LocalEffectsContributor):
    """
    This effect calculator computes the fastest routes for each OD pair.
    If a roads nb_lanes changed, we multiply any demand that routes through that road by some
    factor. Then our multiplier is lanes_m_new/lanes_m_old ** elasticity

    attribute should be the 'transport.layout' UniformAttribute
    """

    _logger: logging.Logger

    _transport_segments: t.Optional[TransportSegmentEntity] = None
    _transport_nodes: t.Optional[PointEntity] = None
    _demand_nodes: t.Optional[PointEntity] = None
    _demand_links: t.Optional[VirtualLinkEntity] = None
    _project: t.Optional[ProjectWrapper] = None
    _cost_attribute: t.Optional[UniformAttribute] = None
    _length_attribute: t.Optional[UniformAttribute] = None

    def setup(
        self,
        state: TrackedState,
        settings: Settings,
        schema: AttributeSchema,
        **_,
    ):
        ds_name = self.info.target_dataset
        entity_name = self.info.target_entity_group
        geom = self.info.target_geometry

        self._project = ProjectWrapper(Path(settings.temp_dir, ds_name))

        if geom != "line":
            raise RuntimeError(f"Local attribute routing has to have line type, not {geom}")

        attr_spec = schema.get_spec(
            (None, "transport.average_time"), default_data_type=DataType(float)
        )
        self._cost_attribute = state.register_attribute(
            dataset_name=ds_name, entity_name=entity_name, spec=attr_spec, flags=INIT
        )

        attr_spec = schema.get_spec((None, "shape.length"), default_data_type=DataType(float))
        self._length_attribute = state.register_attribute(
            dataset_name=ds_name, entity_name=entity_name, spec=attr_spec, flags=INIT
        )

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

    def initialize(self, mapper: LocalMapper):
        self._transport_segments.ensure_ready()
        self._indices = mapper.get_nearest(self._demand_nodes)

        ae_util.fill_project(
            self._project,
            demand_nodes=self._demand_nodes,
            demand_links=self._demand_links,
            transport_nodes=self._transport_nodes,
            transport_segments=self._transport_segments,
        )

        self._project.add_column("cost_field")

    def calculate_values(self):
        self._project.update_column("cost_field", self._cost_attribute.array)
        self._project.build_graph(
            cost_field="cost_field",
            block_centroid_flows=True,
        )
        return self._get_local_route_cost()

    def calculate_contribution(self, new_values, old_values):
        with np.errstate(divide="ignore", invalid="ignore"):
            rv = new_values / old_values
        rv[~np.isfinite(rv)] = 1  # set to 1 in case of division by 0 or NaN
        nonzero = np.nonzero(rv)
        rv[nonzero] = rv[nonzero] ** self._elasticity
        return rv

    def _get_local_route_cost(self) -> np.ndarray:
        """
        For N _demand_nodes, these have N nearest, with possible duplicates
        We get M unique nearest, calculate MxM routes from all to all
        Then we sample that back to N nearest
        """
        ids = self._demand_nodes.index.ids
        segment_index = self._transport_segments.index

        unique_indices = np.unique(self._indices)
        nb_unique_nodes = len(unique_indices)
        summed_values = np.zeros(shape=(nb_unique_nodes, nb_unique_nodes), dtype=np.float64)
        for i, from_idx in enumerate(unique_indices):
            paths = self._project.get_shortest_paths(ids[from_idx], ids[unique_indices])
            for j, (to_idx, path) in enumerate(zip(unique_indices, paths)):
                if i == j:
                    continue
                if path is None:
                    self._logger.debug(
                        f"Nodes {ids[from_idx]}-{ids[to_idx]} "
                        f"do not have a valid path between them."
                    )
                    continue

                roads_indices = segment_index[path.links][1:-1]
                value = np.multiply(
                    self._attribute[roads_indices],
                    self._length_attribute[roads_indices][:, np.newaxis],
                )
                summed_values[i][j] = value.sum()
        # rebuild requested sized matrix of shape=(len(self._closest_idx), len(self._closest_idx))
        orig_idx = self._array_index_in_array(unique_indices, self._indices)
        return summed_values[:, orig_idx][orig_idx, :]

    @staticmethod
    def _array_index_in_array(x: np.ndarray, y: np.ndarray):
        """
        find position of y in x, from https://stackoverflow.com/a/8251757
        """
        index = np.argsort(x)
        sorted_x = x[index]
        sorted_index = np.searchsorted(sorted_x, y)
        return sorted_index

    def close(self):
        if self._project:
            self._project.close()
            self._project = None


class Investment(t.NamedTuple):
    seconds: int
    entity_id: int
    multiplier: float


class InvestmentContributor(LocalContributor):
    def __init__(self, investments: t.Sequence[Investment], demand_node_index: Index):
        self.index = demand_node_index
        self.investments: t.List[Investment] = list(reversed(investments))

    def update_demand(self, matrix: np.ndarray, force_update: bool = False, *, moment: Moment):
        while self.investments and self.investments[-1].seconds <= moment.seconds:
            investment = self.investments.pop()
            idx = self.index[[investment.entity_id]]
            affected_entries = np.zeros_like(matrix, dtype=bool)
            affected_entries[idx] = 1
            affected_entries[:, idx] = 1
            matrix[affected_entries] *= investment.multiplier
        return matrix
