"""Data collection classes for WNTR water network elements"""

from __future__ import annotations

import dataclasses
import typing as t

import numpy as np


@dataclasses.dataclass
class JunctionCollection:
    """Collection of junction data"""

    node_names: t.List[str]
    elevations: np.ndarray
    base_demands: np.ndarray
    demand_patterns: t.Optional[t.List[t.Optional[str]]] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class TankCollection:
    """Collection of tank data"""

    node_names: t.List[str]
    elevations: np.ndarray
    init_levels: np.ndarray
    min_levels: np.ndarray
    max_levels: np.ndarray
    diameters: np.ndarray
    min_volumes: t.Optional[np.ndarray] = None
    volume_curves: t.Optional[t.List[t.Optional[str]]] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class ReservoirCollection:
    """Collection of reservoir data"""

    node_names: t.List[str]
    heads: np.ndarray
    head_patterns: t.Optional[t.List[t.Optional[str]]] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class PipeCollection:
    """Collection of pipe data"""

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    lengths: np.ndarray
    diameters: np.ndarray
    roughnesses: np.ndarray
    minor_losses: t.Optional[np.ndarray] = None
    statuses: t.Optional[t.List[str]] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)


@dataclasses.dataclass
class PumpCollection:
    """Collection of pump data"""

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    pump_types: t.List[str]  # POWER, HEAD
    pump_curves: t.Optional[t.List[t.Optional[str]]] = None
    powers: t.Optional[np.ndarray] = None
    speeds: t.Optional[np.ndarray] = None
    statuses: t.Optional[t.List[str]] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)


@dataclasses.dataclass
class ValveCollection:
    """Collection of valve data"""

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    valve_types: t.List[str]  # PRV, PSV, PBV, FCV, TCV, GPV
    diameters: np.ndarray
    settings: np.ndarray
    minor_losses: t.Optional[np.ndarray] = None
    statuses: t.Optional[t.List[str]] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)


@dataclasses.dataclass
class SimulationResults:
    """Results from WNTR simulation"""

    # Required fields (must come first)
    node_names: t.List[str]
    link_names: t.List[str]

    # Optional node results (junctions, tanks, reservoirs)
    node_pressures: t.Optional[np.ndarray] = None
    node_heads: t.Optional[np.ndarray] = None
    node_demands: t.Optional[np.ndarray] = None
    node_demand_deficits: t.Optional[np.ndarray] = None
    node_levels: t.Optional[np.ndarray] = None  # For tanks only

    # Optional link results (pipes, pumps, valves)
    link_flows: t.Optional[np.ndarray] = None
    link_velocities: t.Optional[np.ndarray] = None
    link_headlosses: t.Optional[np.ndarray] = None
    link_statuses: t.Optional[np.ndarray] = None
    link_powers: t.Optional[np.ndarray] = None  # For pumps only

    def get_node_results(self, node_name: str) -> dict:
        """Get all results for a specific node"""
        try:
            idx = self.node_names.index(node_name)
        except ValueError:
            return {}

        results = {}
        if self.node_pressures is not None:
            results["pressure"] = self.node_pressures[idx]
        if self.node_heads is not None:
            results["head"] = self.node_heads[idx]
        if self.node_demands is not None:
            results["demand"] = self.node_demands[idx]
        if self.node_demand_deficits is not None:
            results["demand_deficit"] = self.node_demand_deficits[idx]
        if self.node_levels is not None:
            results["level"] = self.node_levels[idx]
        return results

    def get_link_results(self, link_name: str) -> dict:
        """Get all results for a specific link"""
        try:
            idx = self.link_names.index(link_name)
        except ValueError:
            return {}

        results = {}
        if self.link_flows is not None:
            results["flow"] = self.link_flows[idx]
        if self.link_velocities is not None:
            results["velocity"] = self.link_velocities[idx]
        if self.link_headlosses is not None:
            results["headloss"] = self.link_headlosses[idx]
        if self.link_statuses is not None:
            results["status"] = self.link_statuses[idx]
        if self.link_powers is not None:
            results["power"] = self.link_powers[idx]
        return results
