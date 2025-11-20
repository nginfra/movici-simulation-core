from __future__ import annotations

import dataclasses
import typing as t

import numpy as np
import numpy.typing as npt
from numba import njit
from scipy.sparse import csr_matrix
from scipy.sparse.csgraph import shortest_path

from movici_simulation_core.core import EntityGroup, Index, TrackedState

from .entity_groups import LinkEntity, PointEntity, TransportLinkEntity, TransportSegmentEntity


class NetworkEntities(t.TypedDict):
    transport_nodes: PointEntity
    transport_links: TransportSegmentEntity
    virtual_nodes: PointEntity
    virtual_links: LinkEntity


class Network:
    """
    Representation of a transport network containing transport nodes and -links and virtual nodes
    and -links.

    Transport nods and -links represent the real network, and can have a cost factor. Virtual nodes
    and -links are special. They represent virtual entry/exit points to the network. Regular nodes
    cannot be used as entry/exit points.
    If a regular node needs to be used as an entry/exit point,
    it needs to be connected to a virtual node, using a virtual link.
    Virtual nodes can be used as source and target nodes for the the network
    """

    # To prevent flow through (non source/non target) virtual nodes, the virtual links
    # connecting them get a very high outgoing cost factor (MAX_COST_FACTOR). The incoming cost
    # factor is very low (MIN_COST_FACTOR), so that the virtual link doesn't influence the shortest
    # path calculation / total cost factor
    # When doing a shortest path calculation, the outgoing cost factor for the source node are set
    # to MIN_COST_FACTOR
    MAX_COST_FACTOR = np.inf
    MIN_COST_FACTOR = 1e-12

    tl_from_node_id: np.ndarray
    tl_to_node_id: np.ndarray
    tl_mapping: np.ndarray
    tl_count = 0
    vn_ids: np.ndarray
    vl_count = 0

    vl_from_node_id: np.ndarray
    vl_to_node_id: np.ndarray
    vl_directionality: np.ndarray
    vl_cost_factor: np.ndarray

    virtual_node_ids: np.ndarray

    graph: Graph
    source_node_idx = None

    _cost_factor: t.Optional[np.ndarray] = None

    def __init__(
        self,
        transport_nodes: PointEntity,
        transport_links: TransportSegmentEntity,
        virtual_nodes: PointEntity,
        virtual_links: LinkEntity,
        cost_factor: t.Optional[np.ndarray] = None,
    ):
        self.node_index = Index(raise_on_invalid=True)
        self.virtual_node_index = Index(raise_on_invalid=False)

        self.transport_node_ids = transport_nodes.index.ids
        self.node_index.add_ids(self.transport_node_ids)
        self.process_transport_links(transport_links)

        self.virtual_node_ids = virtual_nodes.index.ids
        self.node_index.add_ids(self.virtual_node_ids)
        self.virtual_node_index.add_ids(self.virtual_node_ids)

        self.process_virtual_links(virtual_links)

        self.graph = self._build_graph()
        self.initialize_cost_factor()

        if cost_factor is not None:
            self.update_cost_factor(cost_factor)

        self._cache = {}

    @property
    def cost_factor(self):
        return self._cost_factor

    @cost_factor.setter
    def cost_factor(self, val):
        self.update_cost_factor(val)

    def process_transport_links(self, transport_links: TransportSegmentEntity):
        # Transport links may be bidirectional. The graph we create is unidirectional, so for
        # every bidirectional link we must create a forward- and a reverse direction edge in the
        # graph
        #
        # the layout governes the directionality of the transport link, it is a 4-tuple per link
        # indicating the number of lanes for that link: (forward, reverse, bidirectional, unknown)
        # if no layout is given, we assume a one-directional forward link
        layout = transport_links.layout.array.copy()
        layout[transport_links.layout.is_undefined()] = [1, 0, 0, 0]

        # has_forward and has_reverse contain the indices of links that have a forward and a
        # reverse direction respectively
        has_forward = np.flatnonzero((np.minimum(layout, 1) * [1, 0, 1, 1]).sum(axis=1))
        has_reverse = np.flatnonzero((np.minimum(layout, 1) * [0, 1, 1, 1]).sum(axis=1))
        self.tl_mapping = np.concatenate((has_forward, has_reverse))

        # we obtain the relevant from_node_id and to_node_id values for the links in both
        # directions
        forward_from_node_id = transport_links.from_node_id.array[has_forward]
        forward_to_node_id = transport_links.to_node_id.array[has_forward]
        reverse_from_node_id = transport_links.to_node_id.array[has_reverse]
        reverse_to_node_id = transport_links.from_node_id.array[has_reverse]

        # we now end up with two arrays (from/to node_id) for every directional link where
        # bidirectional links have an entry for each direction
        self.tl_from_node_id = np.concatenate((forward_from_node_id, reverse_from_node_id))
        self.tl_to_node_id = np.concatenate((forward_to_node_id, reverse_to_node_id))
        self.tl_count = len(transport_links)

    def process_virtual_links(self, virtual_links: LinkEntity):
        if self.virtual_node_index is None:
            raise ValueError("Cannot add virtual links without virtual nodes")

        self.vl_from_node_id = virtual_links.from_node_id.array
        self.vl_to_node_id = virtual_links.to_node_id.array
        self.vl_count = len(self.vl_to_node_id)

        # virtual links are always unidirectional and must connect to exaclty one virtual node.
        # vl_directionality is the directionality of the link from the viewpoint of the virtual
        # node that it connects to.
        self.vl_directionality = np.zeros_like(self.vl_from_node_id)

        # when checking the index, it returns -1 if the entry does not exist
        self.vl_directionality[self.virtual_node_index[self.vl_from_node_id] != -1] = 1
        self.vl_directionality[self.virtual_node_index[self.vl_to_node_id] != -1] = -1
        if np.any(self.vl_directionality == 0):
            raise ValueError("Virtual links detected that do not connect to a virtual node")

    def initialize_cost_factor(self):
        # outgoing links are vitual links going out of the virtual node (so from the network's
        # perspective this is for incoming traffic), while incoming links are going towards the
        # virtual link (outgoing traffic from the network's perspective)
        outgoing_links = np.flatnonzero(self.vl_directionality == 1)
        incoming_links = np.flatnonzero(self.vl_directionality == -1)

        # By default, for calculating the shortest path between a source node and multiple target
        # nodes, we set the cost factor for outgoing links to a very high number to prevent
        # transport going into the network from every virtual node. This way we prevent transport
        # through virtual nodes where the virtual node is not a destination.
        #
        # In the ``set_source_node`` method we enable outgoing transport from a single node, ie
        # the source node
        self.vl_cost_factor = np.empty((2 * self.vl_count,), dtype=float)
        self.vl_cost_factor[outgoing_links] = self.MAX_COST_FACTOR
        self.vl_cost_factor[self.vl_count + incoming_links] = self.MAX_COST_FACTOR

        # transport can always flow freely into any virtual node, so that every virtual node
        # can act as a sink for connectivity/shortest path calculations
        self.vl_cost_factor[incoming_links] = self.MIN_COST_FACTOR
        self.vl_cost_factor[self.vl_count + outgoing_links] = self.MIN_COST_FACTOR
        self.update_cost_factor(np.ones((self.tl_count,)))

    def _build_graph(self) -> Graph:
        from_node_id = self.tl_from_node_id
        to_node_id = self.tl_to_node_id
        from_node_id = np.concatenate((from_node_id, self.vl_from_node_id, self.vl_to_node_id))
        to_node_id = np.concatenate((to_node_id, self.vl_to_node_id, self.vl_from_node_id))
        return Graph.from_network_data(
            self.node_index, from_node_id=from_node_id, to_node_id=to_node_id
        )

    def update_cost_factor(self, cost_factor: np.ndarray):
        """Update the cost factor of the network graph with a new cost factor for every transport
        link in the network, not including virtual links. The position of entries in the cost
        factor array is equal to the position of entities in the ``"transport_link"`` array used
        to construct this ``Network``

        :param cost_factor: An `np.ndarray` with the new cost factors
        """
        if len(cost_factor) != self.tl_count:
            raise ValueError(
                f"Length of cost_factor input ({len(cost_factor)} does not match"
                f" length of transport links ({self.tl_count})"
            )
        cost_factor = np.asarray(cost_factor, dtype=float)

        # The links in the graph do not match the transport links directly. In
        # ``process_transport_links`` we have created copies for bidirectional links (the graph
        # requires unidirectional links) and in `process_virtual_links` we have added virtual
        # links to the graph with a set cost factor that we need to account for when updating
        # graph's cost factor
        self.graph.update_cost_factor(
            np.concatenate((cost_factor[self.tl_mapping], self.vl_cost_factor))
        )
        self._cost_factor = cost_factor
        self._cache = {}

    def all_shortest_paths(self, virtual_node_ids: npt.ArrayLike | None = None):
        """Compute the shortest path distance between all virtual nodes"""
        if virtual_node_ids is None:
            virtual_node_ids = self.virtual_node_ids
        node_indices = self.node_index[virtual_node_ids]

        return np.vstack(
            [
                self.get_shortest_path(ident)[0][node_indices]
                for ident in np.asarray(virtual_node_ids)
            ]
        )

    def get_shortest_path(self, source_node_id: int) -> tuple[np.ndarray, np.ndarray]:
        """
        see https://docs.scipy.org/doc/scipy/reference/generated/scipy.sparse.csgraph.shortest_path.html
        for more information.

        :returns a (dist, prev) tuple

        """  # noqa E501
        try:
            return self._cache[int(source_node_id)]
        except KeyError:
            pass

        if self.cost_factor is None:
            raise ValueError("Please first set a cost_factor using Network.update_cost_factor")

        self.set_source_node(source_node_id)

        result = self.graph.shortest_path(self.node_index[source_node_id])

        self._cache[int(source_node_id)] = result
        return result

    def set_source_node(self, source_node_id: int):
        """Set the current source node for a shortest path calculation, this must be a virtual node
        id
        """

        if self.virtual_node_index[source_node_id] == -1:
            raise ValueError(f"Node {source_node_id} is not a valid Virtual Node")

        # first we disable transport from the current source node into the network
        if self.source_node_idx is not None:
            self.graph.set_node_outgoing_cost_factor(self.source_node_idx, self.MAX_COST_FACTOR)

        # then we enable transport from the desired source node into the network
        self.source_node_idx = self.node_index[source_node_id]
        self.graph.set_node_outgoing_cost_factor(self.source_node_idx, self.MIN_COST_FACTOR)

    def all_shortest_paths_sum(self, values, virtual_node_ids=None, no_path_found=-1):
        """Calculate the sum of a quantity that is defined for every link on the shortest path from
        all source (virtual) nodes to all target (virtual) nodes. When the source node and the
        target node are the same, the summed value equals 0

        :param values: an array (or array-like) with the quantity values on transport links that
            are to be summed
        :param no_path_found: A fill value for when no valid shortest path can be found between
            source and target.
        """
        values = self._get_mapped_quantity(values)
        if virtual_node_ids is None:
            virtual_node_ids = self.virtual_node_ids
        node_indices = self.virtual_node_index[virtual_node_ids]

        return np.vstack(
            [
                self.shortest_path_sum(
                    ident,
                    values=values,
                    no_path_found=no_path_found,
                    values_are_mapped=True,
                )[node_indices]
                for ident in virtual_node_ids
            ]
        )

    def shortest_path_sum(self, source_node_id, values, no_path_found=-1, values_are_mapped=False):
        """Calculate the sum of a quantity that is defined for every link on the shortest path from
        a source node to all target (virtual) nodes. When the source node and the target node are
        the same, the summed value equals 0

        :param source_node_id: The entity id of the source (virtual) node
        :param values: See `Network.all_shortest_paths_weighted_average`
        :param no_path_found: See `Network.all_shortest_paths_weighted_average`
        :param values_are_mapped: A boolean indicating whether the value array is in their original
            order or already mapped to the corresponding link index in the graph (default: False).
            This is usually `False`

        """
        if not values_are_mapped:
            values = self._get_mapped_quantity(values)

        _, prev = self.get_shortest_path(source_node_id)
        source_idx = self.node_index[source_node_id]
        return self.graph.shortest_path_sum(
            predecessors=prev,
            source_idx=source_idx,
            target_indices=self.node_index[self.virtual_node_ids],
            values=values,
            no_path_found=no_path_found,
        )

    def all_shortest_paths_weighted_average(
        self, values, virtual_node_ids=None, weights=None, no_path_found=-1
    ):
        """Calculate the weighted average of a quantity that is defined for every link on the
        shortest path from all source (virtual) nodes to all target (virtual) nodes. The average
        is weighted by the cost factor of every link on the shortest path

        :param values: an array (or array-like) with the quantity values on transport links that
            are to be averaged
        :param virtual_node_ids: an array (or array-like) for which virtual nodes to calculate the
            weighted averages
        :param weights: (optional) an array with alternative weights to calculate the weighted
            average. By default the network cost factor is used for both calculating the shortest
            path and as weights for the weighted average. Supplying this attributes makes it
            possible to calculate the shortest path by cost factor (eg. travel time) and the
            weighted average by a different attribute (eg. length). This array should have the same
            length as the cost_factor array
        :param no_path_found: A fill value for when no valid shortest path can be found between
            source and target. This is also used for when the source and target node are the same

        """
        values = self._get_mapped_quantity(values)
        if weights is not None:
            weights = self._get_mapped_quantity(weights)

        if virtual_node_ids is None:
            virtual_node_ids = self.virtual_node_ids
        node_indices = self.virtual_node_index[virtual_node_ids]

        return np.vstack(
            [
                self.shortest_path_weighted_average(
                    ident,
                    values=values,
                    weights=weights,
                    no_path_found=no_path_found,
                    values_are_mapped=True,
                )[node_indices]
                for ident in virtual_node_ids
            ]
        )

    def shortest_path_weighted_average(
        self, source_node_id, values, weights=None, no_path_found=-1, values_are_mapped=False
    ):
        """Calculate the weighted average of a quantity that is defined for every link on the
        shortest path from a source node to all target (virtual) nodes. The average is weighted by
        the cost factor of every link on the shortest path

        :param source_node_id: The entity id of the source (virtual) node
        :param values: See ``Network.all_shortest_paths_weighted_average``
        :param weights: See ``Network.all_shortest_paths_weighted_average``
        :param no_path_found: See ``Network.all_shortest_paths_weighted_average``
        :param values_are_mapped: A boolean indicating whether the value array is in their original
            order or already mapped to the corresponding link index in the graph (default: False).
            This is usually ``False``

        """
        if not values_are_mapped:
            values = self._get_mapped_quantity(values)
            if weights is not None:
                weights = self._get_mapped_quantity(weights)
        _, prev = self.get_shortest_path(source_node_id)
        source_idx = self.node_index[source_node_id]
        return self.graph.shortest_path_weighted_average(
            predecessors=prev,
            source_idx=source_idx,
            target_indices=self.node_index[self.virtual_node_ids],
            weights=weights,
            values=values,
            no_path_found=no_path_found,
        )

    def _get_mapped_quantity(self, values):
        return np.concatenate(
            (
                np.asarray(values, dtype=float)[self.tl_mapping],
                np.zeros_like(self.vl_cost_factor, dtype=float),
            )
        )[self.graph.cost_factor_indices]

    @classmethod
    def register_required_attributes(
        cls,
        state: TrackedState,
        dataset_name: str,
        transport_segments_name: str,
        entities: t.Optional[t.Dict[str, t.Union[EntityGroup, t.Type[EntityGroup]]]] = None,
    ) -> NetworkEntities:
        """Register the required entity groups for setting up a ``Network`` to the ``state``.

        By default it will register ``PointEntity`` for transport nodes as
        ``"transport_node_entities"`` and for virtual nodes as ``"virtual_node_entities"``,
        ``LinkEntity`` for virtual links as ``"virtual_link_entities"`` and ``TransportLinkEntity``
        for transport links/segments. Transport links do not have a default name and this name
        must be given as the ``transport_segments_name`` argument. To override defaults, you can
        supply the ``entities`` argument

        :param state: The ``TrackedState`` object to register the entity groups to
        :param dataset_name: The dataset name for the entity groups
        :param transport_segment_name: The name of the transport segment entities. Eg. for a road
            network this may be ``"road_segment_entities"``
        :param entities: An optional dictionary to override the default registered entity groups.
            keys in this dictionary may be ``"transport_nodes"``, ``"transport_links"``,
            ``"virtual_nodes"`` and ``"virtual_links"`` and values must be either subclasses of
            ``Entity`` with the appropriate attributes instances of thereof, ie. a partial of
            ``NetworkEntities``
        :return: A full ``NetworkEntities`` dictionary that can be used for the initialization of
        a ``Network``
        """
        defaults = {
            "transport_nodes": (PointEntity, "transport_node_entities"),
            "transport_links": (TransportLinkEntity, transport_segments_name),
            "virtual_nodes": (PointEntity, "virtual_node_entities"),
            "virtual_links": (LinkEntity, "virtual_link_entities"),
        }
        entities = entities or {}
        rv = {}
        for k, (entity_group, name) in defaults.items():
            entity_group = entities.get(k, entity_group)
            if isinstance(entity_group, type):
                entity_group = entity_group(name)
            rv[k] = state.register_entity_group(dataset_name, entity_group)
        return t.cast(NetworkEntities, rv)


