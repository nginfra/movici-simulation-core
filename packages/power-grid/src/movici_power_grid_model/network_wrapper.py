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

if t.TYPE_CHECKING:
    from .dataset import PowerGridNetwork


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

# PGM TapChangingStrategy string -> enum
_TAP_CHANGING_STRATEGIES = {
    "disabled": pgm.TapChangingStrategy.disabled,
    "any_valid_tap": pgm.TapChangingStrategy.any_valid_tap,
    "min_voltage_tap": pgm.TapChangingStrategy.min_voltage_tap,
    "max_voltage_tap": pgm.TapChangingStrategy.max_voltage_tap,
    "fast_any_tap": pgm.TapChangingStrategy.fast_any_tap,
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


class PGMElementProcessor:
    """Base class for PGM element processors.

    Each processor handles one Movici entity type and knows how to build
    PGM input/update arrays and write results back to entity attributes.

    Entity IDs from Movici are used directly as PGM component IDs, since
    entity IDs are unique within a dataset.

    Class attributes:
        PGM_COMPONENT: PGM component type name (e.g. ``"node"``, ``"line"``).
            Multiple processors can share the same PGM_COMPONENT; the wrapper
            concatenates their arrays.
    """

    PGM_COMPONENT: str

    def __init__(self, wrapper: PowerGridWrapper, entity_group):
        self.wrapper = wrapper
        self.entity_group = entity_group

    def build_input_array(self) -> t.Optional[np.ndarray]:
        raise NotImplementedError

    def build_update_array(self) -> t.Optional[np.ndarray]:
        return None

    def write_results(self, result: dict):
        pass

    def _get_result_slice(self, result: dict) -> tuple[np.ndarray, np.ndarray] | None:
        """Extract the result slice relevant to this processor's entity group.

        :returns: ``(sliced_result, entity_indices)`` or ``None`` if no results
            match this processor's entities.
        """
        comp_result = result.get(self.PGM_COMPONENT)
        if comp_result is None:
            return None
        mask = np.isin(comp_result["id"], self.entity_group.index.ids)
        if not np.any(mask):
            return None
        indices = self.entity_group.get_indices(comp_result["id"][mask])
        return comp_result[mask], indices


# =========================================================================
# Node processors
# =========================================================================


class NodeProcessor(PGMElementProcessor):
    PGM_COMPONENT = "node"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "node", len(eg))
        arr["id"] = eg.index.ids
        arr["u_rated"] = eg.rated_voltage.array
        return arr

    def write_results(self, result: dict):
        if not len(self.entity_group):
            return
        sliced = self._get_result_slice(result)
        if sliced is None:
            return
        comp_result, indices = sliced
        eg = self.entity_group
        eg.voltage_pu[indices] = _scalar(comp_result["u_pu"])
        eg.voltage_angle[indices] = _scalar(comp_result["u_angle"])
        eg.voltage[indices] = _scalar(comp_result["u"])
        # p, q are not available in short circuit results
        if "p" in comp_result.dtype.names:
            eg.active_power[indices] = comp_result["p"]
            eg.reactive_power[indices] = comp_result["q"]


# =========================================================================
# Line/branch processors
# =========================================================================


class LineProcessor(PGMElementProcessor):
    PGM_COMPONENT = "line"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "line", len(eg))
        arr["id"] = eg.index.ids
        arr["from_node"] = eg.from_node_id.array
        arr["to_node"] = eg.to_node_id.array
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
        if not len(self.entity_group):
            return
        sliced = self._get_result_slice(result)
        if sliced is None:
            return
        comp_result, indices = sliced
        eg = self.entity_group
        eg.current_from[indices] = _scalar(comp_result["i_from"])
        eg.current_to[indices] = _scalar(comp_result["i_to"])
        # p, q, loading are not available in short circuit results
        if "p_from" in comp_result.dtype.names:
            eg.power_from[indices] = comp_result["p_from"]
            eg.power_to[indices] = comp_result["p_to"]
            eg.reactive_power_from[indices] = comp_result["q_from"]
            eg.reactive_power_to[indices] = comp_result["q_to"]
            eg.loading[indices] = comp_result["loading"]


