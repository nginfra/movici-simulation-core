"""Power grid cascade model: short circuit -> protection trips -> power flow.

This model simulates the electrical consequences of external hazards (e.g.
flooding) that cause short circuits in the grid. Within a single simulation
timestep it:

1. Applies incoming changes (fault activations, load changes) to the network
2. Runs a short circuit calculation for the active faults
3. Trips protection relays whose pick-up current is exceeded, fastest relays
   first (protection selectivity), and reruns the short circuit on the new
   topology until no further relays trip (the trip set is latching, so this
   loop is bounded by the number of relays)
4. Runs a power flow calculation on the remaining (partially de-energized)
   grid and publishes voltages, currents and per-node energized status

The whole short-circuit/trip sequence happens inside one ``update()`` call
because protection operates on sub-second timescales that cannot be
represented on Movici's integer-second timeline: which relay trips first
determines which relays trip at all (selectivity), so the ordering must be
resolved internally.

Faults are activated by an external model (e.g.
:class:`~movici_power_grid_model.fault_activation.FaultActivationModel`)
publishing ``electrical.status`` on ``electrical_fault_entities``.
"""

from __future__ import annotations

import dataclasses
import logging
import pathlib
import typing as t

import numpy as np
import power_grid_model as pgm

from movici_simulation_core.base_models.tracked_model import TrackedModel
from movici_simulation_core.core.attribute import INIT, OPT, PUB, PUBLISH, SUB, SUBSCRIBE, field
from movici_simulation_core.core.entity_group import EntityGroup
from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import attributes_from_dict
from movici_simulation_core.core.state import TrackedState

from . import attributes
from . import dataset as ds
from .attributes import (
    Electrical_Energized,
    Electrical_FromStatus,
    Electrical_PickUpCurrent,
    Electrical_PickUpTime,
    Electrical_ProtectedLine,
    Electrical_ProtectedSide,
    Electrical_Status,
    Electrical_ToStatus,
    Electrical_Tripped,
)
from .dataset import PowerGridNetwork
from .model import _CALC_METHOD_MAP
from .network_wrapper import (
    _TAP_CHANGING_STRATEGIES,
    CalculationMethod,
    CalculationType,
    PowerGridWrapper,
)

_PACKAGE_DIR = pathlib.Path(__file__).parent

FROM_SIDE = 0
TO_SIDE = 1
_NA_INT8 = -128  # power-grid-model sentinel for "no change" in update arrays


def _worst_phase(arr: np.ndarray) -> np.ndarray:
    """Reduce a per-phase result array ``(n, 3)`` to the worst (maximum) phase.

    Used for trip decisions: a relay picks up on the highest phase current.
    Symmetric results ``(n,)`` are returned as-is.
    """
    if arr.ndim == 2:
        return np.max(arr, axis=1)
    return arr


# =========================================================================
# Entity groups
# =========================================================================
#
# The cascade model upgrades the branch status attributes from OPT to
# OPT|PUB (it publishes breaker positions after trips), fault status from
# OPT to SUB (it is driven by an external fault activation model) and adds
# an energized flag to nodes.


class CascadeNodeEntity(ds.ElectricalNodeEntity):
    energized = field(Electrical_Energized, flags=PUB)


class CascadeVirtualNodeEntity(ds.ElectricalVirtualNodeEntity):
    energized = field(Electrical_Energized, flags=PUB)


class CascadeLineEntity(ds.ElectricalLineEntity):
    from_status = field(Electrical_FromStatus, flags=OPT | PUB)
    to_status = field(Electrical_ToStatus, flags=OPT | PUB)


class CascadeCableEntity(ds.ElectricalCableEntity):
    from_status = field(Electrical_FromStatus, flags=OPT | PUB)
    to_status = field(Electrical_ToStatus, flags=OPT | PUB)


class CascadeLinkEntity(ds.ElectricalLinkEntity):
    from_status = field(Electrical_FromStatus, flags=OPT | PUB)
    to_status = field(Electrical_ToStatus, flags=OPT | PUB)


class CascadeTransformerEntity(ds.ElectricalTransformerEntity):
    from_status = field(Electrical_FromStatus, flags=OPT | PUB)
    to_status = field(Electrical_ToStatus, flags=OPT | PUB)


class CascadeFaultEntity(ds.ElectricalFaultEntity):
    status = field(Electrical_Status, flags=SUB)


