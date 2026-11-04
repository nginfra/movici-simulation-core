"""Reference cases for the power grid models.

Two small grids, a balanced medium voltage grid and a low voltage grid with
single-phase loads, are run through ``power_grid_calculation`` and
``power_grid_cascade`` and compared with results of an earlier Movici power
grid implementation. The fixtures in ``data/`` hold, per grid, the dataset,
an update applied at t=1 and the expected results in the attribute names of
this package.

The reference values were produced by a different solver, so the comparison
uses physical tolerances: voltages within 1 V, powers within 1 kW / 1 kVAr
(the reference values are rounded to kW) and currents within 1 A. Loading in
the expected results follows the current-based definition of
power-grid-model, computed from the reference currents and rated currents.
"""

import copy
import dataclasses
import json
import pathlib

import numpy as np
import pytest

from movici_power_grid_model import CascadeModel, Model
from movici_power_grid_model.attributes import PowerGridAttributes
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.testing.model_tester import ModelTester

DATA = pathlib.Path(__file__).parent / "data"
FAULT_ID_OFFSET = 2000

U_TOL = 1.0  # V
PQ_TOL = 1000.0  # W / VAr
I_TOL = 1.0  # A

NODE_TOLERANCES = {
    "electrical.voltage": U_TOL,
    "electrical.voltage_pu": 1e-4,
    "electrical.voltage_angle": 1e-3,
}
BRANCH_TOLERANCES = {
    "electrical.power_from": PQ_TOL,
    "electrical.power_to": PQ_TOL,
    "electrical.reactive_power_from": PQ_TOL,
    "electrical.reactive_power_to": PQ_TOL,
    "electrical.current_from": I_TOL,
    "electrical.current_to": I_TOL,
    "electrical.loading": 1e-3,
}
APPLIANCE_TOLERANCES = {
    "electrical.active_power": PQ_TOL,
    "electrical.reactive_power": PQ_TOL,
    "electrical.current": I_TOL,
    "electrical.apparent_power": PQ_TOL,
    "electrical.power_factor": 1e-3,
}
BRANCH_GROUPS = (
    "electrical_cable_entities",
    "electrical_line_entities",
    "electrical_link_entities",
    "electrical_transformer_entities",
)
APPLIANCE_GROUPS = (
    "electrical_load_entities",
    "electrical_generator_entities",
    "electrical_source_entities",
    "electrical_shunt_entities",
)
PROTECTION_GROUPS = (
    "electrical_branch_protection_entities",
    "electrical_appliance_protection_entities",
    "electrical_remote_node_protection_entities",
)


def load(name):
    return json.loads((DATA / f"{name}.json").read_text())


def apply_update(dataset, update):
    """Return a copy of ``dataset`` with an update dict applied by id."""
    out = copy.deepcopy(dataset)
    for group, values in update.items():
        target = out["data"][group]
        position = {i: n for n, i in enumerate(target["id"])}
        for attr, column in values.items():
            if attr == "id":
                continue
            for i, value in zip(values["id"], column):
                if value is not None:
                    target[attr][position[i]] = value
    return out


def by_id(group, attr):
    return dict(zip(group["id"], group[attr]))


def model_state(tester):
    """All entity groups of the model as ``{group name: {attr: {id: value}}}``.

    Published results only carry changed values, so a case that applies an
    update at t=1 compares against the model's state instead.
    """
    dataset = tester.model.dataset
    state = {}
    for field in dataclasses.fields(dataset):
        eg = getattr(dataset, field.name)
        if not len(eg):
            continue
        ids = eg.index.ids.tolist()
        group = state.setdefault(eg.__entity_name__, {})
        for name, field in eg.attributes.items():
            attr = getattr(eg, name)
            if attr.has_data():
                group[field.spec.name] = dict(zip(ids, attr.array.tolist()))
    return state


def assert_matches(got, expected, tolerances, label, skip_ids=()):
    """Compare ``{attr: {id: value}}`` with an expected group within tolerances."""
    for attr, tol in tolerances.items():
        if attr not in expected:
            continue
        reference = by_id(expected, attr)
        for i, ref in reference.items():
            if i in skip_ids:
                continue
            assert abs(got[attr][i] - ref) < tol, f"{label} {attr} id {i}: {got[attr][i]} != {ref}"


def assert_state_matches(state, expected, skip_angle_ids=()):
    nodes = expected["electrical_node_entities"]
    assert_matches(
        state["electrical_node_entities"],
        {k: v for k, v in nodes.items() if k != "electrical.voltage_angle"},
        NODE_TOLERANCES,
        "node",
    )
    assert_matches(
        state["electrical_node_entities"],
        nodes,
        {"electrical.voltage_angle": NODE_TOLERANCES["electrical.voltage_angle"]},
        "node",
        skip_ids=skip_angle_ids,
    )
    for group in BRANCH_GROUPS:
        if group in expected:
            assert_matches(state[group], expected[group], BRANCH_TOLERANCES, group)
    for group in APPLIANCE_GROUPS:
        if group in expected:
            assert_matches(state[group], expected[group], APPLIANCE_TOLERANCES, group)


