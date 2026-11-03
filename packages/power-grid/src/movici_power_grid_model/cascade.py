"""Power grid cascade model: short circuit -> protection trips -> power flow.

This model simulates the electrical consequences of external hazards (e.g.
flooding) that cause short circuits in the grid. Within a single simulation
timestep it:

1. Applies incoming changes (fault activations, load changes) to the network
2. Runs a short circuit calculation for the active faults
3. Trips the protection relays that see their trigger, fastest relays first
   (protection selectivity), and reruns the short circuit on the new
   topology until no further relays trip (the trip set is latching, so this
   loop is bounded by the number of relays)
4. Runs a power flow calculation on the remaining (partially de-energized)
   grid and publishes voltages, currents and per-node energized status

Three kinds of relay are modelled, all sharing the same selectivity rule:

* **branch protection** opens one side of a branch when the short-circuit
  current at that side exceeds its pick-up current
* **remote node protection** opens both sides of a branch when a monitored
  node is short-circuited, regardless of current (e.g. a transformer
  protected against faults on its secondary busbar)
* **appliance protection** disconnects a source, shunt, load or generator
  when the current through it exceeds its pick-up current

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
    Electrical_ProtectedAppliance,
    Electrical_ProtectedLine,
    Electrical_ProtectedNode,
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
    _worst_phase,
)

_PACKAGE_DIR = pathlib.Path(__file__).parent

FROM_SIDE = 0
TO_SIDE = 1
_NA_INT8 = -128  # power-grid-model sentinel for "no change" in update arrays

# PGM components that branch relays can open, and appliance relays can disconnect
_BRANCH_COMPONENTS = ("line", "transformer")
_APPLIANCE_COMPONENTS = ("source", "shunt", "sym_load", "sym_gen", "asym_load", "asym_gen")


# =========================================================================
# Entity groups
# =========================================================================
#
# The cascade model upgrades the branch status attributes from OPT to
# OPT|PUB (it publishes breaker positions after trips; OPT already subscribes
# to external switching), appliance status likewise (appliance relays
# disconnect them), fault status from OPT to SUB (it is driven by an
# external fault activation model) and adds an energized flag to nodes.


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


class CascadeLoadEntity(ds.ElectricalLoadEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


class CascadeGeneratorEntity(ds.ElectricalGeneratorEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


class CascadeAsymLoadEntity(ds.ElectricalAsymLoadEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


class CascadeAsymGeneratorEntity(ds.ElectricalAsymGeneratorEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


class CascadeSourceEntity(ds.ElectricalSourceEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


class CascadeShuntEntity(ds.ElectricalShuntEntity):
    status = field(Electrical_Status, flags=OPT | PUB)


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


class ElectricalRemoteNodeProtectionEntity(EntityGroup):
    """Remote node protection relay.

    Opens both sides of a branch when a monitored node is short-circuited
    (has an active fault while still energized), regardless of the current.
    Typical use: a transformer that must be disconnected on a fault at its
    secondary busbar.
    """

    __entity_name__ = "electrical_remote_node_protection_entities"

    # Input attributes
    pick_up_time = field(Electrical_PickUpTime, flags=OPT)
    protected_node = field(Electrical_ProtectedNode, flags=INIT)
    protected_line = field(Electrical_ProtectedLine, flags=INIT)

    # Output attributes
    tripped = field(Electrical_Tripped, flags=PUB)


class ElectricalApplianceProtectionEntity(EntityGroup):
    """Appliance protection relay.

    Disconnects a source, shunt, load or generator when the short-circuit
    current through it exceeds ``pick_up_current``. Loads and generators
    carry no short-circuit current in power-grid-model, so in practice this
    protects sources and shunts.
    """

    __entity_name__ = "electrical_appliance_protection_entities"

    # Input attributes
    pick_up_current = field(Electrical_PickUpCurrent, flags=INIT)
    pick_up_time = field(Electrical_PickUpTime, flags=OPT)
    protected_appliance = field(Electrical_ProtectedAppliance, flags=INIT)

    # Output attributes
    tripped = field(Electrical_Tripped, flags=PUB)


# =========================================================================
# Relay groups
# =========================================================================


class _RelayGroup:
    """One kind of protection relay with the shared latching bookkeeping.

    Subclasses decide which relays see their trigger in a short-circuit
    result (:meth:`candidates`) and what a trip does (:meth:`trip`). The
    model picks the fastest candidates across all groups.
    """

    kind: str

    def __init__(self, model: Model, entity_group: EntityGroup):
        self.model = model
        self.eg = entity_group
        n = len(entity_group)
        self.tripped = np.zeros(n, dtype=bool)
        if n and entity_group.pick_up_time.is_initialized():
            self.pick_up_time = entity_group.pick_up_time.array.copy()
        else:
            self.pick_up_time = np.zeros(n)

    def __len__(self):
        return len(self.eg)

    def candidates(self, sc_result: dict) -> np.ndarray:
        """Boolean mask of relays that see their trigger (tripped or not)."""
        raise NotImplementedError

    def trip(self, relay_idx: np.ndarray, moment: Moment):
        """Perform the switching action of the given relays."""
        raise NotImplementedError

    def record(self, trip_now: np.ndarray):
        self.tripped |= trip_now
        self.eg.tripped[np.flatnonzero(trip_now)] = 1


class _BranchRelays(_RelayGroup):
    kind = "branch"

    def candidates(self, sc_result):
        currents = _branch_currents(sc_result)
        prot = self.eg
        measured = np.zeros(len(prot))
        for i, (branch_id, side) in enumerate(
            zip(prot.protected_line.array, prot.protected_side.array)
        ):
            i_from, i_to = currents.get(int(branch_id), (0.0, 0.0))
            measured[i] = i_to if side == TO_SIDE else i_from
        return measured > prot.pick_up_current.array

    def trip(self, relay_idx, moment):
        branch_ids = self.eg.protected_line.array[relay_idx]
        sides = self.eg.protected_side.array[relay_idx]
        self.model.logger.info(
            f"t={moment.timestamp}: branch protection trips on branches "
            f"{branch_ids.tolist()} (sides {sides.tolist()})"
        )
        self.model.open_branches(branch_ids, sides == FROM_SIDE, sides == TO_SIDE)


class _RemoteNodeRelays(_RelayGroup):
    kind = "remote node"

    def candidates(self, sc_result):
        shorted = self.model.short_circuited_nodes(sc_result)
        return np.isin(self.eg.protected_node.array, shorted)

    def trip(self, relay_idx, moment):
        branch_ids = self.eg.protected_line.array[relay_idx]
        nodes = self.eg.protected_node.array[relay_idx]
        self.model.logger.info(
            f"t={moment.timestamp}: remote node protection on nodes {nodes.tolist()} "
            f"opens branches {branch_ids.tolist()}"
        )
        both = np.ones(len(branch_ids), dtype=bool)
        self.model.open_branches(branch_ids, both, both)


class _ApplianceRelays(_RelayGroup):
    kind = "appliance"

    def candidates(self, sc_result):
        currents = _appliance_currents(sc_result)
        measured = np.array([currents.get(int(a), 0.0) for a in self.eg.protected_appliance.array])
        return measured > self.eg.pick_up_current.array

    def trip(self, relay_idx, moment):
        appliance_ids = self.eg.protected_appliance.array[relay_idx]
        self.model.logger.info(
            f"t={moment.timestamp}: appliance protection disconnects {appliance_ids.tolist()}"
        )
        self.model.disconnect_appliances(appliance_ids)


def _branch_currents(sc_result: dict) -> t.Dict[int, t.Tuple[float, float]]:
    """Map branch id -> (i_from, i_to), worst phase, from SC results."""
    out = {}
    for component in _BRANCH_COMPONENTS:
        res = sc_result.get(component)
        if res is None:
            continue
        i_from = _worst_phase(res["i_from"])
        i_to = _worst_phase(res["i_to"])
        for i, branch_id in enumerate(res["id"]):
            out[int(branch_id)] = (float(i_from[i]), float(i_to[i]))
    return out


def _appliance_currents(sc_result: dict) -> t.Dict[int, float]:
    """Map appliance id -> current, worst phase, from SC results."""
    out = {}
    for component in _APPLIANCE_COMPONENTS:
        res = sc_result.get(component)
        if res is None:
            continue
        current = _worst_phase(res["i"])
        for i, appliance_id in enumerate(res["id"]):
            out[int(appliance_id)] = float(current[i])
    return out


# =========================================================================
# Model
# =========================================================================


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
        self.branch_protection: t.Optional[ElectricalBranchProtectionEntity] = None
        self.remote_node_protection: t.Optional[ElectricalRemoteNodeProtectionEntity] = None
        self.appliance_protection: t.Optional[ElectricalApplianceProtectionEntity] = None
        self.relays: t.List[_RelayGroup] = []
        self.logger: t.Optional[logging.Logger] = None

        self.calc_method = _CALC_METHOD_MAP.get(
            self.config.get("algorithm", "newton_raphson"),
            CalculationMethod.NEWTON_RAPHSON,
        )
        self.symmetric = self.config.get("symmetric", True)
        self.per_phase_output = self.config.get("per_phase_output", False)
        self.max_iterations = self.config.get("max_cascade_iterations", 20)
        tap_str = self.config.get("tap_changing")
        self.tap_changing_strategy = _TAP_CHANGING_STRATEGIES.get(tap_str) if tap_str else None

    def setup(self, state: TrackedState, logger: logging.Logger, **_):
        self.logger = logger
        name = self.config["dataset"]

        def register(entity_cls, entity_name, optional=True):
            return state.register_entity_group(
                name, entity_cls(name=entity_name, optional=optional)
            )

        self.dataset = PowerGridNetwork(
            nodes=register(CascadeNodeEntity, "electrical_node_entities", optional=False),
            virtual_nodes=register(CascadeVirtualNodeEntity, "electrical_virtual_node_entities"),
            lines=register(CascadeLineEntity, "electrical_line_entities"),
            cables=register(CascadeCableEntity, "electrical_cable_entities"),
            links=register(CascadeLinkEntity, "electrical_link_entities"),
            transformers=register(CascadeTransformerEntity, "electrical_transformer_entities"),
            three_winding_transformers=register(
                ds.ElectricalThreeWindingTransformerEntity,
                "electrical_three_winding_transformer_entities",
            ),
            loads=register(CascadeLoadEntity, "electrical_load_entities"),
            generators=register(CascadeGeneratorEntity, "electrical_generator_entities"),
            asym_loads=register(CascadeAsymLoadEntity, "electrical_asym_load_entities"),
            asym_generators=register(
                CascadeAsymGeneratorEntity, "electrical_asym_generator_entities"
            ),
            sources=register(CascadeSourceEntity, "electrical_source_entities"),
            shunts=register(CascadeShuntEntity, "electrical_shunt_entities"),
            voltage_sensors=register(
                ds.ElectricalVoltageSensorEntity, "electrical_voltage_sensor_entities"
            ),
            power_sensors=register(
                ds.ElectricalPowerSensorEntity, "electrical_power_sensor_entities"
            ),
            current_sensors=register(
                ds.ElectricalCurrentSensorEntity, "electrical_current_sensor_entities"
            ),
            faults=register(CascadeFaultEntity, "electrical_fault_entities"),
            tap_regulators=register(
                ds.ElectricalTapRegulatorEntity, "electrical_tap_regulator_entities"
            ),
        )
        self.branch_protection = register(
            ElectricalBranchProtectionEntity, "electrical_branch_protection_entities"
        )
        self.remote_node_protection = register(
            ElectricalRemoteNodeProtectionEntity, "electrical_remote_node_protection_entities"
        )
        self.appliance_protection = register(
            ElectricalApplianceProtectionEntity, "electrical_appliance_protection_entities"
        )
        self.wrapper = PowerGridWrapper()
        self.wrapper.per_phase_output = self.per_phase_output

    def initialize(self, state: TrackedState):
        self._ensure_pub_attributes_initialized()
        self.wrapper.initialize(self.dataset)
        # The cascade runs both calculations every timestamp, so both must hold
        self.wrapper.validate(CalculationType.SHORT_CIRCUIT)
        self.wrapper.validate(CalculationType.POWER_FLOW, self.symmetric)

        self.relays = [
            _BranchRelays(self, self.branch_protection),
            _RemoteNodeRelays(self, self.remote_node_protection),
            _ApplianceRelays(self, self.appliance_protection),
        ]
        n_relays = sum(len(group) for group in self.relays)

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
            trips = self._select_trips(sc_result)
            if not trips:
                break
            for group, trip_now in trips:
                group.trip(np.flatnonzero(trip_now), moment)
                group.record(trip_now)
        else:
            self.logger.warning(
                f"Protection cascade did not converge within {self.max_iterations} iterations"
            )
        return first_sc

    def _select_trips(self, sc_result: dict) -> t.List[t.Tuple[_RelayGroup, np.ndarray]]:
        """Determine which relays trip in this round.

        Among all untripped relays of any kind that see their trigger, only
        those with the lowest ``pick_up_time`` operate (selectivity): faster
        relays may clear the fault so that slower (backup) relays never see
        the overcurrent again.

        :returns: ``(relay group, boolean relay mask)`` pairs; empty if no
            relay trips.
        """
        candidates = []
        for group in self.relays:
            if not len(group):
                continue
            mask = group.candidates(sc_result) & ~group.tripped
            if np.any(mask):
                candidates.append((group, mask))
        if not candidates:
            return []
        fastest = min(np.min(group.pick_up_time[mask]) for group, mask in candidates)
        trips = []
        for group, mask in candidates:
            trip_now = mask & (group.pick_up_time == fastest)
            if np.any(trip_now):
                trips.append((group, trip_now))
        return trips

    def short_circuited_nodes(self, sc_result: dict) -> np.ndarray:
        """Ids of nodes with an active fault that is still being fed.

        A fault on an already isolated island draws no current and does not
        trigger remote node protection.
        """
        faults = self.dataset.faults
        if not len(faults) or not faults.status.is_initialized():
            return np.array([], dtype=int)
        faulted = faults.fault_object_id.array[faults.status.array == 1]
        node_result = sc_result.get("node")
        if node_result is None:
            return np.array([], dtype=int)
        energized = node_result["id"][node_result["energized"] == 1]
        return np.intersect1d(faulted, energized)

    # =====================================================================
    # Switching actions
    # =====================================================================

    def open_branches(self, branch_ids: np.ndarray, open_from: np.ndarray, open_to: np.ndarray):
        """Open the given sides of the given branches.

        Updates the PGM model (so subsequent calculations see the new
        topology) and the Movici status attributes (published downstream).
        """
        for component in _BRANCH_COMPONENTS:
            comp_input = self.wrapper.input_data.get(component)
            if comp_input is None:
                continue
            in_component = np.isin(branch_ids, comp_input["id"])
            if not np.any(in_component):
                continue
            arr = pgm.initialize_array("update", component, int(np.sum(in_component)))
            arr["id"] = branch_ids[in_component]
            arr["from_status"] = np.where(open_from[in_component], 0, _NA_INT8).astype(np.int8)
            arr["to_status"] = np.where(open_to[in_component], 0, _NA_INT8).astype(np.int8)
            self.wrapper.model.update(update_data={component: arr})

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
            from_idx = indices[open_from[mask]]
            to_idx = indices[open_to[mask]]
            if len(from_idx):
                eg.from_status[from_idx] = 0
            if len(to_idx):
                eg.to_status[to_idx] = 0

    def disconnect_appliances(self, appliance_ids: np.ndarray):
        """Switch the given sources / shunts / loads / generators off.

        Updates the PGM model and publishes ``electrical.status = 0``.
        """
        for component in _APPLIANCE_COMPONENTS:
            comp_input = self.wrapper.input_data.get(component)
            if comp_input is None:
                continue
            in_component = np.isin(appliance_ids, comp_input["id"])
            if not np.any(in_component):
                continue
            arr = pgm.initialize_array("update", component, int(np.sum(in_component)))
            arr["id"] = appliance_ids[in_component]
            arr["status"] = 0
            self.wrapper.model.update(update_data={component: arr})

        groups = (
            self.dataset.sources,
            self.dataset.shunts,
            self.dataset.loads,
            self.dataset.generators,
            self.dataset.asym_loads,
            self.dataset.asym_generators,
        )
        for eg in groups:
            if not len(eg):
                continue
            mask = np.isin(appliance_ids, eg.index.ids)
            if not np.any(mask):
                continue
            eg.status[eg.get_indices(appliance_ids[mask])] = 0

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
        entity_groups += [
            self.branch_protection,
            self.remote_node_protection,
            self.appliance_protection,
        ]
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