@dataclasses.dataclass
class Graph:
    """Internal class that acts as an interface to ``scipy.sparse.csr_matrix`` and
    ``scipy.sparse.csgraph.shortest_path`` to be used by a ``Network``. The arguments ``indices``
    and ``indptr`` have the same meaining as in ``scipy.sparse.csr_matrix`.

    The graph is initially setup with a cost factor of 1, but a cost factor can be set using
    the ``update_cost_factor`` method.

    Rather than instantiating this class directly, it is recommended to use the
    ``Graph.from_network_data`` constructor that will calculate the correct sparse matrix from
    ``from_node_id`` and ``to_node_id`` data and a node ``Index``

    :param indices: sparse matrix column indices array (see ``scipy.sparse.csr_matrix``)
    :param indptr: sparse matrix index pointer array (see ``scipy.sparse.csr_matrix``)
    :param cost_factor_indices: a mapping between "TransportNode oriented cost factor" and their
        position in the sparse matrix
    """

    indices: np.ndarray
    indptr: np.ndarray
    cost_factor_indices: np.ndarray
    node_count: int = dataclasses.field(init=False)
    cost_factor: np.ndarray = dataclasses.field(init=False)

    @staticmethod
    def from_network_data(node_idx: Index, from_node_id, to_node_id):
        """Create a ``Graph`` from Network data.

        :param node_idx: the ``Index with all node ids
        :param from_node_id: an array with source node id for every edge/link
        :param to_node_id: an array with target node id for every edge/link
        :return: a ``Graph`` representing the network
        """
        indptr, indices, edge_indices = _build_graph(node_idx.ids, from_node_id, to_node_id)
        return Graph(node_idx[indices], indptr, edge_indices)

    def __post_init__(self):
        self.node_count = len(self.indptr) - 1
        self.cost_factor = np.ones_like(self.cost_factor_indices, dtype=np.float64)

    def update_cost_factor(self, cost_factor: np.ndarray):
        """Set the cost factor of the graph.

        :param cost_factor: a ``np.ndarray`` containing the cost factor of the links as they were
            provided to the ``Graph.from_network_data`` constructor.
        """
        self.cost_factor = cost_factor[self.cost_factor_indices]

    def set_node_outgoing_cost_factor(self, node_idx, value):
        """Set the outgoing cost factor for all edges of a single node. Useful for
        enabling/disabling a virtual node by setting a very low or high value"""
        begin, end = self.indptr[node_idx : node_idx + 2]
        self.cost_factor[begin:end] = value

    def shortest_path(self, indices: int | np.typing.NDArray[np.int_]):
        matrix = csr_matrix((self.cost_factor, self.indices, self.indptr))
        return shortest_path(
            matrix,
            directed=True,
            return_predecessors=True,
            indices=indices,
        )

    def shortest_path_sum(
        self, predecessors, source_idx, target_indices, values, no_path_found=-1
    ):
        return _shortest_path_sum(
            predecessors=predecessors,
            source_idx=source_idx,
            target_indices=target_indices,
            indptr=self.indptr,
            indices=self.indices,
            cost_factor=self.cost_factor,
            values=values,
            no_path_found=no_path_found,
        )

    def shortest_path_weighted_average(
        self, predecessors, source_idx, target_indices, values, weights=None, no_path_found=-1
    ):
        return _shortest_path_weighted_average(
            predecessors=predecessors,
            source_idx=source_idx,
            target_indices=target_indices,
            indptr=self.indptr,
            indices=self.indices,
            cost_factor=self.cost_factor,
            weights=weights if weights is not None else self.cost_factor,
            values=values,
            no_path_found=no_path_found,
        )

    def get_cost(self, source_idx, target_idx):
        """Helper method to retrieve the cost from a source to a target. Useful for testing.

        :param source_idx: The index of the source node in the graph
        :param target_idx: The index of the target node in the graph
        """
        min_i = self.indptr[source_idx]
        max_i = self.indptr[source_idx + 1]
        for i in range(min_i, max_i):
            candidate = self.indices[i]
            if candidate == target_idx:
                return self.cost_factor[i]
            if candidate > target_idx:
                break
        return -1

    def get_neighbours(self, source_index):
        return self.indices[self.indptr[source_index] : self.indptr[source_index + 1]]


