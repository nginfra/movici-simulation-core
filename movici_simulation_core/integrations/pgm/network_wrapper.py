"""Power-grid-model integration with processor-based architecture.

Each electrical entity type has a dedicated processor that handles:
- Building PGM input arrays from Movici entity group data
- Building sparse update arrays for changed elements
- Writing PGM results back to entity group attributes

The PowerGridWrapper orchestrates processors and manages the PGM model.
"""

from __future__ import annotations

import typing as t
from enum import IntEnum

import numpy as np
import power_grid_model as pgm

from movici_simulation_core.core.entity_group import EntityGroup

from .id_generator import ComponentIdManager

if t.TYPE_CHECKING:
    from movici_simulation_core.models.power_grid_calculation.dataset import PowerGridNetwork

T = t.TypeVar("T", bound=EntityGroup)


# =========================================================================
# Enums
# =========================================================================


class CalculationType(IntEnum):
    POWER_FLOW = 0
    STATE_ESTIMATION = 1
    SHORT_CIRCUIT = 2


class CalculationMethod(IntEnum):
    NEWTON_RAPHSON = 0
    LINEAR = 1
    LINEAR_CURRENT = 2
    ITERATIVE_CURRENT = 3


_PGM_CALC_METHODS = {
    CalculationMethod.NEWTON_RAPHSON: pgm.CalculationMethod.newton_raphson,
    CalculationMethod.LINEAR: pgm.CalculationMethod.linear,
    CalculationMethod.LINEAR_CURRENT: pgm.CalculationMethod.linear_current,
    CalculationMethod.ITERATIVE_CURRENT: pgm.CalculationMethod.iterative_current,
}

# PGM MeasuredTerminalType -> component types to search
_TERMINAL_TYPE_TO_COMPONENTS = {
    0: ["line", "transformer"],  # branch_from
    1: ["line", "transformer"],  # branch_to
    2: ["source"],
    3: ["shunt"],
    4: ["sym_load"],
    5: ["sym_gen"],
}


# =========================================================================
# Helpers
# =========================================================================


def _scalar(arr: np.ndarray) -> np.ndarray:
    """Extract scalar values from a potentially 3-phase result array.

    Short circuit results have shape ``(n, 3)`` (one value per phase).
    Power flow results have shape ``(n,)``.  This helper returns phase A
    (index 0) when the array is 2-D, otherwise returns the array as-is.
    """
    if arr.ndim == 2:
        return arr[:, 0]
    return arr


def _get_optional_array(attr, default=0, dtype=np.float64) -> np.ndarray:
    """Get array from attribute, using default if not initialized."""
    if attr.is_initialized():
        return attr.array
    return np.full(len(attr), default, dtype=dtype)


def _get_status_array(attr, default: int = 1) -> np.ndarray:
    """Get status array with default value of 1 (enabled)."""
    if attr.is_initialized():
        return attr.array.astype(np.int8)
    return np.full(len(attr), default, dtype=np.int8)


# =========================================================================
# Base processor
# =========================================================================


class PGMElementProcessor(t.Generic[T]):
    """Base class for PGM element processors.

    Each processor handles one Movici entity type and knows how to build
    PGM input/update arrays and write results back to entity attributes.

    Class attributes:
        PGM_COMPONENT: PGM component type name (e.g. ``"node"``, ``"line"``).
            Multiple processors can share the same PGM_COMPONENT; the wrapper
            concatenates their arrays.
    """

    PGM_COMPONENT: str

    def __init__(self, wrapper: PowerGridWrapper, entity_group: T):
        self.wrapper = wrapper
        self.entity_group = entity_group

    @property
    def id_manager(self) -> ComponentIdManager:
        return self.wrapper.id_manager

    def build_input_array(self) -> t.Optional[np.ndarray]:
        raise NotImplementedError

    def build_update_array(self) -> t.Optional[np.ndarray]:
        return None

    def write_results(self, result: dict):
        pass


# =========================================================================
# Node processors
# =========================================================================