@pytest.fixture
def schema():
    schema = AttributeSchema()
    schema.use(PowerGridAttributes)
    return schema


def power_flow_config(dataset, **options):
    return {
        "name": "pg",
        "type": "power_grid_calculation",
        "dataset": dataset["name"],
        **options,
    }


def run_power_flow(schema, dataset, update=None, **options):
    """Run t=0 and, when given, ``update`` at t=1. Returns the model state."""
    name = dataset["name"]
    with ModelTester(Model(power_flow_config(dataset, **options)), schema=schema) as tester:
        tester.add_init_data(name, dataset)
        tester.initialize()
        tester.update(0, None)
        if update is not None:
            tester.new_time(1)
            tester.update(1, {name: update})
        return model_state(tester)


def run_cascade(schema, dataset, fault_nodes=(), update=None):
    """Run ``power_grid_cascade``: t=0 as given, t=1 with faults activated
    (and ``update`` applied). Returns the published results of both steps."""
    name = dataset["name"]
    cfg = {"name": "pg", "type": "power_grid_cascade", "dataset": name}
    data = dict(update or {})
    if fault_nodes:
        ids = [FAULT_ID_OFFSET + n for n in fault_nodes]
        data["electrical_fault_entities"] = {"id": ids, "electrical.status": [1] * len(ids)}
    with ModelTester(CascadeModel(cfg), schema=schema) as tester:
        tester.add_init_data(name, dataset)
        tester.initialize()
        r0, _ = tester.update(0, None)
        tester.new_time(1)
        r1, _ = tester.update(1, {name: data} if data else None)
    # an update that changes nothing publishes nothing
    return (r0 or {}).get(name, {}), (r1 or {}).get(name, {})


def tripped_relays(result):
    return {
        i
        for group in PROTECTION_GROUPS
        for i, tripped in zip(
            result.get(group, {}).get("id", []),
            result.get(group, {}).get("electrical.tripped", []),
        )
        if tripped == 1
    }


def energized_nodes(result):
    return by_id(result["electrical_node_entities"], "electrical.energized")


class TestMVPowerFlow:
    """Balanced 10 kV grid: a source, a tap-changing transformer to a 20 kV
    feeder, cables, a line, links, loads, a generator, a capacitor and an
    inductor. The update opens cable 20 at the to-side, moves the transformer
    tap from -1 to -4, switches the capacitor off and the inductor on."""

    def test_base_case(self, schema):
        state = run_power_flow(schema, load("mv_grid_simple_10"))
        assert_state_matches(state, load("mv_grid_simple_10_expected"))

    @pytest.mark.parametrize("as_update", [False, True], ids=["in_init_data", "at_t1"])
    def test_updated_case(self, schema, as_update):
        dataset = load("mv_grid_simple_10")
        update = load("mv_grid_simple_10_update")
        expected = load("mv_grid_simple_10_updated_expected")
        if as_update:
            state = run_power_flow(schema, dataset, update)
        else:
            state = run_power_flow(schema, apply_update(dataset, update))
        # a de-energized node has an arbitrary voltage angle in the reference
        dead = [i for i, e in energized_nodes(expected).items() if not e]
        assert_state_matches(state, expected, skip_angle_ids=dead)

    def test_updated_case_energized(self, schema):
        dataset = apply_update(load("mv_grid_simple_10"), load("mv_grid_simple_10_update"))
        r0, _ = run_cascade(schema, dataset)
        expected = load("mv_grid_simple_10_updated_expected")
        assert energized_nodes(r0) == energized_nodes(expected)

    @pytest.mark.parametrize("as_update", [False, True], ids=["in_init_data", "at_t1"])
    def test_all_off(self, schema, as_update):
        """Opening link 41, the only connection to the source node, leaves
        every node de-energized."""
        dataset = load("mv_grid_simple_10")
        update = load("mv_grid_simple_10_all_off_update")
        if as_update:
            state = run_power_flow(schema, dataset, update)
        else:
            state = run_power_flow(schema, apply_update(dataset, update))
        voltages = state["electrical_node_entities"]["electrical.voltage"]
        assert len(voltages) == 13
        assert all(u == 0.0 for u in voltages.values())
        for group in BRANCH_GROUPS:
            assert all(i == 0.0 for i in state[group]["electrical.current_from"].values())

    def test_all_off_energized(self, schema):
        dataset = apply_update(load("mv_grid_simple_10"), load("mv_grid_simple_10_all_off_update"))
        r0, _ = run_cascade(schema, dataset)
        assert set(energized_nodes(r0).values()) == {0}


