from dataclasses import dataclass
from typing import Optional, cast, List, Sequence

import numpy as np

PointCollection = List[List[float]]
LinestringCollection = List[List[List[float]]]


def _get_numpy_array(sequence: Optional[Sequence], fill_len: int = 0) -> np.ndarray:
    if sequence is None:
        return np.zeros(fill_len)
    elif not isinstance(sequence, np.ndarray):
        return np.array(sequence)
    else:
        return cast(np.ndarray, sequence)


@dataclass(init=False)
class NodeCollection:
    ids: np.ndarray
    is_centroids: np.ndarray
    geometries: Optional[PointCollection]

    def __init__(
        self,
        ids: Optional[Sequence] = None,
        is_centroids: Optional[Sequence] = None,
        geometries: Optional[PointCollection] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.is_centroids = _get_numpy_array(is_centroids, len(self.ids))
        self.geometries = geometries


@dataclass(init=False)
class LinkCollection:
    ids: np.ndarray
    from_nodes: np.ndarray
    to_nodes: np.ndarray
    directions: np.ndarray
    max_speeds: np.ndarray
    capacities: np.ndarray
    geometries: Optional[LinestringCollection]

    def __init__(
        self,
        ids: Optional[Sequence] = None,
        from_nodes: Optional[Sequence] = None,
        to_nodes: Optional[Sequence] = None,
        directions: Optional[Sequence] = None,
        max_speeds: Optional[Sequence] = None,
        capacities: Optional[Sequence] = None,
        geometries: Optional[LinestringCollection] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.from_nodes = _get_numpy_array(from_nodes, len(self.ids))
        self.to_nodes = _get_numpy_array(to_nodes, len(self.ids))
        self.directions = _get_numpy_array(directions, len(self.ids))
        self.max_speeds = _get_numpy_array(max_speeds, len(self.ids))
        self.capacities = _get_numpy_array(capacities, len(self.ids))
        self.geometries = geometries


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
        ids: Optional[Sequence] = None,
        passenger_flow: Optional[Sequence] = None,
        cargo_flow: Optional[Sequence] = None,
        congested_time: Optional[Sequence] = None,
        delay_factor: Optional[Sequence] = None,
        volume_to_capacity: Optional[Sequence] = None,
        passenger_car_unit: Optional[Sequence] = None,
    ):
        self.ids = _get_numpy_array(ids)
        self.passenger_flow = _get_numpy_array(passenger_flow, len(self.ids))
        self.cargo_flow = _get_numpy_array(cargo_flow, len(self.ids))
        self.congested_time = _get_numpy_array(congested_time, len(self.ids))
        self.delay_factor = _get_numpy_array(delay_factor, len(self.ids))
        self.volume_to_capacity = _get_numpy_array(volume_to_capacity, len(self.ids))
        self.passenger_car_unit = _get_numpy_array(passenger_car_unit, len(self.ids))