class ElectricalBranchProtectionEntity(EntityGroup):
    """Branch protection relay.

    Monitors the short-circuit current at one side of a branch and opens
    that side when the current exceeds ``pick_up_current``. Relays with the
    lowest ``pick_up_time`` operate first (selectivity).
    """

    __entity_name__ = "electrical_branch_protection_entities"

    # Input attributes
    pick_up_current = field(Electrical_PickUpCurrent, flags=INIT)
    pick_up_time = field(Electrical_PickUpTime, flags=OPT)
    protected_line = field(Electrical_ProtectedLine, flags=INIT)
    protected_side = field(Electrical_ProtectedSide, flags=INIT)

    # Output attributes
    tripped = field(Electrical_Tripped, flags=PUB)


class Model(TrackedModel, name="power_grid_cascade"):
    """Short circuit -> protection -> power flow cascade model.

    Configuration:

    .. code-block:: json

        {
            "name": "grid_cascade",
            "type": "power_grid_cascade",
            "dataset": "power_grid_the_hague",
            "algorithm": "newton_raphson",
            "max_cascade_iterations": 20
        }
    """

    __model_config_schema__ = _PACKAGE_DIR / "power_grid_cascade.json"
    auto_reset = PUBLISH

    @classmethod
    def get_schema_attributes(cls):
        return attributes_from_dict(vars(attributes))

    def __init__(self, model_config: dict):
        super().__init__(model_config)
        self.wrapper: t.Optional[PowerGridWrapper] = None
        self.dataset: t.Optional[PowerGridNetwork] = None
        self.protection: t.Optional[ElectricalBranchProtectionEntity] = None
        self.logger: t.Optional[logging.Logger] = None

        self.calc_method = _CALC_METHOD_MAP.get(
            self.config.get("algorithm", "newton_raphson"),
            CalculationMethod.NEWTON_RAPHSON,
        )
        self.symmetric = self.config.get("symmetric", True)
        self.max_iterations = self.config.get("max_cascade_iterations", 20)
        tap_str = self.config.get("tap_changing")
        self.tap_changing_strategy = _TAP_CHANGING_STRATEGIES.get(tap_str) if tap_str else None

        # Relay bookkeeping, built in initialize()
        self._tripped: t.Optional[np.ndarray] = None
        self._pick_up_time: t.Optional[np.ndarray] = None

    def setup(self, state: TrackedState, logger: logging.Logger, **_):
        self.logger = logger
        name = self.config["dataset"]

        self.dataset = PowerGridNetwork(
            nodes=state.register_entity_group(
                name, CascadeNodeEntity(name="electrical_node_entities")
            ),
            virtual_nodes=state.register_entity_group(
                name,
                CascadeVirtualNodeEntity(name="electrical_virtual_node_entities", optional=True),
            ),
            lines=state.register_entity_group(
                name, CascadeLineEntity(name="electrical_line_entities", optional=True)
            ),
            cables=state.register_entity_group(
                name, CascadeCableEntity(name="electrical_cable_entities", optional=True)
            ),
            links=state.register_entity_group(
                name, CascadeLinkEntity(name="electrical_link_entities", optional=True)
            ),
            transformers=state.register_entity_group(
                name,
                CascadeTransformerEntity(name="electrical_transformer_entities", optional=True),
            ),
            three_winding_transformers=state.register_entity_group(
                name,
                ds.ElectricalThreeWindingTransformerEntity(
                    name="electrical_three_winding_transformer_entities", optional=True
                ),
            ),
            loads=state.register_entity_group(
                name, ds.ElectricalLoadEntity(name="electrical_load_entities", optional=True)
            ),
            generators=state.register_entity_group(
                name,
                ds.ElectricalGeneratorEntity(name="electrical_generator_entities", optional=True),
            ),
            sources=state.register_entity_group(
                name, ds.ElectricalSourceEntity(name="electrical_source_entities", optional=True)
            ),
            shunts=state.register_entity_group(
                name, ds.ElectricalShuntEntity(name="electrical_shunt_entities", optional=True)
            ),
            voltage_sensors=state.register_entity_group(
                name,
                ds.ElectricalVoltageSensorEntity(
                    name="electrical_voltage_sensor_entities", optional=True
                ),
            ),
            power_sensors=state.register_entity_group(
                name,
                ds.ElectricalPowerSensorEntity(
                    name="electrical_power_sensor_entities", optional=True
                ),
            ),
            current_sensors=state.register_entity_group(
                name,
                ds.ElectricalCurrentSensorEntity(
                    name="electrical_current_sensor_entities", optional=True
                ),
            ),
            faults=state.register_entity_group(
                name, CascadeFaultEntity(name="electrical_fault_entities", optional=True)
            ),
            tap_regulators=state.register_entity_group(
                name,
                ds.ElectricalTapRegulatorEntity(
                    name="electrical_tap_regulator_entities", optional=True
                ),
            ),
        )
        self.protection = state.register_entity_group(
            name,
            ElectricalBranchProtectionEntity(
                name="electrical_branch_protection_entities", optional=True
            ),
        )
        self.wrapper = PowerGridWrapper()

    def initialize(self, state: TrackedState):
        self._ensure_pub_attributes_initialized()
        self.wrapper.initialize(self.dataset)
        # The cascade runs both calculations every timestamp, so both must hold
        self.wrapper.validate(CalculationType.SHORT_CIRCUIT)
        self.wrapper.validate(CalculationType.POWER_FLOW, self.symmetric)

        n_relays = len(self.protection)
        self._tripped = np.zeros(n_relays, dtype=bool)
        if n_relays and self.protection.pick_up_time.is_initialized():
            self._pick_up_time = self.protection.pick_up_time.array.copy()
        else:
            self._pick_up_time = np.zeros(n_relays)

        self.logger.info(
            f"Power grid cascade network built with {len(self.dataset.nodes)} nodes, "
            f"{len(self.dataset.faults)} fault locations and {n_relays} protection relays"
        )

    def update(self, state: TrackedState, moment: Moment) -> t.Optional[Moment]:
        # Apply incoming changes (fault activations, load changes) to PGM
        self.wrapper.process_changes()
        state.reset_tracked_changes(SUBSCRIBE)

        # Short circuit / protection cascade on the current topology
        sc_result = self._run_cascade(moment)
        if sc_result is not None:
            # Publishes fault currents; node/branch values are overwritten by
            # the power flow results below
            self.wrapper.write_results(sc_result)

        # Power flow on the remaining grid
        pf_result = self.wrapper.calculate_power_flow(
            method=self.calc_method,
            symmetric=self.symmetric,
            tap_changing_strategy=self.tap_changing_strategy,
        )
        self.wrapper.write_results(pf_result)
        self._write_energized(pf_result)
        return None

    # =====================================================================
    # Cascade loop
    # =====================================================================

    def _run_cascade(self, moment: Moment) -> t.Optional[dict]:
        """Run the short-circuit/trip loop.

        Returns the first-round SC result — the prospective fault currents on
        the pre-trip topology, i.e. the currents the protection responded to.
        Later rounds are only used for trip decisions: once a fault is
        isolated its current drops to zero, which would make the published
        fault currents meaningless.

        Returns ``None`` when no faults are active (no SC was run).
        """
        faults = self.dataset.faults
        if not len(faults) or not faults.status.is_initialized():
            return None
        if not np.any(faults.status.array == 1):
            return None

        first_sc = None
        for _ in range(self.max_iterations):
            sc_result = self.wrapper.calculate_short_circuit()
            if first_sc is None:
                first_sc = sc_result
            trip_now = self._select_trips(sc_result)
            if trip_now is None:
                break
            self._apply_trips(trip_now, moment)
        else:
            self.logger.warning(
                f"Protection cascade did not converge within {self.max_iterations} iterations"
            )
        return first_sc

    def _select_trips(self, sc_result: dict) -> t.Optional[np.ndarray]:
        """Determine which relays trip in this round.

        Among all untripped relays whose branch current exceeds the pick-up
        current, only those with the lowest ``pick_up_time`` operate
        (selectivity): faster relays may clear the fault so that slower
        (backup) relays never see the overcurrent again.

        :returns: boolean relay mask, or ``None`` if no relay trips.
        """
        if self.protection is None or not len(self.protection):
            return None

        currents = self._branch_currents(sc_result)
        prot = self.protection
        branch_ids = prot.protected_line.array
        sides = prot.protected_side.array
        pick_up = prot.pick_up_current.array

        measured = np.zeros(len(prot))
        for i, (branch_id, side) in enumerate(zip(branch_ids, sides)):
            i_from, i_to = currents.get(int(branch_id), (0.0, 0.0))
            measured[i] = i_to if side == TO_SIDE else i_from

        candidates = ~self._tripped & (measured > pick_up)
        if not np.any(candidates):
            return None
        fastest = np.min(self._pick_up_time[candidates])
        return candidates & (self._pick_up_time == fastest)

    @staticmethod
    def _branch_currents(sc_result: dict) -> t.Dict[int, t.Tuple[float, float]]:
        """Map branch id -> (i_from, i_to), worst phase, from SC results."""
        out = {}
        for component in ("line", "transformer"):
            res = sc_result.get(component)
            if res is None:
                continue
            i_from = _worst_phase(res["i_from"])
            i_to = _worst_phase(res["i_to"])
            for i, branch_id in enumerate(res["id"]):
                out[int(branch_id)] = (float(i_from[i]), float(i_to[i]))
        return out

    def _apply_trips(self, trip_now: np.ndarray, moment: Moment):
        """Open the protected side of each tripping relay's branch.

        Updates the PGM model (so subsequent calculations see the new
        topology), the Movici status attributes (published downstream) and
        the relay bookkeeping.
        """
        prot = self.protection
        relay_idx = np.flatnonzero(trip_now)
        branch_ids = prot.protected_line.array[relay_idx]
        sides = prot.protected_side.array[relay_idx]

        self.logger.info(
            f"t={moment.timestamp}: protection trips on branches "
            f"{branch_ids.tolist()} (sides {sides.tolist()})"
        )

        for component in ("line", "transformer"):
            comp_input = self.wrapper.input_data.get(component)
            if comp_input is None:
                continue
            in_component = np.isin(branch_ids, comp_input["id"])
            if not np.any(in_component):
                continue
            arr = pgm.initialize_array("update", component, int(np.sum(in_component)))
            arr["id"] = branch_ids[in_component]
            comp_sides = sides[in_component]
            arr["from_status"] = np.where(comp_sides == FROM_SIDE, 0, _NA_INT8).astype(np.int8)
            arr["to_status"] = np.where(comp_sides == TO_SIDE, 0, _NA_INT8).astype(np.int8)
            self.wrapper.model.update(update_data={component: arr})

        self._publish_branch_status(branch_ids, sides)
        self._tripped |= trip_now
        prot.tripped[relay_idx] = 1

    def _publish_branch_status(self, branch_ids: np.ndarray, sides: np.ndarray):
        """Write opened breaker positions to the branch entity groups."""
        groups = (
            self.dataset.lines,
            self.dataset.cables,
            self.dataset.links,
            self.dataset.transformers,
        )
        for eg in groups:
            if not len(eg):
                continue
            mask = np.isin(branch_ids, eg.index.ids)
            if not np.any(mask):
                continue
            indices = eg.get_indices(branch_ids[mask])
            group_sides = sides[mask]
            from_idx = indices[group_sides == FROM_SIDE]
            to_idx = indices[group_sides == TO_SIDE]
            if len(from_idx):
                eg.from_status[from_idx] = 0
            if len(to_idx):
                eg.to_status[to_idx] = 0

    # =====================================================================
    # Result publishing
    # =====================================================================

    def _write_energized(self, pf_result: dict):
        node_result = pf_result.get("node")
        if node_result is None:
            return
        for eg in (self.dataset.nodes, self.dataset.virtual_nodes):
            if not len(eg):
                continue
            mask = np.isin(node_result["id"], eg.index.ids)
            if not np.any(mask):
                continue
            indices = eg.get_indices(node_result["id"][mask])
            eg.energized[indices] = node_result["energized"][mask]

    def _ensure_pub_attributes_initialized(self):
        """Ensure all PUB attributes have their arrays allocated.

        PUB-only attributes may not receive data during init loading. They
        must be initialized before the framework checks their ``.changed``
        property during ``generate_update``.
        """
        entity_groups = [getattr(self.dataset, f.name) for f in dataclasses.fields(self.dataset)]
        entity_groups.append(self.protection)
        for entity in entity_groups:
            size = len(entity)
            for attr_name in entity.attributes:
                attr = getattr(entity, attr_name)
                if attr.flags & PUBLISH and not attr.has_data():
                    attr.initialize(size)

    def shutdown(self, state: TrackedState):
        if self.wrapper is not None:
            self.wrapper.close()
            self.wrapper = None