# A branch over-current relay on cable 16, an over-current relay on source 28
# and a remote node relay that opens transformer 27 when node 6 is
# short-circuited.
MV_PROTECTION = {
    "electrical_branch_protection_entities": {
        "id": [1001],
        "electrical.pick_up_time": [0.1],
        "electrical.protected_line": [16],
        "electrical.protected_side": [0],
        "electrical.pick_up_current": [1e3],
    },
    "electrical_appliance_protection_entities": {
        "id": [1002],
        "electrical.pick_up_time": [2.0],
        "electrical.protected_appliance": [28],
        "electrical.pick_up_current": [1e3],
    },
    "electrical_remote_node_protection_entities": {
        "id": [1003],
        "electrical.pick_up_time": [0.0],
        "electrical.protected_node": [6],
        "electrical.protected_line": [27],
    },
}


def mv_with_protection():
    dataset = load("mv_grid_simple_10")
    dataset["data"].update(copy.deepcopy(MV_PROTECTION))
    return dataset


class TestMVProtection:
    def test_faults_trip_feeder_and_transformer(self, schema):
        """Faults at nodes 6 and 7: the remote node relay opens the
        transformer at once and the cable relay follows."""
        _, r1 = run_cascade(schema, mv_with_protection(), fault_nodes=[6, 7])
        dead = {i for i, e in energized_nodes(r1).items() if e == 0}
        assert dead == {1, 4, 6, 7, 8, 11, 12}
        assert tripped_relays(r1) == {1001, 1003}

    def test_fault_at_source_node(self, schema):
        """A fault at the source node trips the source relay and takes the
        whole grid down."""
        _, r1 = run_cascade(schema, mv_with_protection(), fault_nodes=[0])
        energized = energized_nodes(r1)
        assert set(energized) == set(range(13))
        assert set(energized.values()) == {0}
        assert tripped_relays(r1) == {1002}
        assert by_id(r1["electrical_source_entities"], "electrical.status") == {28: 0}

    def test_faults_without_protection(self, schema):
        """Without relays the fault currents are published and the grid
        stays energized."""
        _, r1 = run_cascade(schema, load("mv_grid_simple_10"), fault_nodes=[6, 7])
        faults = by_id(r1["electrical_fault_entities"], "electrical.fault_current")
        assert faults[2006] > 1e3 and faults[2007] > 1e3
        # nothing tripped, so no changed node state is published at t=1
        energized = r1.get("electrical_node_entities", {}).get("electrical.energized")
        assert energized is None or set(energized) == {1}


class TestLVGrid:
    """400 V grid with single-phase loads, run as an asymmetric power flow.
    The update opens cable 7, moves loads 14 and 15 to phase c and switches
    load 15 off. The expected per-phase voltages are on the line-to-line
    base of ``electrical.voltage_per_phase``."""

    @staticmethod
    def assert_per_phase_matches(state, expected, i_tol=I_TOL):
        # the reference is line-to-neutral, so 1 V there is sqrt(3) V on this base
        u_tol = U_TOL * np.sqrt(3)
        got = state["electrical_node_entities"]["electrical.voltage_per_phase"]
        nodes = by_id(expected["electrical_node_entities"], "electrical.voltage_per_phase")
        for i, ref in nodes.items():
            assert np.allclose(got[i], ref, rtol=0, atol=u_tol), f"node {i}: {got[i]} != {ref}"
        for group in (
            "electrical_asym_load_entities",
            "electrical_source_entities",
            "electrical_shunt_entities",
        ):
            got = state[group]["electrical.current_per_phase"]
            for i, ref in by_id(expected[group], "electrical.current_per_phase").items():
                assert np.allclose(got[i], ref, rtol=0, atol=i_tol), f"{group} {i}: {got[i]}"

    def test_base_case(self, schema):
        state = run_power_flow(
            schema, load("lv_grid_simple_6"), symmetric=False, per_phase_output=True
        )
        self.assert_per_phase_matches(state, load("lv_grid_simple_6_expected"))

    @pytest.mark.parametrize("as_update", [False, True], ids=["in_init_data", "at_t1"])
    def test_updated_case(self, schema, as_update):
        """The reference voltages of this case are off by up to 0.9 V, which
        is worth 2 A on a 500 A single-phase load, so currents get a wider
        tolerance."""
        dataset = load("lv_grid_simple_6")
        update = load("lv_grid_simple_6_update")
        options = {"symmetric": False, "per_phase_output": True}
        if as_update:
            state = run_power_flow(schema, dataset, update, **options)
        else:
            state = run_power_flow(schema, apply_update(dataset, update), **options)
        self.assert_per_phase_matches(state, load("lv_grid_simple_6_updated_expected"), i_tol=3.0)

    def test_fault_trips_feeder(self, schema):
        """With cable 7 open, a fault at node 2 trips the relay on cable 5
        and de-energizes nodes 1 and 2."""
        _, r1 = run_cascade(
            schema,
            load("lv_grid_simple_6"),
            fault_nodes=[2],
            update=load("lv_grid_simple_6_update"),
        )
        dead = {i for i, e in energized_nodes(r1).items() if e == 0}
        assert dead == {1, 2}
        assert by_id(r1["electrical_branch_protection_entities"], "electrical.tripped") == {16: 1}
