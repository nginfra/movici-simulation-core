import typing as t
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt
from aequilibrae import PathResults

from movici_simulation_core.core import TrackedCSRArray
from movici_simulation_core.core.attribute import ensure_csr_data

PointCollection = t.Union[t.List[t.List[float]], t.List[np.ndarray], np.ndarray]
LinestringCollection = t.List[t.List[t.List[float]]]


def _get_numpy_array(
    sequence: t.Optional[npt.ArrayLike], fill_len: int = 0, fill_value=0
) -> np.ndarray:
    if sequence is None:
        return np.full(fill_len, fill_value)
    if not isinstance(sequence, np.ndarray):
        return np.array(sequence)
    return t.cast(np.ndarray, sequence)


@dataclass(init=False)
class NodeCollection:
    ids: np.ndarray
    is_centroids: np.ndarray
    geometries: t.Optional[PointCollection]

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        is_centroids: t.Optional[npt.ArrayLike] = None,
        geometries: t.Optional[PointCollection] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.is_centroids = _get_numpy_array(is_centroids, len(self.ids), fill_value=False)
        self.geometries = np.asarray(geometries, dtype=float) if geometries is not None else None


@dataclass(init=False)
class LinkCollection:
    ids: np.ndarray
    from_nodes: np.ndarray
    to_nodes: np.ndarray
    directions: np.ndarray
    max_speeds: np.ndarray
    capacities: np.ndarray
    geometries: t.Optional[TrackedCSRArray]

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        from_nodes: t.Optional[npt.ArrayLike] = None,
        to_nodes: t.Optional[npt.ArrayLike] = None,
        directions: t.Optional[npt.ArrayLike] = None,
        max_speeds: t.Optional[npt.ArrayLike] = None,
        capacities: t.Optional[npt.ArrayLike] = None,
        geometries: t.Optional[TrackedCSRArray] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.from_nodes = _get_numpy_array(from_nodes, len(self.ids))
        self.to_nodes = _get_numpy_array(to_nodes, len(self.ids))
        self.directions = _get_numpy_array(directions, len(self.ids))
        self.max_speeds = _get_numpy_array(max_speeds, len(self.ids))
        self.capacities = _get_numpy_array(capacities, len(self.ids))
        self.geometries = ensure_csr_data(geometries) if geometries is not None else None


@dataclass(init=False)
class AssignmentResultCollection:
    ids: np.ndarray
    passenger_flow: np.ndarray
    cargo_flow: np.ndarray
    congested_time: np.ndarray
    delay_factor: np.ndarray
    volume_to_capacity: np.ndarray
    passenger_car_unit: np.ndarray

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        passenger_flow: t.Optional[npt.ArrayLike] = None,
        cargo_flow: t.Optional[npt.ArrayLike] = None,
        congested_time: t.Optional[npt.ArrayLike] = None,
        delay_factor: t.Optional[npt.ArrayLike] = None,
        volume_to_capacity: t.Optional[npt.ArrayLike] = None,
        passenger_car_unit: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.passenger_flow = _get_numpy_array(passenger_flow, len(self.ids))
        self.cargo_flow = _get_numpy_array(cargo_flow, len(self.ids))
        self.congested_time = _get_numpy_array(congested_time, len(self.ids))
        self.delay_factor = _get_numpy_array(delay_factor, len(self.ids))
        self.volume_to_capacity = _get_numpy_array(volume_to_capacity, len(self.ids))
        self.passenger_car_unit = _get_numpy_array(passenger_car_unit, len(self.ids))


@dataclass
class GraphPath:
    nodes: np.ndarray
    links: np.ndarray
    path_results: PathResults