class NodeProcessor(PGMElementProcessor):
    PGM_COMPONENT = "node"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("node", eg.index.ids)
        arr = pgm.initialize_array("input", "node", len(eg))
        arr["id"] = pgm_ids
        arr["u_rated"] = eg.rated_voltage.array
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        node_result = result.get("node")
        if node_result is None:
            return
        result_ids = self.id_manager.get_movici_ids("node", node_result["id"])
        mask = np.isin(result_ids, eg.index.ids)
        if not np.any(mask):
            return
        indices = eg.get_indices(result_ids[mask])
        eg.voltage_pu[indices] = _scalar(node_result["u_pu"][mask])
        eg.voltage_angle[indices] = _scalar(node_result["u_angle"][mask])
        eg.voltage[indices] = _scalar(node_result["u"][mask])
        # p, q are not available in short circuit results
        if "p" in node_result.dtype.names:
            eg.active_power[indices] = node_result["p"][mask]
            eg.reactive_power[indices] = node_result["q"][mask]


class VirtualNodeProcessor(NodeProcessor):
    """Same as NodeProcessor but for virtual node entities."""

    pass


# =========================================================================
# Line/branch processors
# =========================================================================


class LineProcessor(PGMElementProcessor):
    PGM_COMPONENT = "line"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("line", eg.index.ids)
        from_node_pgm = self.id_manager.get_pgm_ids("node", eg.from_node_id.array)
        to_node_pgm = self.id_manager.get_pgm_ids("node", eg.to_node_id.array)

        arr = pgm.initialize_array("input", "line", len(eg))
        arr["id"] = pgm_ids
        arr["from_node"] = from_node_pgm
        arr["to_node"] = to_node_pgm
        arr["from_status"] = _get_status_array(eg.from_status)
        arr["to_status"] = _get_status_array(eg.to_status)
        arr["r1"] = eg.resistance.array
        arr["x1"] = eg.reactance.array
        arr["c1"] = eg.capacitance.array
        arr["tan1"] = eg.tan_delta.array
        i_n = _get_optional_array(eg.rated_current, default=np.inf)
        arr["i_n"] = np.where(np.isinf(i_n), np.nan, i_n)
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        line_result = result.get("line")
        if line_result is None:
            return
        result_ids = self.id_manager.get_movici_ids("line", line_result["id"])
        mask = np.isin(result_ids, eg.index.ids)
        if not np.any(mask):
            return
        indices = eg.get_indices(result_ids[mask])
        eg.current_from[indices] = _scalar(line_result["i_from"][mask])
        eg.current_to[indices] = _scalar(line_result["i_to"][mask])
        # p, q, loading are not available in short circuit results
        if "p_from" in line_result.dtype.names:
            eg.power_from[indices] = line_result["p_from"][mask]
            eg.power_to[indices] = line_result["p_to"][mask]
            eg.reactive_power_from[indices] = line_result["q_from"][mask]
            eg.reactive_power_to[indices] = line_result["q_to"][mask]
            eg.loading[indices] = line_result["loading"][mask]


class CableProcessor(LineProcessor):
    """Same as LineProcessor but for underground cable entities."""

    pass


class LinkProcessor(PGMElementProcessor):
    """Converts zero-impedance links to minimal-impedance PGM lines."""

    PGM_COMPONENT = "line"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        n = len(eg)
        pgm_ids = self.id_manager.register_ids("line", eg.index.ids)
        from_node_pgm = self.id_manager.get_pgm_ids("node", eg.from_node_id.array)
        to_node_pgm = self.id_manager.get_pgm_ids("node", eg.to_node_id.array)

        arr = pgm.initialize_array("input", "line", n)
        arr["id"] = pgm_ids
        arr["from_node"] = from_node_pgm
        arr["to_node"] = to_node_pgm
        arr["from_status"] = _get_status_array(eg.from_status)
        arr["to_status"] = _get_status_array(eg.to_status)
        arr["r1"] = np.full(n, 1e-6)
        arr["x1"] = np.full(n, 1e-6)
        arr["c1"] = np.full(n, 1e-12)
        arr["tan1"] = np.zeros(n)
        arr["i_n"] = np.full(n, np.nan)
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        line_result = result.get("line")
        if line_result is None:
            return
        result_ids = self.id_manager.get_movici_ids("line", line_result["id"])
        mask = np.isin(result_ids, eg.index.ids)
        if not np.any(mask):
            return
        indices = eg.get_indices(result_ids[mask])
        eg.current_from[indices] = _scalar(line_result["i_from"][mask])
        eg.current_to[indices] = _scalar(line_result["i_to"][mask])
        if "p_from" in line_result.dtype.names:
            eg.power_from[indices] = line_result["p_from"][mask]
            eg.power_to[indices] = line_result["p_to"][mask]
            eg.reactive_power_from[indices] = line_result["q_from"][mask]
            eg.reactive_power_to[indices] = line_result["q_to"][mask]
            eg.loading[indices] = line_result["loading"][mask]


