"""Data collection classes for WNTR water network elements.

These dataclasses serve as intermediate representations between Movici entities
and WNTR network objects. They hold the data needed to create WNTR elements
and store simulation results.
"""

from __future__ import annotations

import dataclasses
import typing as t

import numpy as np


@dataclasses.dataclass
class JunctionCollection:
    """Collection of junction data.

    :ivar node_names: WNTR node names
    :ivar elevations: Node elevations (m)
    :ivar base_demands: Base demand values (m³/s)
    :ivar demand_factors: Demand scaling factors (default 1.0)
    :ivar coordinates: Optional (N, 2) array of x, y coordinates
    """

    node_names: t.List[str]
    elevations: np.ndarray
    base_demands: np.ndarray
    demand_factors: t.Optional[np.ndarray] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class TankCollection:
    """Collection of tank data.

    Tank volume is defined either by diameter (cylindrical) or volume_curves (non-cylindrical).

    :ivar node_names: WNTR node names
    :ivar elevations: Tank bottom elevations (m)
    :ivar init_levels: Initial water levels (m)
    :ivar min_levels: Minimum levels for drainage (m), optional
    :ivar max_levels: Maximum levels / overflow threshold (m), optional
    :ivar diameters: Tank diameters for cylindrical tanks (m), optional
    :ivar min_volumes: Minimum volumes for drainage (m³), optional
    :ivar volume_curves: List of volume curve data for non-cylindrical tanks, optional
    :ivar overflows: Boolean array indicating overflow capability, optional
    :ivar coordinates: Optional (N, 2) array of x, y coordinates
    """

    node_names: t.List[str]
    elevations: np.ndarray
    init_levels: np.ndarray
    min_levels: t.Optional[np.ndarray] = None
    max_levels: t.Optional[np.ndarray] = None
    diameters: t.Optional[np.ndarray] = None
    min_volumes: t.Optional[np.ndarray] = None
    volume_curves: t.Optional[t.List[t.Optional[np.ndarray]]] = None
    overflows: t.Optional[np.ndarray] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class ReservoirCollection:
    """Collection of reservoir data.

    :ivar node_names: WNTR node names
    :ivar base_heads: Base head values (m)
    :ivar head_factors: Head scaling factors (default 1.0)
    :ivar coordinates: Optional (N, 2) array of x, y coordinates
    """

    node_names: t.List[str]
    base_heads: np.ndarray
    head_factors: t.Optional[np.ndarray] = None
    coordinates: t.Optional[np.ndarray] = None

    def __len__(self):
        return len(self.node_names)


@dataclasses.dataclass
class PipeCollection:
    """Collection of pipe data.

    :ivar link_names: WNTR link names
    :ivar from_nodes: Start node names
    :ivar to_nodes: End node names
    :ivar lengths: Pipe lengths (m)
    :ivar diameters: Pipe diameters (m)
    :ivar roughnesses: Roughness coefficients
    :ivar minor_losses: Minor loss coefficients, optional
    :ivar check_valves: Boolean array for check valve presence, optional
    :ivar statuses: Initial status values (True=open, False=closed), optional
    :ivar geometries: Line geometries for visualization, optional
    """

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    lengths: np.ndarray
    diameters: np.ndarray
    roughnesses: np.ndarray
    minor_losses: t.Optional[np.ndarray] = None
    check_valves: t.Optional[np.ndarray] = None
    statuses: t.Optional[np.ndarray] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)


@dataclasses.dataclass
class PumpCollection:
    """Collection of pump data.

    Pump type determines which parameters are used:

    - ``"power"``: Uses ``powers`` attribute
    - ``"head"``: Uses ``head_curves`` attribute

    :ivar link_names: WNTR link names
    :ivar from_nodes: Inlet node names
    :ivar to_nodes: Outlet node names
    :ivar pump_types: Pump type strings (``"power"`` or ``"head"``)
    :ivar powers: Power values for power pumps (W), optional
    :ivar head_curves: List of head curve data arrays for head pumps, optional
    :ivar speeds: Relative pump speeds (default 1.0), optional
    :ivar statuses: Initial status values (True=open, False=closed), optional
    :ivar geometries: Line geometries for visualization, optional
    """

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    pump_types: t.List[str]
    powers: t.Optional[np.ndarray] = None
    head_curves: t.Optional[t.List[t.Optional[np.ndarray]]] = None
    speeds: t.Optional[np.ndarray] = None
    statuses: t.Optional[np.ndarray] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)