@njit(cache=True)
def _build_graph(nodes_ids, from_node_id, to_node_id):
    indices_length = len(from_node_id)
    if len(to_node_id) != indices_length:
        raise TypeError("lengths of from_node_id must match to_node_id")
    indptr_length = len(nodes_ids) + 1
    indptr = np.empty((indptr_length,), dtype=np.int64)
    indices = np.empty((indices_length,), dtype=np.int64)
    edge_indices = np.empty_like(indices)

    indptr[0] = 0
    for idx, source in enumerate(nodes_ids):
        edges = np.flatnonzero(from_node_id == source)

        targets = to_node_id[edges]
        n_targets = len(targets)
        sort_indices = np.argsort(targets)

        begin, end = indptr[idx], indptr[idx] + n_targets
        indices[begin:end] = targets[sort_indices]
        edge_indices[begin:end] = edges[sort_indices]

        indptr[idx + 1] = end

    return indptr, indices, edge_indices


@njit(cache=True)
def _shortest_path_weighted_average(
    predecessors,
    source_idx,
    target_indices,
    indptr,
    indices,
    cost_factor,
    weights,
    values,
    no_path_found=-1,
):
    """calculate the weighted average of a quantity along the shortest path"""
    result = np.zeros_like(target_indices, dtype=np.float64)

    for result_idx, target in enumerate(target_indices):
        # the predecessors array contains for every target node, what is the next node that
        # needs to be taken to travel to the source node over the shortest path. We'll travel along
        # the path back from the target towards the source until we've reached the source.

        # we start at the target idx
        curr = target

        total_weight = 0.0
        error = False

        while curr != source_idx:
            # We need to examine the first link from the current node towards the source node
            # ``prev`` is the next node on our path to the source node, so the link to examine
            # is prev->curr
            prev = predecessors[curr]

            # A negative value in predecessors means that there is no connected route from the
            # target towards the source
            if prev < 0:
                error = True
                break

            # get the index of the link in the csr matrix. The link for node a->b exists in the
            # full-form matrix at position [a][b]. In csr form, we lookup the index in the csr-data
            # array.
            val_idx = shortest_link_index(indptr, indices, prev, curr, cost_factor)

            if val_idx == -1:  # link not found
                error = True
                break

            # keep a running total of the weighted quantity before later dividing by the total
            # weight of the route
            total_weight += weights[val_idx]
            result[result_idx] += weights[val_idx] * values[val_idx]

            # move to the next (previous) node
            curr = prev

        # If the total weight is 0, it means that the source node and target node are the same,
        # or there is another reason why they have a zero-weighting. In either case
        # we cannot calculate the weighted average
        if total_weight == 0.0:
            error = True

        if error:
            result[result_idx] = no_path_found
        else:
            result[result_idx] /= total_weight

    return result