class TransformerProcessor(PGMElementProcessor):
    PGM_COMPONENT = "transformer"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("transformer", eg.index.ids)
        from_node_pgm = self.id_manager.get_pgm_ids("node", eg.from_node_id.array)
        to_node_pgm = self.id_manager.get_pgm_ids("node", eg.to_node_id.array)

        arr = pgm.initialize_array("input", "transformer", len(eg))
        arr["id"] = pgm_ids
        arr["from_node"] = from_node_pgm
        arr["to_node"] = to_node_pgm
        arr["from_status"] = _get_status_array(eg.from_status)
        arr["to_status"] = _get_status_array(eg.to_status)
        arr["u1"] = eg.primary_voltage.array
        arr["u2"] = eg.secondary_voltage.array
        arr["sn"] = eg.rated_power.array
        arr["uk"] = eg.short_circuit_voltage.array
        arr["pk"] = eg.copper_loss.array
        arr["i0"] = eg.no_load_current.array
        arr["p0"] = eg.no_load_loss.array
        arr["winding_from"] = _get_optional_array(eg.winding_from, default=1, dtype=np.int8)
        arr["winding_to"] = _get_optional_array(eg.winding_to, default=1, dtype=np.int8)
        arr["clock"] = _get_optional_array(eg.clock, default=0, dtype=np.int8)
        arr["tap_side"] = _get_optional_array(eg.tap_side, default=0, dtype=np.int8)
        arr["tap_pos"] = _get_optional_array(eg.tap_position, default=0, dtype=np.int8)
        arr["tap_min"] = _get_optional_array(eg.tap_min, default=0, dtype=np.int8)
        arr["tap_max"] = _get_optional_array(eg.tap_max, default=0, dtype=np.int8)
        arr["tap_nom"] = _get_optional_array(eg.tap_nom, default=0, dtype=np.int8)
        arr["tap_size"] = _get_optional_array(eg.tap_size, default=0.0)
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        trafo_result = result.get("transformer")
        if trafo_result is None:
            return
        result_ids = self.id_manager.get_movici_ids("transformer", trafo_result["id"])
        mask = np.isin(result_ids, eg.index.ids)
        if not np.any(mask):
            return
        indices = eg.get_indices(result_ids[mask])
        eg.current_from[indices] = _scalar(trafo_result["i_from"][mask])
        eg.current_to[indices] = _scalar(trafo_result["i_to"][mask])
        if "p_from" in trafo_result.dtype.names:
            eg.power_from[indices] = trafo_result["p_from"][mask]
            eg.power_to[indices] = trafo_result["p_to"][mask]
            eg.loading[indices] = trafo_result["loading"][mask]