@dataclasses.dataclass
class ValveCollection:
    """Collection of valve data.

    Valve type determines which setting attribute is used:

    - ``"PRV"``, ``"PSV"``, ``"PBV"``: Uses ``valve_pressures``
    - ``"FCV"``: Uses ``valve_flows``
    - ``"TCV"``: Uses ``valve_loss_coefficients``
    - ``"GPV"``: Uses ``valve_curves``

    :ivar link_names: WNTR link names
    :ivar from_nodes: Inlet node names
    :ivar to_nodes: Outlet node names
    :ivar valve_types: Valve type strings
    :ivar diameters: Valve diameters (m)
    :ivar valve_pressures: Pressure settings for PRV/PSV/PBV (m), optional
    :ivar valve_flows: Flow settings for FCV (m³/s), optional
    :ivar valve_loss_coefficients: Loss coefficients for TCV, optional
    :ivar valve_curves: List of curve data arrays for GPV, optional
    :ivar minor_losses: Minor loss coefficients, optional
    :ivar geometries: Line geometries for visualization, optional
    """

    link_names: t.List[str]
    from_nodes: t.List[str]
    to_nodes: t.List[str]
    valve_types: t.List[str]
    diameters: np.ndarray
    valve_pressures: t.Optional[np.ndarray] = None
    valve_flows: t.Optional[np.ndarray] = None
    valve_loss_coefficients: t.Optional[np.ndarray] = None
    valve_curves: t.Optional[t.List[t.Optional[np.ndarray]]] = None
    minor_losses: t.Optional[np.ndarray] = None
    geometries: t.Optional[t.List] = None

    def __len__(self):
        return len(self.link_names)

    def get_setting(self, index: int) -> float:
        """Get the appropriate setting value for a valve based on its type.

        :param index: Index of the valve in the collection
        :return: Setting value for WNTR
        :raises ValueError: If no setting is available for the valve type
        """
        valve_type = self.valve_types[index].upper()

        if valve_type in ("PRV", "PSV", "PBV"):
            if self.valve_pressures is not None:
                return float(self.valve_pressures[index])
        elif valve_type == "FCV":
            if self.valve_flows is not None:
                return float(self.valve_flows[index])
        elif valve_type == "TCV":
            if self.valve_loss_coefficients is not None:
                return float(self.valve_loss_coefficients[index])
        elif valve_type == "GPV":
            # GPV uses curve, not a scalar setting
            return 0.0

        raise ValueError(f"No setting available for valve type {valve_type} at index {index}")


@dataclasses.dataclass
class SimulationResults:
    """Results from WNTR simulation.

    Contains node and link results mapped by WNTR element names.

    :ivar node_names: List of node names in result order
    :ivar link_names: List of link names in result order
    :ivar node_pressures: Pressure at each node (m)
    :ivar node_heads: Total head at each node (m)
    :ivar node_demands: Delivered demand at each node (m³/s)
    :ivar node_levels: Water level for tanks (m)
    :ivar link_flows: Flow rate through each link (m³/s)
    :ivar link_velocities: Flow velocity in each link (m/s)
    :ivar link_headlosses: Head loss across each link (m)
    :ivar link_statuses: Status of each link (LinkStatus enum values)
    """

    node_names: t.List[str]
    link_names: t.List[str]
    node_pressures: t.Optional[np.ndarray] = None
    node_heads: t.Optional[np.ndarray] = None
    node_demands: t.Optional[np.ndarray] = None
    node_levels: t.Optional[np.ndarray] = None
    link_flows: t.Optional[np.ndarray] = None
    link_velocities: t.Optional[np.ndarray] = None
    link_headlosses: t.Optional[np.ndarray] = None
    link_statuses: t.Optional[np.ndarray] = None

    def get_node_results(self, node_name: str) -> dict:
        """Get all results for a specific node.

        :param node_name: Name of the node
        :return: Dictionary of result values, empty if node not found
        """
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
        if self.node_levels is not None:
            results["level"] = self.node_levels[idx]
        return results

    def get_link_results(self, link_name: str) -> dict:
        """Get all results for a specific link.

        :param link_name: Name of the link
        :return: Dictionary of result values, empty if link not found
        """
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
        return results
