"""Wrapper around power-grid-model's PowerGridModel.

This module provides the PowerGridWrapper class which encapsulates the
power-grid-model library, handling data conversion between Movici collections
and PGM structured arrays.
"""

from __future__ import annotations

import typing as t
from enum import IntEnum

import numpy as np
import power_grid_model as pgm

from .collections import (
    ApplianceResult,
    BranchResult,
    FaultCollection,
    GeneratorCollection,
    LineCollection,
    LoadCollection,
    NodeCollection,
    NodeResult,
    PowerFlowResult,
    PowerSensorCollection,
    ShortCircuitResult,
    ShuntCollection,
    SourceCollection,
    TransformerCollection,
    VoltageSensorCollection,
)
from .id_generator import ComponentIdManager


class CalculationType(IntEnum):
    """Supported calculation types."""

    POWER_FLOW = 0
    STATE_ESTIMATION = 1
    SHORT_CIRCUIT = 2


class CalculationMethod(IntEnum):
    """Power flow calculation methods."""

    NEWTON_RAPHSON = 0
    LINEAR = 1
    LINEAR_CURRENT = 2
    ITERATIVE_CURRENT = 3


class LoadGenType(IntEnum):
    """Load/generator type enumeration."""

    CONST_POWER = 0
    CONST_IMPEDANCE = 1
    CONST_CURRENT = 2


class WindingType(IntEnum):
    """Transformer winding type enumeration."""

    WYE = 0
    WYE_N = 1
    DELTA = 2


class BranchSide(IntEnum):
    """Branch side enumeration."""

    FROM = 0
    TO = 1


class FaultType(IntEnum):
    """Fault type enumeration."""

    THREE_PHASE = 0
    SINGLE_PHASE_TO_GROUND = 1
    TWO_PHASE = 2
    TWO_PHASE_TO_GROUND = 3


