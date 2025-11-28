"""Data collections for Power Grid Model components.

These dataclasses serve as intermediate containers between Movici entity data
and power-grid-model input/output arrays. They provide a clean interface
for data transformation and validation.
"""

from __future__ import annotations

import typing as t
from dataclasses import dataclass

import numpy as np
import numpy.typing as npt


def _get_array(
    value: t.Optional[npt.ArrayLike],
    length: int = 0,
    fill_value: t.Any = 0,
    dtype: npt.DTypeLike = np.float64,
) -> np.ndarray:
    """Convert value to numpy array with optional fill.

    :param value: Input value to convert (array-like or None).
    :param length: Length for fill array if value is None.
    :param fill_value: Value to fill array with if value is None.
    :param dtype: Data type for the output array.
    :returns: Numpy array.
    """
    if value is None:
        return np.full(length, fill_value, dtype=dtype)
    if not isinstance(value, np.ndarray):
        return np.asarray(value, dtype=dtype)
    return value


# =============================================================================
# Input Collections (Movici -> PGM)
# =============================================================================


@dataclass(init=False)
class NodeCollection:
    """Collection of electrical nodes (buses)."""

    ids: np.ndarray
    u_rated: np.ndarray  # Rated voltage (V)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        u_rated: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        self.u_rated = _get_array(u_rated, len(self.ids))

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class LineCollection:
    """Collection of electrical lines (branches)."""

    ids: np.ndarray
    from_node: np.ndarray
    to_node: np.ndarray
    from_status: np.ndarray
    to_status: np.ndarray
    r1: np.ndarray  # Resistance (Ω)
    x1: np.ndarray  # Reactance (Ω)
    c1: np.ndarray  # Capacitance (F)
    tan1: np.ndarray  # Loss tangent
    i_n: np.ndarray  # Rated current (A), optional

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        from_node: t.Optional[npt.ArrayLike] = None,
        to_node: t.Optional[npt.ArrayLike] = None,
        from_status: t.Optional[npt.ArrayLike] = None,
        to_status: t.Optional[npt.ArrayLike] = None,
        r1: t.Optional[npt.ArrayLike] = None,
        x1: t.Optional[npt.ArrayLike] = None,
        c1: t.Optional[npt.ArrayLike] = None,
        tan1: t.Optional[npt.ArrayLike] = None,
        i_n: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.from_node = _get_array(from_node, n, dtype=np.int32)
        self.to_node = _get_array(to_node, n, dtype=np.int32)
        self.from_status = _get_array(from_status, n, fill_value=1, dtype=np.int8)
        self.to_status = _get_array(to_status, n, fill_value=1, dtype=np.int8)
        self.r1 = _get_array(r1, n)
        self.x1 = _get_array(x1, n)
        self.c1 = _get_array(c1, n)
        self.tan1 = _get_array(tan1, n)
        self.i_n = _get_array(i_n, n, fill_value=np.inf)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class TransformerCollection:
    """Collection of two-winding transformers."""

    ids: np.ndarray
    from_node: np.ndarray
    to_node: np.ndarray
    from_status: np.ndarray
    to_status: np.ndarray
    u1: np.ndarray  # Primary voltage (V)
    u2: np.ndarray  # Secondary voltage (V)
    sn: np.ndarray  # Rated power (VA)
    uk: np.ndarray  # Short-circuit voltage (p.u.)
    pk: np.ndarray  # Copper loss (W)
    i0: np.ndarray  # No-load current (p.u.)
    p0: np.ndarray  # No-load loss (W)
    winding_from: np.ndarray  # Winding type (0=wye, 1=wye_n, 2=delta)
    winding_to: np.ndarray
    clock: np.ndarray  # Clock number (0-12)
    tap_side: np.ndarray  # Tap side (0=from, 1=to)
    tap_pos: np.ndarray  # Tap position
    tap_min: np.ndarray
    tap_max: np.ndarray
    tap_nom: np.ndarray
    tap_size: np.ndarray  # Tap size (V)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        from_node: t.Optional[npt.ArrayLike] = None,
        to_node: t.Optional[npt.ArrayLike] = None,
        from_status: t.Optional[npt.ArrayLike] = None,
        to_status: t.Optional[npt.ArrayLike] = None,
        u1: t.Optional[npt.ArrayLike] = None,
        u2: t.Optional[npt.ArrayLike] = None,
        sn: t.Optional[npt.ArrayLike] = None,
        uk: t.Optional[npt.ArrayLike] = None,
        pk: t.Optional[npt.ArrayLike] = None,
        i0: t.Optional[npt.ArrayLike] = None,
        p0: t.Optional[npt.ArrayLike] = None,
        winding_from: t.Optional[npt.ArrayLike] = None,
        winding_to: t.Optional[npt.ArrayLike] = None,
        clock: t.Optional[npt.ArrayLike] = None,
        tap_side: t.Optional[npt.ArrayLike] = None,
        tap_pos: t.Optional[npt.ArrayLike] = None,
        tap_min: t.Optional[npt.ArrayLike] = None,
        tap_max: t.Optional[npt.ArrayLike] = None,
        tap_nom: t.Optional[npt.ArrayLike] = None,
        tap_size: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.from_node = _get_array(from_node, n, dtype=np.int32)
        self.to_node = _get_array(to_node, n, dtype=np.int32)
        self.from_status = _get_array(from_status, n, fill_value=1, dtype=np.int8)
        self.to_status = _get_array(to_status, n, fill_value=1, dtype=np.int8)
        self.u1 = _get_array(u1, n)
        self.u2 = _get_array(u2, n)
        self.sn = _get_array(sn, n)
        self.uk = _get_array(uk, n)
        self.pk = _get_array(pk, n)
        self.i0 = _get_array(i0, n)
        self.p0 = _get_array(p0, n)
        self.winding_from = _get_array(winding_from, n, fill_value=1, dtype=np.int8)  # wye_n
        self.winding_to = _get_array(winding_to, n, fill_value=1, dtype=np.int8)  # wye_n
        self.clock = _get_array(clock, n, fill_value=0, dtype=np.int8)
        self.tap_side = _get_array(tap_side, n, fill_value=0, dtype=np.int8)
        self.tap_pos = _get_array(tap_pos, n, fill_value=0, dtype=np.int8)
        self.tap_min = _get_array(tap_min, n, fill_value=0, dtype=np.int8)
        self.tap_max = _get_array(tap_max, n, fill_value=0, dtype=np.int8)
        self.tap_nom = _get_array(tap_nom, n, fill_value=0, dtype=np.int8)
        self.tap_size = _get_array(tap_size, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class LoadCollection:
    """Collection of symmetric loads."""

    ids: np.ndarray
    node: np.ndarray  # Connected node ID
    status: np.ndarray
    type: np.ndarray  # Load type (0=const_power, 1=const_impedance, 2=const_current)
    p_specified: np.ndarray  # Active power (W)
    q_specified: np.ndarray  # Reactive power (VAr)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        node: t.Optional[npt.ArrayLike] = None,
        status: t.Optional[npt.ArrayLike] = None,
        type: t.Optional[npt.ArrayLike] = None,
        p_specified: t.Optional[npt.ArrayLike] = None,
        q_specified: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.node = _get_array(node, n, dtype=np.int32)
        self.status = _get_array(status, n, fill_value=1, dtype=np.int8)
        self.type = _get_array(type, n, fill_value=0, dtype=np.int8)  # const_power
        self.p_specified = _get_array(p_specified, n)
        self.q_specified = _get_array(q_specified, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class GeneratorCollection:
    """Collection of symmetric generators."""

    ids: np.ndarray
    node: np.ndarray
    status: np.ndarray
    type: np.ndarray
    p_specified: np.ndarray  # Active power (W) - positive = generation
    q_specified: np.ndarray  # Reactive power (VAr)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        node: t.Optional[npt.ArrayLike] = None,
        status: t.Optional[npt.ArrayLike] = None,
        type: t.Optional[npt.ArrayLike] = None,
        p_specified: t.Optional[npt.ArrayLike] = None,
        q_specified: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.node = _get_array(node, n, dtype=np.int32)
        self.status = _get_array(status, n, fill_value=1, dtype=np.int8)
        self.type = _get_array(type, n, fill_value=0, dtype=np.int8)
        self.p_specified = _get_array(p_specified, n)
        self.q_specified = _get_array(q_specified, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class SourceCollection:
    """Collection of external grid sources (slack buses)."""

    ids: np.ndarray
    node: np.ndarray
    status: np.ndarray
    u_ref: np.ndarray  # Reference voltage (p.u.)
    u_ref_angle: np.ndarray  # Reference angle (rad)
    sk: np.ndarray  # Short-circuit power (VA)
    rx_ratio: np.ndarray  # R/X ratio

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        node: t.Optional[npt.ArrayLike] = None,
        status: t.Optional[npt.ArrayLike] = None,
        u_ref: t.Optional[npt.ArrayLike] = None,
        u_ref_angle: t.Optional[npt.ArrayLike] = None,
        sk: t.Optional[npt.ArrayLike] = None,
        rx_ratio: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.node = _get_array(node, n, dtype=np.int32)
        self.status = _get_array(status, n, fill_value=1, dtype=np.int8)
        self.u_ref = _get_array(u_ref, n, fill_value=1.0)  # 1.0 p.u. default
        self.u_ref_angle = _get_array(u_ref_angle, n, fill_value=0.0)
        self.sk = _get_array(sk, n, fill_value=1e10)  # Very large default
        self.rx_ratio = _get_array(rx_ratio, n, fill_value=0.1)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class ShuntCollection:
    """Collection of shunt elements."""

    ids: np.ndarray
    node: np.ndarray
    status: np.ndarray
    g1: np.ndarray  # Conductance (S)
    b1: np.ndarray  # Susceptance (S)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        node: t.Optional[npt.ArrayLike] = None,
        status: t.Optional[npt.ArrayLike] = None,
        g1: t.Optional[npt.ArrayLike] = None,
        b1: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.node = _get_array(node, n, dtype=np.int32)
        self.status = _get_array(status, n, fill_value=1, dtype=np.int8)
        self.g1 = _get_array(g1, n)
        self.b1 = _get_array(b1, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class VoltageSensorCollection:
    """Collection of voltage sensors for state estimation."""

    ids: np.ndarray
    measured_object: np.ndarray  # Node ID being measured
    u_measured: np.ndarray  # Measured voltage (V)
    u_sigma: np.ndarray  # Measurement uncertainty (V)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        measured_object: t.Optional[npt.ArrayLike] = None,
        u_measured: t.Optional[npt.ArrayLike] = None,
        u_sigma: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.measured_object = _get_array(measured_object, n, dtype=np.int32)
        self.u_measured = _get_array(u_measured, n)
        self.u_sigma = _get_array(u_sigma, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class PowerSensorCollection:
    """Collection of power sensors for state estimation."""

    ids: np.ndarray
    measured_object: np.ndarray  # Object ID being measured
    measured_terminal_type: np.ndarray  # Terminal type enum
    p_measured: np.ndarray  # Measured active power (W)
    q_measured: np.ndarray  # Measured reactive power (VAr)
    power_sigma: np.ndarray  # Measurement uncertainty (VA)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        measured_object: t.Optional[npt.ArrayLike] = None,
        measured_terminal_type: t.Optional[npt.ArrayLike] = None,
        p_measured: t.Optional[npt.ArrayLike] = None,
        q_measured: t.Optional[npt.ArrayLike] = None,
        power_sigma: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.measured_object = _get_array(measured_object, n, dtype=np.int32)
        self.measured_terminal_type = _get_array(measured_terminal_type, n, dtype=np.int8)
        self.p_measured = _get_array(p_measured, n)
        self.q_measured = _get_array(q_measured, n)
        self.power_sigma = _get_array(power_sigma, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class FaultCollection:
    """Collection of fault definitions for short-circuit analysis."""

    ids: np.ndarray
    status: np.ndarray
    fault_type: np.ndarray  # Fault type enum
    fault_phase: np.ndarray  # Fault phase enum
    fault_object: np.ndarray  # Object ID where fault occurs
    r_f: np.ndarray  # Fault resistance (Ω)
    x_f: np.ndarray  # Fault reactance (Ω)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        status: t.Optional[npt.ArrayLike] = None,
        fault_type: t.Optional[npt.ArrayLike] = None,
        fault_phase: t.Optional[npt.ArrayLike] = None,
        fault_object: t.Optional[npt.ArrayLike] = None,
        r_f: t.Optional[npt.ArrayLike] = None,
        x_f: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.status = _get_array(status, n, fill_value=1, dtype=np.int8)
        self.fault_type = _get_array(fault_type, n, fill_value=0, dtype=np.int8)  # three_phase
        self.fault_phase = _get_array(fault_phase, n, fill_value=0, dtype=np.int8)
        self.fault_object = _get_array(fault_object, n, dtype=np.int32)
        self.r_f = _get_array(r_f, n)
        self.x_f = _get_array(x_f, n)

    def __len__(self) -> int:
        return len(self.ids)


# =============================================================================
# Output Collections (PGM -> Movici)
# =============================================================================


@dataclass(init=False)
class NodeResult:
    """Power flow results for nodes."""

    ids: np.ndarray
    u_pu: np.ndarray  # Voltage magnitude (p.u.)
    u_angle: np.ndarray  # Voltage angle (rad)
    u: np.ndarray  # Voltage magnitude (V)
    p: np.ndarray  # Active power injection (W)
    q: np.ndarray  # Reactive power injection (VAr)

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        u_pu: t.Optional[npt.ArrayLike] = None,
        u_angle: t.Optional[npt.ArrayLike] = None,
        u: t.Optional[npt.ArrayLike] = None,
        p: t.Optional[npt.ArrayLike] = None,
        q: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.u_pu = _get_array(u_pu, n)
        self.u_angle = _get_array(u_angle, n)
        self.u = _get_array(u, n)
        self.p = _get_array(p, n)
        self.q = _get_array(q, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class BranchResult:
    """Power flow results for branches (lines/transformers)."""

    ids: np.ndarray
    p_from: np.ndarray  # Active power at from-side (W)
    q_from: np.ndarray  # Reactive power at from-side (VAr)
    i_from: np.ndarray  # Current at from-side (A)
    s_from: np.ndarray  # Apparent power at from-side (VA)
    p_to: np.ndarray  # Active power at to-side (W)
    q_to: np.ndarray  # Reactive power at to-side (VAr)
    i_to: np.ndarray  # Current at to-side (A)
    s_to: np.ndarray  # Apparent power at to-side (VA)
    loading: np.ndarray  # Loading ratio

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        p_from: t.Optional[npt.ArrayLike] = None,
        q_from: t.Optional[npt.ArrayLike] = None,
        i_from: t.Optional[npt.ArrayLike] = None,
        s_from: t.Optional[npt.ArrayLike] = None,
        p_to: t.Optional[npt.ArrayLike] = None,
        q_to: t.Optional[npt.ArrayLike] = None,
        i_to: t.Optional[npt.ArrayLike] = None,
        s_to: t.Optional[npt.ArrayLike] = None,
        loading: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.p_from = _get_array(p_from, n)
        self.q_from = _get_array(q_from, n)
        self.i_from = _get_array(i_from, n)
        self.s_from = _get_array(s_from, n)
        self.p_to = _get_array(p_to, n)
        self.q_to = _get_array(q_to, n)
        self.i_to = _get_array(i_to, n)
        self.s_to = _get_array(s_to, n)
        self.loading = _get_array(loading, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass(init=False)
class ApplianceResult:
    """Power flow results for appliances (loads/generators)."""

    ids: np.ndarray
    p: np.ndarray  # Active power (W)
    q: np.ndarray  # Reactive power (VAr)
    i: np.ndarray  # Current (A)
    s: np.ndarray  # Apparent power (VA)
    pf: np.ndarray  # Power factor

    def __init__(
        self,
        ids: t.Optional[npt.ArrayLike] = None,
        p: t.Optional[npt.ArrayLike] = None,
        q: t.Optional[npt.ArrayLike] = None,
        i: t.Optional[npt.ArrayLike] = None,
        s: t.Optional[npt.ArrayLike] = None,
        pf: t.Optional[npt.ArrayLike] = None,
    ):
        self.ids = _get_array(ids, dtype=np.int32)
        n = len(self.ids)
        self.p = _get_array(p, n)
        self.q = _get_array(q, n)
        self.i = _get_array(i, n)
        self.s = _get_array(s, n)
        self.pf = _get_array(pf, n)

    def __len__(self) -> int:
        return len(self.ids)


@dataclass
class PowerFlowResult:
    """Complete power flow calculation result."""

    nodes: NodeResult
    lines: t.Optional[BranchResult] = None
    transformers: t.Optional[BranchResult] = None
    loads: t.Optional[ApplianceResult] = None
    generators: t.Optional[ApplianceResult] = None
    sources: t.Optional[ApplianceResult] = None


@dataclass
class ShortCircuitResult:
    """Short circuit calculation result."""

    fault_ids: np.ndarray
    i_f: np.ndarray  # Fault current (A)
    i_f_angle: np.ndarray  # Fault current angle (rad)