class LinkProcessor(LineProcessor):
    """Converts zero-impedance links to minimal-impedance PGM lines.

    Links have no electrical parameters, so we override the impedance
    fields with near-zero values after the parent builds the base array.
    """

    def _get_impedance_fields(self, n: int) -> dict:
        return {
            "r1": np.full(n, 1e-6),
            "x1": np.full(n, 1e-6),
            "c1": np.full(n, 1e-12),
            "tan1": np.zeros(n),
            "i_n": np.full(n, np.nan),
        }

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        n = len(eg)
        arr = pgm.initialize_array("input", "line", n)
        arr["id"] = eg.index.ids
        arr["from_node"] = eg.from_node_id.array
        arr["to_node"] = eg.to_node_id.array
        arr["from_status"] = _get_status_array(eg.from_status)
        arr["to_status"] = _get_status_array(eg.to_status)
        for field, values in self._get_impedance_fields(n).items():
            arr[field] = values
        return arr


class TransformerProcessor(PGMElementProcessor):
    PGM_COMPONENT = "transformer"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "transformer", len(eg))
        arr["id"] = eg.index.ids
        arr["from_node"] = eg.from_node_id.array
        arr["to_node"] = eg.to_node_id.array
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
        if not len(self.entity_group):
            return
        sliced = self._get_result_slice(result)
        if sliced is None:
            return
        comp_result, indices = sliced
        eg = self.entity_group
        eg.current_from[indices] = _scalar(comp_result["i_from"])
        eg.current_to[indices] = _scalar(comp_result["i_to"])
        if "p_from" in comp_result.dtype.names:
            eg.power_from[indices] = comp_result["p_from"]
            eg.power_to[indices] = comp_result["p_to"]
            eg.reactive_power_from[indices] = comp_result["q_from"]
            eg.reactive_power_to[indices] = comp_result["q_to"]
            eg.loading[indices] = comp_result["loading"]


class ThreeWindingTransformerProcessor(PGMElementProcessor):
    PGM_COMPONENT = "three_winding_transformer"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "three_winding_transformer", len(eg))
        arr["id"] = eg.index.ids
        arr["node_1"] = eg.node_1_id.array
        arr["node_2"] = eg.node_2_id.array
        arr["node_3"] = eg.node_3_id.array
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
        indices = eg.get_indices(t3w_result["id"])
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


class ApplianceProcessor(PGMElementProcessor):
    """Shared base for sym_load and sym_gen processors."""

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", self.PGM_COMPONENT, len(eg))
        arr["id"] = eg.index.ids
        arr["node"] = eg.node_id.array
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

        arr = pgm.initialize_array("update", self.PGM_COMPONENT, len(idx))
        arr["id"] = changed_ids
        arr["p_specified"] = eg.p_specified.array[idx]
        arr["q_specified"] = eg.q_specified.array[idx]
        return arr


class LoadProcessor(ApplianceProcessor):
    PGM_COMPONENT = "sym_load"


class GeneratorProcessor(ApplianceProcessor):
    PGM_COMPONENT = "sym_gen"


class SourceProcessor(PGMElementProcessor):
    PGM_COMPONENT = "source"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "source", len(eg))
        arr["id"] = eg.index.ids
        arr["node"] = eg.node_id.array
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
        arr = pgm.initialize_array("input", "shunt", len(eg))
        arr["id"] = eg.index.ids
        arr["node"] = eg.node_id.array
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
        arr = pgm.initialize_array("input", "sym_voltage_sensor", len(eg))
        arr["id"] = eg.index.ids
        arr["measured_object"] = eg.node_id.array
        arr["u_measured"] = eg.measured_voltage.array
        arr["u_sigma"] = eg.voltage_sigma.array
        return arr

    def build_update_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        if not eg.measured_voltage.has_changes():
            return None
        idx = np.flatnonzero(eg.measured_voltage.changed)
        changed_ids = eg.index.ids[idx]
        arr = pgm.initialize_array("update", "sym_voltage_sensor", len(idx))
        arr["id"] = changed_ids
        arr["u_measured"] = eg.measured_voltage.array[idx]
        return arr


class PowerSensorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_power_sensor"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "sym_power_sensor", len(eg))
        arr["id"] = eg.index.ids
        arr["measured_object"] = eg.measured_object_id.array
        arr["measured_terminal_type"] = eg.measured_terminal_type.array
        arr["p_measured"] = eg.measured_active_power.array
        arr["q_measured"] = eg.measured_reactive_power.array
        arr["power_sigma"] = eg.power_sigma.array
        return arr

    def build_update_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        p_changed = eg.measured_active_power.has_changes()
        q_changed = eg.measured_reactive_power.has_changes()
        if not (p_changed or q_changed):
            return None
        changed = eg.measured_active_power.changed | eg.measured_reactive_power.changed
        idx = np.flatnonzero(changed)
        changed_ids = eg.index.ids[idx]
        arr = pgm.initialize_array("update", "sym_power_sensor", len(idx))
        arr["id"] = changed_ids
        arr["p_measured"] = eg.measured_active_power.array[idx]
        arr["q_measured"] = eg.measured_reactive_power.array[idx]
        return arr