class PowerGridWrapper:
    """Wrapper around power-grid-model's PowerGridModel.

    This class handles:

    * Converting Movici collections to PGM structured arrays
    * Managing component ID mappings
    * Running calculations (power flow, state estimation, short circuit)
    * Converting results back to Movici-compatible collections
    """

    def __init__(self):
        self.model = None
        self.input_data: dict[str, np.ndarray] = {}
        self.id_manager = ComponentIdManager()

    def build_network(
        self,
        nodes: NodeCollection,
        lines: t.Optional[LineCollection] = None,
        transformers: t.Optional[TransformerCollection] = None,
        loads: t.Optional[LoadCollection] = None,
        generators: t.Optional[GeneratorCollection] = None,
        sources: t.Optional[SourceCollection] = None,
        shunts: t.Optional[ShuntCollection] = None,
        voltage_sensors: t.Optional[VoltageSensorCollection] = None,
        power_sensors: t.Optional[PowerSensorCollection] = None,
        faults: t.Optional[FaultCollection] = None,
    ) -> None:
        """Build the power grid model from component collections.

        :param nodes: Node collection (required).
        :param lines: Line collection (optional).
        :param transformers: Transformer collection (optional).
        :param loads: Load collection (optional).
        :param generators: Generator collection (optional).
        :param sources: Source collection (required for power flow).
        :param shunts: Shunt collection (optional).
        :param voltage_sensors: Voltage sensor collection (for state estimation).
        :param power_sensors: Power sensor collection (for state estimation).
        :param faults: Fault collection (for short circuit analysis).
        """
        self.id_manager.clear()
        self.input_data = {}

        # Build node array (required)
        self.input_data["node"] = self._build_node_array(nodes)

        # Build optional component arrays
        if lines is not None and len(lines) > 0:
            self.input_data["line"] = self._build_line_array(lines, nodes)

        if transformers is not None and len(transformers) > 0:
            self.input_data["transformer"] = self._build_transformer_array(transformers, nodes)

        if loads is not None and len(loads) > 0:
            self.input_data["sym_load"] = self._build_load_array(loads, nodes)

        if generators is not None and len(generators) > 0:
            self.input_data["sym_gen"] = self._build_generator_array(generators, nodes)

        if sources is not None and len(sources) > 0:
            self.input_data["source"] = self._build_source_array(sources, nodes)

        if shunts is not None and len(shunts) > 0:
            self.input_data["shunt"] = self._build_shunt_array(shunts, nodes)

        # Build sensor arrays (for state estimation)
        if voltage_sensors is not None and len(voltage_sensors) > 0:
            self.input_data["sym_voltage_sensor"] = self._build_voltage_sensor_array(
                voltage_sensors
            )

        if power_sensors is not None and len(power_sensors) > 0:
            self.input_data["sym_power_sensor"] = self._build_power_sensor_array(power_sensors)

        # Build fault array (for short circuit)
        if faults is not None and len(faults) > 0:
            self.input_data["fault"] = self._build_fault_array(faults)

        # Create the PowerGridModel
        self.model = pgm.PowerGridModel(self.input_data)

    def update_loads(self, loads: LoadCollection) -> None:
        """Update load values for next calculation.

        :param loads: Load collection with updated p_specified and q_specified.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call build_network first.")

        update_data = self._build_load_update(loads)
        self.model.update(update_data={"sym_load": update_data})

    def update_generators(self, generators: GeneratorCollection) -> None:
        """Update generator values for next calculation.

        :param generators: Generator collection with updated values.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call build_network first.")

        update_data = self._build_generator_update(generators)
        self.model.update(update_data={"sym_gen": update_data})

    def calculate_power_flow(
        self,
        method: CalculationMethod = CalculationMethod.NEWTON_RAPHSON,
        symmetric: bool = True,
    ) -> PowerFlowResult:
        """Run power flow calculation.

        :param method: Calculation method to use.
        :param symmetric: Whether to use symmetric (balanced) calculation.
        :returns: Power flow results.
        :raises RuntimeError: If network not built.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call build_network first.")

        # Map calculation method
        calc_method = self._get_calculation_method(method)

        # Run calculation
        result = self.model.calculate_power_flow(
            symmetric=symmetric,
            calculation_method=calc_method,
        )

        return self._convert_power_flow_result(result)

    def calculate_state_estimation(
        self,
        symmetric: bool = True,
    ) -> PowerFlowResult:
        """Run state estimation calculation.

        Sensors must be provided during build_network() call.

        :param symmetric: Whether to use symmetric calculation.
        :returns: Estimated state as power flow result.
        :raises RuntimeError: If network not built or no sensors defined.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call build_network first.")

        if (
            "sym_voltage_sensor" not in self.input_data
            and "sym_power_sensor" not in self.input_data
        ):
            raise RuntimeError(
                "No sensors defined. Provide voltage_sensors or power_sensors in build_network()."
            )

        result = self.model.calculate_state_estimation(symmetric=symmetric)
        return self._convert_power_flow_result(result)

    def calculate_short_circuit(self) -> ShortCircuitResult:
        """Run short circuit calculation.

        Faults must be provided during build_network() call.

        :returns: Short circuit results.
        :raises RuntimeError: If network not built or no faults defined.
        """
        if self.model is None:
            raise RuntimeError("Network not built. Call build_network first.")

        if "fault" not in self.input_data:
            raise RuntimeError("No faults defined. Provide faults in build_network().")

        result = self.model.calculate_short_circuit()
        # Get fault IDs from input data
        fault_ids = self.id_manager.get_movici_ids("fault", self.input_data["fault"]["id"])
        return self._convert_short_circuit_result(result, fault_ids)

    # =========================================================================
    # Array building methods
    # =========================================================================

    def _build_node_array(self, nodes: NodeCollection) -> np.ndarray:
        """Build PGM node input array.

        :param nodes: Node collection.
        :returns: PGM structured array for nodes.
        """
        pgm_ids = self.id_manager.register_ids("node", nodes.ids)
        arr = pgm.initialize_array("input", "node", len(nodes))
        arr["id"] = pgm_ids
        arr["u_rated"] = nodes.u_rated
        return arr

    def _build_line_array(self, lines: LineCollection, nodes: NodeCollection) -> np.ndarray:
        """Build PGM line input array.

        :param lines: Line collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for lines.
        """
        pgm_ids = self.id_manager.register_ids("line", lines.ids)
        from_node_pgm = self.id_manager.get_pgm_ids("node", lines.from_node)
        to_node_pgm = self.id_manager.get_pgm_ids("node", lines.to_node)

        arr = pgm.initialize_array("input", "line", len(lines))
        arr["id"] = pgm_ids
        arr["from_node"] = from_node_pgm
        arr["to_node"] = to_node_pgm
        arr["from_status"] = lines.from_status
        arr["to_status"] = lines.to_status
        arr["r1"] = lines.r1
        arr["x1"] = lines.x1
        arr["c1"] = lines.c1
        arr["tan1"] = lines.tan1
        arr["i_n"] = np.where(np.isinf(lines.i_n), np.nan, lines.i_n)  # PGM uses NaN for no limit
        return arr

    def _build_transformer_array(
        self, transformers: TransformerCollection, nodes: NodeCollection
    ) -> np.ndarray:
        """Build PGM transformer input array.

        :param transformers: Transformer collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for transformers.
        """
        pgm_ids = self.id_manager.register_ids("transformer", transformers.ids)
        from_node_pgm = self.id_manager.get_pgm_ids("node", transformers.from_node)
        to_node_pgm = self.id_manager.get_pgm_ids("node", transformers.to_node)

        arr = pgm.initialize_array("input", "transformer", len(transformers))
        arr["id"] = pgm_ids
        arr["from_node"] = from_node_pgm
        arr["to_node"] = to_node_pgm
        arr["from_status"] = transformers.from_status
        arr["to_status"] = transformers.to_status
        arr["u1"] = transformers.u1
        arr["u2"] = transformers.u2
        arr["sn"] = transformers.sn
        arr["uk"] = transformers.uk
        arr["pk"] = transformers.pk
        arr["i0"] = transformers.i0
        arr["p0"] = transformers.p0
        arr["winding_from"] = transformers.winding_from
        arr["winding_to"] = transformers.winding_to
        arr["clock"] = transformers.clock
        arr["tap_side"] = transformers.tap_side
        arr["tap_pos"] = transformers.tap_pos
        arr["tap_min"] = transformers.tap_min
        arr["tap_max"] = transformers.tap_max
        arr["tap_nom"] = transformers.tap_nom
        arr["tap_size"] = transformers.tap_size
        return arr

    def _build_load_array(self, loads: LoadCollection, nodes: NodeCollection) -> np.ndarray:
        """Build PGM symmetric load input array.

        :param loads: Load collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for loads.
        """
        pgm_ids = self.id_manager.register_ids("sym_load", loads.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", loads.node)

        arr = pgm.initialize_array("input", "sym_load", len(loads))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = loads.status
        arr["type"] = loads.type
        arr["p_specified"] = loads.p_specified
        arr["q_specified"] = loads.q_specified
        return arr

    def _build_generator_array(
        self, generators: GeneratorCollection, nodes: NodeCollection
    ) -> np.ndarray:
        """Build PGM symmetric generator input array.

        :param generators: Generator collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for generators.
        """
        pgm_ids = self.id_manager.register_ids("sym_gen", generators.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", generators.node)

        arr = pgm.initialize_array("input", "sym_gen", len(generators))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = generators.status
        arr["type"] = generators.type
        arr["p_specified"] = generators.p_specified
        arr["q_specified"] = generators.q_specified
        return arr

    def _build_source_array(self, sources: SourceCollection, nodes: NodeCollection) -> np.ndarray:
        """Build PGM source input array.

        :param sources: Source collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for sources.
        """
        pgm_ids = self.id_manager.register_ids("source", sources.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", sources.node)

        arr = pgm.initialize_array("input", "source", len(sources))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = sources.status
        arr["u_ref"] = sources.u_ref
        arr["u_ref_angle"] = sources.u_ref_angle
        arr["sk"] = sources.sk
        arr["rx_ratio"] = sources.rx_ratio
        return arr

    def _build_shunt_array(self, shunts: ShuntCollection, nodes: NodeCollection) -> np.ndarray:
        """Build PGM shunt input array.

        :param shunts: Shunt collection.
        :param nodes: Node collection for ID mapping.
        :returns: PGM structured array for shunts.
        """
        pgm_ids = self.id_manager.register_ids("shunt", shunts.ids)
        node_pgm = self.id_manager.get_pgm_ids("node", shunts.node)

        arr = pgm.initialize_array("input", "shunt", len(shunts))
        arr["id"] = pgm_ids
        arr["node"] = node_pgm
        arr["status"] = shunts.status
        arr["g1"] = shunts.g1
        arr["b1"] = shunts.b1
        return arr

    def _build_voltage_sensor_array(self, sensors: VoltageSensorCollection) -> np.ndarray:
        """Build PGM voltage sensor input array.

        :param sensors: Voltage sensor collection.
        :returns: PGM structured array for voltage sensors.
        """
        pgm_ids = self.id_manager.register_ids("sym_voltage_sensor", sensors.ids)
        measured_pgm = self.id_manager.get_pgm_ids("node", sensors.measured_object)

        arr = pgm.initialize_array("input", "sym_voltage_sensor", len(sensors))
        arr["id"] = pgm_ids
        arr["measured_object"] = measured_pgm
        arr["u_measured"] = sensors.u_measured
        arr["u_sigma"] = sensors.u_sigma
        return arr

    def _build_power_sensor_array(self, sensors: PowerSensorCollection) -> np.ndarray:
        """Build PGM power sensor input array.

        :param sensors: Power sensor collection.
        :returns: PGM structured array for power sensors.
        """
        pgm_ids = self.id_manager.register_ids("sym_power_sensor", sensors.ids)

        # Map measured_terminal_type to component type for ID lookup
        # PGM MeasuredTerminalType: 0=branch_from, 1=branch_to, 2=source, 3=shunt, 4=load, 5=gen
        terminal_type_to_component = {
            0: ["line", "transformer"],  # branch_from
            1: ["line", "transformer"],  # branch_to
            2: ["source"],
            3: ["shunt"],
            4: ["sym_load"],
            5: ["sym_gen"],
        }

        # Get PGM IDs for measured objects based on their terminal type
        measured_pgm = np.zeros(len(sensors), dtype=np.int32)
        for i, (obj_id, term_type) in enumerate(
            zip(sensors.measured_object, sensors.measured_terminal_type)
        ):
            component_types = terminal_type_to_component.get(int(term_type), [])
            for comp_type in component_types:
                try:
                    measured_pgm[i] = self.id_manager.get_pgm_ids(comp_type, np.array([obj_id]))[0]
                    break
                except (ValueError, KeyError):
                    continue
            else:
                raise ValueError(
                    f"Cannot find measured_object {obj_id} for terminal_type {term_type}"
                )

        arr = pgm.initialize_array("input", "sym_power_sensor", len(sensors))
        arr["id"] = pgm_ids
        arr["measured_object"] = measured_pgm
        arr["measured_terminal_type"] = sensors.measured_terminal_type
        arr["p_measured"] = sensors.p_measured
        arr["q_measured"] = sensors.q_measured
        arr["power_sigma"] = sensors.power_sigma
        return arr

    def _build_fault_array(self, faults: FaultCollection) -> np.ndarray:
        """Build PGM fault input array.

        :param faults: Fault collection.
        :returns: PGM structured array for faults.
        """
        pgm_ids = self.id_manager.register_ids("fault", faults.ids)
        fault_object_pgm = self.id_manager.get_pgm_ids("node", faults.fault_object)

        arr = pgm.initialize_array("input", "fault", len(faults))
        arr["id"] = pgm_ids
        arr["status"] = faults.status
        arr["fault_type"] = faults.fault_type
        arr["fault_phase"] = faults.fault_phase
        arr["fault_object"] = fault_object_pgm
        arr["r_f"] = faults.r_f
        arr["x_f"] = faults.x_f
        return arr

    # =========================================================================
    # Update array building methods
    # =========================================================================

    def _build_load_update(self, loads: LoadCollection) -> np.ndarray:
        """Build PGM load update array.

        :param loads: Load collection with updated values.
        :returns: PGM structured array for load updates.
        """
        pgm_ids = self.id_manager.get_pgm_ids("sym_load", loads.ids)

        arr = pgm.initialize_array("update", "sym_load", len(loads))
        arr["id"] = pgm_ids
        arr["status"] = loads.status
        arr["p_specified"] = loads.p_specified
        arr["q_specified"] = loads.q_specified
        return arr

    def _build_generator_update(self, generators: GeneratorCollection) -> np.ndarray:
        """Build PGM generator update array.

        :param generators: Generator collection with updated values.
        :returns: PGM structured array for generator updates.
        """
        pgm_ids = self.id_manager.get_pgm_ids("sym_gen", generators.ids)

        arr = pgm.initialize_array("update", "sym_gen", len(generators))
        arr["id"] = pgm_ids
        arr["status"] = generators.status
        arr["p_specified"] = generators.p_specified
        arr["q_specified"] = generators.q_specified
        return arr

    # =========================================================================
    # Result conversion methods
    # =========================================================================

    def _convert_power_flow_result(self, result: dict) -> PowerFlowResult:
        """Convert PGM result dict to PowerFlowResult.

        :param result: PGM calculation result dictionary.
        :returns: PowerFlowResult with converted data.
        """
        # Convert node results
        node_result = result.get("node")
        nodes = NodeResult(
            ids=self.id_manager.get_movici_ids("node", node_result["id"]),
            u_pu=node_result["u_pu"],
            u_angle=node_result["u_angle"],
            u=node_result["u"],
            p=node_result["p"],
            q=node_result["q"],
        )

        # Convert line results if present
        lines = None
        if "line" in result:
            line_result = result["line"]
            lines = BranchResult(
                ids=self.id_manager.get_movici_ids("line", line_result["id"]),
                p_from=line_result["p_from"],
                q_from=line_result["q_from"],
                i_from=line_result["i_from"],
                s_from=line_result["s_from"],
                p_to=line_result["p_to"],
                q_to=line_result["q_to"],
                i_to=line_result["i_to"],
                s_to=line_result["s_to"],
                loading=line_result["loading"],
            )

        # Convert transformer results if present
        transformers = None
        if "transformer" in result:
            trafo_result = result["transformer"]
            transformers = BranchResult(
                ids=self.id_manager.get_movici_ids("transformer", trafo_result["id"]),
                p_from=trafo_result["p_from"],
                q_from=trafo_result["q_from"],
                i_from=trafo_result["i_from"],
                s_from=trafo_result["s_from"],
                p_to=trafo_result["p_to"],
                q_to=trafo_result["q_to"],
                i_to=trafo_result["i_to"],
                s_to=trafo_result["s_to"],
                loading=trafo_result["loading"],
            )

        # Convert load results if present
        loads = None
        if "sym_load" in result:
            load_result = result["sym_load"]
            loads = ApplianceResult(
                ids=self.id_manager.get_movici_ids("sym_load", load_result["id"]),
                p=load_result["p"],
                q=load_result["q"],
                i=load_result["i"],
                s=load_result["s"],
                pf=load_result["pf"],
            )

        # Convert generator results if present
        generators = None
        if "sym_gen" in result:
            gen_result = result["sym_gen"]
            generators = ApplianceResult(
                ids=self.id_manager.get_movici_ids("sym_gen", gen_result["id"]),
                p=gen_result["p"],
                q=gen_result["q"],
                i=gen_result["i"],
                s=gen_result["s"],
                pf=gen_result["pf"],
            )

        # Convert source results if present
        sources = None
        if "source" in result:
            source_result = result["source"]
            sources = ApplianceResult(
                ids=self.id_manager.get_movici_ids("source", source_result["id"]),
                p=source_result["p"],
                q=source_result["q"],
                i=source_result["i"],
                s=source_result["s"],
                pf=source_result["pf"],
            )

        return PowerFlowResult(
            nodes=nodes,
            lines=lines,
            transformers=transformers,
            loads=loads,
            generators=generators,
            sources=sources,
        )

    def _convert_short_circuit_result(
        self, result: dict, fault_ids: np.ndarray
    ) -> ShortCircuitResult:
        """Convert PGM short circuit result.

        :param result: PGM calculation result dictionary.
        :param fault_ids: Movici fault IDs.
        :returns: ShortCircuitResult with converted data.
        """
        n_faults = len(fault_ids)

        # Short circuit result is a dict with structured numpy arrays
        fault_result = result.get("fault")
        if fault_result is not None:
            i_f = fault_result["i_f"]
            i_f_angle = fault_result["i_f_angle"]
        else:
            i_f = np.zeros(n_faults)
            i_f_angle = np.zeros(n_faults)

        return ShortCircuitResult(
            fault_ids=fault_ids,
            i_f=i_f,
            i_f_angle=i_f_angle,
        )

    def _get_calculation_method(self, method: CalculationMethod):
        """Get PGM calculation method enum.

        :param method: Internal calculation method enum.
        :returns: PGM CalculationMethod enum value.
        """
        method_map = {
            CalculationMethod.NEWTON_RAPHSON: pgm.CalculationMethod.newton_raphson,
            CalculationMethod.LINEAR: pgm.CalculationMethod.linear,
            CalculationMethod.LINEAR_CURRENT: pgm.CalculationMethod.linear_current,
            CalculationMethod.ITERATIVE_CURRENT: pgm.CalculationMethod.iterative_current,
        }
        return method_map.get(method, pgm.CalculationMethod.newton_raphson)

    def close(self) -> None:
        """Clean up resources."""
        self.model = None
        self.input_data.clear()
        self.id_manager.clear()