@njit(cache=True)
def _shortest_path_sum(
    predecessors,
    source_idx,
    target_indices,
    indptr,
    indices,
    cost_factor,
    values,
    no_path_found=-1,
):
    result = np.zeros_like(target_indices, dtype=np.float64)

    for result_idx, target in enumerate(target_indices):
        # the predecessors array contains for every target node, what is the next node that
        # needs to be taken to travel to the source node over the shortest path. We'll travel along
        # the path back from the target towards the source until we've reached the source.

        # we start at the target idx
        curr = target

        while curr != source_idx:
            # We need to examine the first link from the current node towards the source node
            # ``prev`` is the next node on our path to the source node, so the link to examine
            # is prev->curr
            prev = predecessors[curr]

            # A negative value in predecessors means that there is no connected route from the
            # target towards the source
            if prev < 0:
                result[result_idx] = no_path_found
                break

            val_idx = shortest_link_index(indptr, indices, prev, curr, cost_factor)
            if val_idx == -1:  # link not found
                result[result_idx] = no_path_found
                break

            # keep a running total
            result[result_idx] += values[val_idx]

            # move on to the next (previous) node
            curr = prev

    return result


@njit(cache=True)
def shortest_link_index(indptr, indices, from_idx, to_idx, cost_factor):
    """A graph may have multiple links between two nodes that each have a cost. This function
    finds the index of the link with the lowest cost between the from_idx and the to_idx node

    in case there are no links connecting the nodes, this function return ``-1``
    """
    all_links = link_indices(indptr, indices, from_idx, to_idx)
    if len(all_links) == 0:
        return -1
    costs = cost_factor[all_links]
    return all_links[np.argmin(costs)]


@njit(cache=True)
def link_indices(indptr, indices, from_idx, to_idx):
    """return the indices of all links in a csr sparse network going from from_idx to to_idx"""

    min_i = indptr[from_idx]
    max_i = indptr[from_idx + 1]

    begin_idx = candidate_idx = np.searchsorted(indices[min_i:max_i], to_idx) + min_i
    while candidate_idx < max_i and indices[candidate_idx] == to_idx:
        candidate_idx += 1
    return np.arange(begin_idx, candidate_idx)