class CurrentSensorProcessor(PGMElementProcessor):
    PGM_COMPONENT = "sym_current_sensor"

    def build_input_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        arr = pgm.initialize_array("input", "sym_current_sensor", len(eg))
        arr["id"] = eg.index.ids
        arr["measured_object"] = eg.measured_object_id.array
        arr["measured_terminal_type"] = eg.measured_terminal_type.array
        arr["i_measured"] = eg.measured_current.array
        arr["i_sigma"] = eg.current_sigma.array
        arr["angle_measurement_type"] = eg.angle_measurement_type.array
        arr["i_angle_measured"] = eg.measured_current_angle.array
        arr["i_angle_sigma"] = eg.current_angle_sigma.array
        return arr

    def build_update_array(self):
        eg = self.entity_group
        if not len(eg):
            return None
        i_changed = eg.measured_current.has_changes()
        a_changed = eg.measured_current_angle.has_changes()
        if not (i_changed or a_changed):
            return None
        changed = eg.measured_current.changed | eg.measured_current_angle.changed
        idx = np.flatnonzero(changed)
        changed_ids = eg.index.ids[idx]
        arr = pgm.initialize_array("update", "sym_current_sensor", len(idx))
        arr["id"] = changed_ids
        arr["i_measured"] = eg.measured_current.array[idx]
        arr["i_angle_measured"] = eg.measured_current_angle.array[idx]
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
        arr = pgm.initialize_array("input", "fault", len(eg))
        arr["id"] = eg.index.ids
        arr["status"] = _get_status_array(eg.status)
        arr["fault_type"] = eg.fault_type.array
        arr["fault_phase"] = _get_optional_array(eg.fault_phase, default=0, dtype=np.int8)
        arr["fault_object"] = eg.fault_object_id.array
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
        indices = eg.get_indices(fault_result["id"])
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
        arr = pgm.initialize_array("input", "transformer_tap_regulator", len(eg))
        arr["id"] = eg.index.ids
        arr["regulated_object"] = eg.regulated_object_id.array
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
        indices = eg.get_indices(reg_result["id"])
        eg.tap_position[indices] = reg_result["tap_pos"]


# =========================================================================
# Wrapper
# =========================================================================


class PowerGridWrapper:
    """Orchestrates PGM processors and manages the PowerGridModel."""

    def __init__(self):
        self.model: t.Optional[pgm.PowerGridModel] = None
        self.input_data: dict[str, np.ndarray] = {}
        self.processors: list[PGMElementProcessor] = []

    def initialize(self, dataset: PowerGridNetwork):
        """Build the PGM model from a PowerGridNetwork.

        :param dataset: PowerGridNetwork with entity groups loaded with init data.
        :raises ValueError: If no source entities are defined.
        """
        if not len(dataset.sources):
            raise ValueError(
                "At least one source (slack bus) is required for power grid calculations"
            )

        self.input_data = {}
        self.processors = []

        processor_specs = [
            NodeProcessor(self, dataset.nodes),
            NodeProcessor(self, dataset.virtual_nodes),
            LineProcessor(self, dataset.lines),
            LineProcessor(self, dataset.cables),
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
                    self.input_data[comp] = np.concatenate([self.input_data[comp], arr])
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
        tap_changing_strategy: t.Optional[pgm.TapChangingStrategy] = None,
    ) -> dict:
        """Run power flow calculation.

        :param tap_changing_strategy: Strategy for automatic tap changing.
            When ``None`` (default), uses ``any_valid_tap`` if regulators are
            present, otherwise ``disabled``.
        :returns: Raw PGM result dictionary.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call initialize first.")
        calc_method = _PGM_CALC_METHODS.get(method, pgm.CalculationMethod.newton_raphson)
        if tap_changing_strategy is None and "transformer_tap_regulator" in self.input_data:
            tap_changing_strategy = pgm.TapChangingStrategy.any_valid_tap
        kwargs: dict[str, t.Any] = {
            "symmetric": symmetric,
            "calculation_method": calc_method,
        }
        if tap_changing_strategy is not None:
            kwargs["tap_changing_strategy"] = tap_changing_strategy
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
        self.processors.clear()