class ThreeWindingTransformerProcessor(PGMElementProcessor):
    PGM_COMPONENT = "three_winding_transformer"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("three_winding_transformer", eg.index.ids)
        node1_pgm = self.id_manager.get_pgm_ids("node", eg.node_1_id.array)
        node2_pgm = self.id_manager.get_pgm_ids("node", eg.node_2_id.array)
        node3_pgm = self.id_manager.get_pgm_ids("node", eg.node_3_id.array)

        arr = pgm.initialize_array("input", "three_winding_transformer", len(eg))
        arr["id"] = pgm_ids
        arr["node_1"] = node1_pgm
        arr["node_2"] = node2_pgm
        arr["node_3"] = node3_pgm
        arr["status_1"] = _get_status_array(eg.status_1)
        arr["status_2"] = _get_status_array(eg.status_2)
        arr["status_3"] = _get_status_array(eg.status_3)
        arr["u1"] = eg.primary_voltage.array
        arr["u2"] = eg.secondary_voltage.array
        arr["u3"] = eg.tertiary_voltage.array
        arr["sn_1"] = eg.rated_power_1.array
        arr["sn_2"] = eg.rated_power_2.array
        arr["sn_3"] = eg.rated_power_3.array
        arr["uk_12"] = eg.short_circuit_voltage_12.array
        arr["uk_13"] = eg.short_circuit_voltage_13.array
        arr["uk_23"] = eg.short_circuit_voltage_23.array
        arr["pk_12"] = eg.copper_loss_12.array
        arr["pk_13"] = eg.copper_loss_13.array
        arr["pk_23"] = eg.copper_loss_23.array
        arr["i0"] = eg.no_load_current.array
        arr["p0"] = eg.no_load_loss.array
        arr["winding_1"] = _get_optional_array(eg.winding_1, default=1, dtype=np.int8)
        arr["winding_2"] = _get_optional_array(eg.winding_2, default=1, dtype=np.int8)
        arr["winding_3"] = _get_optional_array(eg.winding_3, default=1, dtype=np.int8)
        arr["clock_12"] = _get_optional_array(eg.clock_12, default=0, dtype=np.int8)
        arr["clock_13"] = _get_optional_array(eg.clock_13, default=0, dtype=np.int8)
        arr["tap_side"] = _get_optional_array(eg.tap_side, default=0, dtype=np.int8)
        arr["tap_pos"] = _get_optional_array(eg.tap_position, default=0, dtype=np.int8)
        arr["tap_min"] = _get_optional_array(eg.tap_min, default=0, dtype=np.int8)
        arr["tap_max"] = _get_optional_array(eg.tap_max, default=0, dtype=np.int8)
        arr["tap_nom"] = _get_optional_array(eg.tap_nom, default=0, dtype=np.int8)
        arr["tap_size"] = _get_optional_array(eg.tap_size, default=0.0)
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        t3w_result = result.get("three_winding_transformer")
        if t3w_result is None:
            return
        result_ids = self.id_manager.get_movici_ids(
            "three_winding_transformer", t3w_result["id"]
        )
        indices = eg.get_indices(result_ids)
        eg.current_1[indices] = _scalar(t3w_result["i_1"])
        eg.current_2[indices] = _scalar(t3w_result["i_2"])
        eg.current_3[indices] = _scalar(t3w_result["i_3"])
        if "p_1" in t3w_result.dtype.names:
            eg.power_1[indices] = t3w_result["p_1"]
            eg.power_2[indices] = t3w_result["p_2"]
            eg.power_3[indices] = t3w_result["p_3"]
            eg.reactive_power_1[indices] = t3w_result["q_1"]
            eg.reactive_power_2[indices] = t3w_result["q_2"]
            eg.reactive_power_3[indices] = t3w_result["q_3"]
            eg.loading[indices] = t3w_result["loading"]


# =========================================================================
# Appliance processors
# =========================================================================


class LoadProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_load"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("sym_load", eg.index.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", eg.node_id.array)

        arr = pgm.initialize_array("input", "sym_load", len(eg))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = _get_status_array(eg.status)
        arr["type"] = _get_optional_array(eg.load_type, default=0, dtype=np.int8)
        arr["p_specified"] = eg.p_specified.array
        arr["q_specified"] = eg.q_specified.array
        return arr

    def build_update_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        p_changed = eg.p_specified.has_changes()
        q_changed = eg.q_specified.has_changes()
        if not (p_changed or q_changed):
            return None

        changed = eg.p_specified.changed | eg.q_specified.changed
        idx = np.flatnonzero(changed)
        changed_ids = eg.index.ids[idx]

        pgm_ids = self.id_manager.get_pgm_ids("sym_load", changed_ids)
        arr = pgm.initialize_array("update", "sym_load", len(idx))
        arr["id"] = pgm_ids
        arr["p_specified"] = eg.p_specified.array[idx]
        arr["q_specified"] = eg.q_specified.array[idx]
        return arr


class GeneratorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_gen"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("sym_gen", eg.index.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", eg.node_id.array)

        arr = pgm.initialize_array("input", "sym_gen", len(eg))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = _get_status_array(eg.status)
        arr["type"] = _get_optional_array(eg.load_type, default=0, dtype=np.int8)
        arr["p_specified"] = eg.p_specified.array
        arr["q_specified"] = eg.q_specified.array
        return arr

    def build_update_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        p_changed = eg.p_specified.has_changes()
        q_changed = eg.q_specified.has_changes()
        if not (p_changed or q_changed):
            return None

        changed = eg.p_specified.changed | eg.q_specified.changed
        idx = np.flatnonzero(changed)
        changed_ids = eg.index.ids[idx]

        pgm_ids = self.id_manager.get_pgm_ids("sym_gen", changed_ids)
        arr = pgm.initialize_array("update", "sym_gen", len(idx))
        arr["id"] = pgm_ids
        arr["p_specified"] = eg.p_specified.array[idx]
        arr["q_specified"] = eg.q_specified.array[idx]
        return arr


class SourceProcessor(PGMElementProcessor):
    PGM_COMPONENT = "source"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("source", eg.index.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", eg.node_id.array)

        arr = pgm.initialize_array("input", "source", len(eg))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = _get_status_array(eg.status)
        arr["u_ref"] = eg.reference_voltage.array
        arr["u_ref_angle"] = _get_optional_array(eg.reference_angle, default=0.0)
        arr["sk"] = _get_optional_array(eg.short_circuit_power, default=1e10)
        arr["rx_ratio"] = _get_optional_array(eg.rx_ratio, default=0.1)
        return arr


class ShuntProcessor(PGMElementProcessor):
    PGM_COMPONENT = "shunt"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("shunt", eg.index.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", eg.node_id.array)

        arr = pgm.initialize_array("input", "shunt", len(eg))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = _get_status_array(eg.status)
        arr["g1"] = eg.conductance.array
        arr["b1"] = eg.susceptance.array
        return arr


# =========================================================================
# Sensor processors (state estimation)
# =========================================================================


class VoltageSensorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_voltage_sensor"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("sym_voltage_sensor", eg.index.ids)
        measured_pgm = self.id_manager.get_pgm_ids("node", eg.node_id.array)

        arr = pgm.initialize_array("input", "sym_voltage_sensor", len(eg))
        arr["id"] = pgm_ids
        arr["measured_object"] = measured_pgm
        arr["u_measured"] = eg.measured_voltage.array
        arr["u_sigma"] = eg.voltage_sigma.array
        return arr


class PowerSensorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_power_sensor"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("sym_power_sensor", eg.index.ids)

        # Resolve measured_object IDs based on terminal type
        measured_pgm = np.zeros(len(eg), dtype=np.int32)
        for i, (obj_id, term_type) in enumerate(
            zip(eg.measured_object_id.array, eg.measured_terminal_type.array)
        ):
            component_types = _TERMINAL_TYPE_TO_COMPONENTS.get(int(term_type), [])
            for comp_type in component_types:
                try:
                    measured_pgm[i] = self.id_manager.get_pgm_ids(
                        comp_type, np.array([obj_id])
                    )[0]
                    break
                except (ValueError, KeyError):
                    continue
            else:
                raise ValueError(
                    f"Cannot find measured_object {obj_id} for terminal_type {term_type}"
                )

        arr = pgm.initialize_array("input", "sym_power_sensor", len(eg))
        arr["id"] = pgm_ids
        arr["measured_object"] = measured_pgm
        arr["measured_terminal_type"] = eg.measured_terminal_type.array
        arr["p_measured"] = eg.measured_active_power.array
        arr["q_measured"] = eg.measured_reactive_power.array
        arr["power_sigma"] = eg.power_sigma.array
        return arr


class CurrentSensorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_current_sensor"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("sym_current_sensor", eg.index.ids)

        # Resolve measured_object IDs based on terminal type (same as power sensor)
        measured_pgm = np.zeros(len(eg), dtype=np.int32)
        for i, (obj_id, term_type) in enumerate(
            zip(eg.measured_object_id.array, eg.measured_terminal_type.array)
        ):
            component_types = _TERMINAL_TYPE_TO_COMPONENTS.get(int(term_type), [])
            for comp_type in component_types:
                try:
                    measured_pgm[i] = self.id_manager.get_pgm_ids(
                        comp_type, np.array([obj_id])
                    )[0]
                    break
                except (ValueError, KeyError):
                    continue
            else:
                raise ValueError(
                    f"Cannot find measured_object {obj_id} for terminal_type {term_type}"
                )

        arr = pgm.initialize_array("input", "sym_current_sensor", len(eg))
        arr["id"] = pgm_ids
        arr["measured_object"] = measured_pgm
        arr["measured_terminal_type"] = eg.measured_terminal_type.array
        arr["i_measured"] = eg.measured_current.array
        arr["i_sigma"] = eg.current_sigma.array
        arr["angle_measurement_type"] = eg.angle_measurement_type.array
        arr["i_angle_measured"] = eg.measured_current_angle.array
        arr["i_angle_sigma"] = eg.current_angle_sigma.array
        return arr


# =========================================================================
# Fault processor (short circuit)
# =========================================================================


class FaultProcessor(PGMElementProcessor):
    PGM_COMPONENT = "fault"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("fault", eg.index.ids)
        fault_object_pgm = self.id_manager.get_pgm_ids("node", eg.fault_object_id.array)

        arr = pgm.initialize_array("input", "fault", len(eg))
        arr["id"] = pgm_ids
        arr["status"] = _get_status_array(eg.status)
        arr["fault_type"] = eg.fault_type.array
        arr["fault_phase"] = _get_optional_array(eg.fault_phase, default=0, dtype=np.int8)
        arr["fault_object"] = fault_object_pgm
        arr["r_f"] = _get_optional_array(eg.fault_resistance, default=0.0)
        arr["x_f"] = _get_optional_array(eg.fault_reactance, default=0.0)
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        fault_result = result.get("fault")
        if fault_result is None:
            return
        # i_f and i_f_angle are only in short-circuit results
        if "i_f" not in fault_result.dtype.names:
            return
        result_ids = self.id_manager.get_movici_ids("fault", fault_result["id"])
        indices = eg.get_indices(result_ids)
        eg.fault_current[indices] = _scalar(fault_result["i_f"])
        eg.fault_current_angle[indices] = _scalar(fault_result["i_f_angle"])


# =========================================================================
# Regulator processor
# =========================================================================


class TapRegulatorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "transformer_tap_regulator"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        pgm_ids = self.id_manager.register_ids("transformer_tap_regulator", eg.index.ids)

        # Resolve regulated_object_id to transformer PGM ID
        regulated_pgm = np.zeros(len(eg), dtype=np.int32)
        for i, obj_id in enumerate(eg.regulated_object_id.array):
            # Try both transformer and three_winding_transformer
            for comp_type in ("transformer", "three_winding_transformer"):
                try:
                    regulated_pgm[i] = self.id_manager.get_pgm_ids(
                        comp_type, np.array([obj_id])
                    )[0]
                    break
                except (ValueError, KeyError):
                    continue
            else:
                raise ValueError(
                    f"Cannot find regulated transformer for ID {obj_id}"
                )

        arr = pgm.initialize_array("input", "transformer_tap_regulator", len(eg))
        arr["id"] = pgm_ids
        arr["regulated_object"] = regulated_pgm
        arr["status"] = _get_status_array(eg.status)
        arr["control_side"] = eg.control_side.array.astype(np.int8)
        arr["u_set"] = eg.voltage_setpoint.array
        arr["u_band"] = eg.voltage_band.array
        arr["line_drop_compensation_r"] = _get_optional_array(
            eg.line_drop_compensation_r, default=0.0
        )
        arr["line_drop_compensation_x"] = _get_optional_array(
            eg.line_drop_compensation_x, default=0.0
        )
        return arr

    def write_results(self, result: dict):
        eg = self.entity_group
        if not len(eg):
            return
        reg_result = result.get("transformer_tap_regulator")
        if reg_result is None:
            return
        if "tap_pos" not in reg_result.dtype.names:
            return
        result_ids = self.id_manager.get_movici_ids(
            "transformer_tap_regulator", reg_result["id"]
        )
        indices = eg.get_indices(result_ids)
        eg.tap_position[indices] = reg_result["tap_pos"]


# =========================================================================
# Wrapper
# =========================================================================


class PowerGridWrapper:
    """Orchestrates PGM processors and manages the PowerGridModel.

    Processors are created in dependency order (nodes before branches/appliances)
    so that ID registration works correctly.
    """

    def __init__(self):
        self.model: t.Optional[pgm.PowerGridModel] = None
        self.input_data: dict[str, np.ndarray] = {}
        self.id_manager = ComponentIdManager()
        self.processors: list[PGMElementProcessor] = []

    def initialize(self, dataset: PowerGridNetwork):
        """Build the PGM model from a PowerGridNetwork.

        :param dataset: PowerGridNetwork with entity groups loaded with init data.
        """
        self.id_manager.clear()
        self.input_data = {}
        self.processors = []

        # Create processors in dependency order:
        # 1. Nodes (must be first so branches can look up node IDs)
        # 2. Branches (lines, cables, links, transformers)
        # 3. Appliances (loads, generators, sources, shunts)
        # 4. Sensors, faults, regulators
        processor_specs = [
            NodeProcessor(self, dataset.nodes),
            VirtualNodeProcessor(self, dataset.virtual_nodes),
            LineProcessor(self, dataset.lines),
            CableProcessor(self, dataset.cables),
            LinkProcessor(self, dataset.links),
            TransformerProcessor(self, dataset.transformers),
            ThreeWindingTransformerProcessor(self, dataset.three_winding_transformers),
            LoadProcessor(self, dataset.loads),
            GeneratorProcessor(self, dataset.generators),
            SourceProcessor(self, dataset.sources),
            ShuntProcessor(self, dataset.shunts),
            VoltageSensorProcessor(self, dataset.voltage_sensors),
            PowerSensorProcessor(self, dataset.power_sensors),
            CurrentSensorProcessor(self, dataset.current_sensors),
            FaultProcessor(self, dataset.faults),
            TapRegulatorProcessor(self, dataset.tap_regulators),
        ]

        for proc in processor_specs:
            arr = proc.build_input_array()
            if arr is not None and len(arr) > 0:
                self.processors.append(proc)
                comp = proc.PGM_COMPONENT
                if comp in self.input_data:
                    self.input_data[comp] = np.concatenate(
                        [self.input_data[comp], arr]
                    )
                else:
                    self.input_data[comp] = arr

        self.model = pgm.PowerGridModel(self.input_data)

    def process_changes(self):
        """Apply dynamic changes from processors with SUB attributes."""
        update_data: dict[str, np.ndarray] = {}
        for proc in self.processors:
            arr = proc.build_update_array()
            if arr is not None and len(arr) > 0:
                comp = proc.PGM_COMPONENT
                if comp in update_data:
                    update_data[comp] = np.concatenate([update_data[comp], arr])
                else:
                    update_data[comp] = arr
        if update_data:
            self.model.update(update_data=update_data)

    def calculate_power_flow(
        self,
        method: CalculationMethod = CalculationMethod.NEWTON_RAPHSON,
        symmetric: bool = True,
    ) -> dict:
        """Run power flow calculation.

        :returns: Raw PGM result dictionary.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call initialize first.")
        calc_method = _PGM_CALC_METHODS.get(method, pgm.CalculationMethod.newton_raphson)
        kwargs: dict[str, t.Any] = {
            "symmetric": symmetric,
            "calculation_method": calc_method,
        }
        if "transformer_tap_regulator" in self.input_data:
            kwargs["tap_changing_strategy"] = pgm.TapChangingStrategy.any_valid_tap
        return self.model.calculate_power_flow(**kwargs)

    def calculate_state_estimation(self, symmetric: bool = True) -> dict:
        """Run state estimation calculation.

        :returns: Raw PGM result dictionary.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call initialize first.")
        if not any(
            s in self.input_data
            for s in ("sym_voltage_sensor", "sym_power_sensor", "sym_current_sensor")
        ):
            raise RuntimeError("No sensors defined.")
        return self.model.calculate_state_estimation(symmetric=symmetric)

    def calculate_short_circuit(self) -> dict:
        """Run short circuit calculation.

        :returns: Raw PGM result dictionary.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call initialize first.")
        if "fault" not in self.input_data:
            raise RuntimeError("No faults defined.")
        return self.model.calculate_short_circuit()

    def write_results(self, result: dict):
        """Write PGM results back to entity groups via processors."""
        for proc in self.processors:
            proc.write_results(result)

    def close(self):
        """Clean up resources."""
        self.model = None
        self.input_data.clear()
        self.id_manager.clear()
        self.processors.clear()
