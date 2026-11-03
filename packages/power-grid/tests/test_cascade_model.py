"""Tests for the power grid cascade and fault activation models."""

import pytest

from movici_power_grid_model import CascadeModel, FaultActivationModel
from movici_power_grid_model.attributes import PowerGridAttributes
from movici_simulation_core.testing.model_tester import ModelTester

DATASET_NAME = "test_grid"


def get_dataset(name, ds_type, data, **kwargs):
    ds = {
        "version": 3,
        "name": name,
        "type": ds_type,
        "display_name": "",
        "epsg_code": 28992,
        "data": data,
    }
    ds.update(kwargs)
    return ds


@pytest.fixture
def global_schema(global_schema):
    global_schema.use(PowerGridAttributes)
    return global_schema


def _cascade_network_data():
    """Radial network: source -> n1 --L1-- n2 --L2-- n3, load at n3.

    A fault at n3 (initially off) can be cleared by relay R2 on L2
    (instantaneous). Relay R1 on L1 is a slower backup (0.6 s): with correct
    selectivity it never operates because R2 clears the fault first.

    Impedances are low so the short-circuit current comfortably exceeds the
    relay pick-up currents; the load is small so normal operating current
    stays well below them.
    """
    return {
        "electrical_node_entities": {
            "id": [1, 2, 3],
            "geometry.x": [0.0, 1.0, 2.0],
            "geometry.y": [0.0, 0.0, 0.0],
            "electrical.rated_voltage": [10000.0, 10000.0, 10000.0],
        },
        "electrical_source_entities": {
            "id": [10],
            "connection.to_id": [1],
            "electrical.reference_voltage": [1.0],
            "electrical.short_circuit_power": [1e8],
        },
        "electrical_load_entities": {
            "id": [20],
            "connection.to_id": [3],
            "electrical.active_power_specified": [100000.0],
            "electrical.reactive_power_specified": [10000.0],
        },
        "electrical_line_entities": {
            "id": [31, 32],
            "topology.from_node_id": [1, 2],
            "topology.to_node_id": [2, 3],
            "electrical.resistance": [0.05, 0.05],
            "electrical.reactance": [0.1, 0.1],
            "electrical.capacitance": [1e-9, 1e-9],
            "electrical.tan_delta": [0.0, 0.0],
            "electrical.rated_current": [500.0, 500.0],
        },
        "electrical_fault_entities": {
            "id": [41],
            "connection.to_id": [3],
            "electrical.status": [0],
            "electrical.fault_type": [0],
        },
        "electrical_branch_protection_entities": {
            "id": [51, 52],
            "electrical.pick_up_current": [1000.0, 1000.0],
            "electrical.pick_up_time": [0.6, 0.0],
            "electrical.protected_line": [31, 32],
            "electrical.protected_side": [0, 0],
        },
    }


@pytest.fixture
def cascade_config():
    return {
        "name": "test_cascade",
        "type": "power_grid_cascade",
        "dataset": DATASET_NAME,
    }


@pytest.fixture
def cascade_data():
    return _cascade_network_data()


@pytest.fixture
def tester(cascade_config, cascade_data, global_schema):
    model = CascadeModel(cascade_config)
    with ModelTester(model, schema=global_schema) as tester:
        tester.add_init_data(
            DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", cascade_data)
        )
        tester.initialize()
        yield tester


def _activate_fault(tester, timestamp=1, fault_id=41):
    tester.new_time(timestamp)
    return tester.update(
        timestamp,
        {
            DATASET_NAME: {
                "electrical_fault_entities": {
                    "id": [fault_id],
                    "electrical.status": [1],
                }
            }
        },
    )


class TestCascadeWithoutFaults:
    def test_no_fault_runs_power_flow(self, tester):
        """Without active faults the model behaves like a plain power flow."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert "electrical.voltage_pu" in nodes
        assert all(v > 0.9 for v in nodes["electrical.voltage_pu"])

    def test_all_nodes_energized(self, tester):
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert nodes["electrical.energized"] == [1, 1, 1]

    def test_no_trips_published(self, tester):
        result, _ = tester.update(0, None)
        assert "electrical_branch_protection_entities" not in result.get(DATASET_NAME, {})


class TestCascadeTripping:
    def test_fault_trips_nearest_relay(self, tester):
        """Fault at n3: instantaneous relay R2 (on L2) trips, not backup R1."""
        tester.update(0, None)
        result, _ = _activate_fault(tester)
        prot = result[DATASET_NAME]["electrical_branch_protection_entities"]
        trip_by_id = dict(zip(prot["id"], prot["electrical.tripped"]))
        assert trip_by_id.get(52) == 1
        assert trip_by_id.get(51) is None or trip_by_id[51] == 0

    def test_tripped_branch_opened(self, tester):
        tester.update(0, None)
        result, _ = _activate_fault(tester)
        lines = result[DATASET_NAME]["electrical_line_entities"]
        status_by_id = dict(zip(lines["id"], lines["electrical.from_status"]))
        assert status_by_id.get(32) == 0

    def test_faulted_island_deenergized(self, tester):
        """After the trip, n3 is de-energized; n1, n2 stay energized.

        Updates only contain changed values: unchanged energized states are
        ``None`` in the published data, not re-published as 1.
        """
        tester.update(0, None)
        result, _ = _activate_fault(tester)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        energized_by_id = dict(zip(nodes["id"], nodes["electrical.energized"]))
        assert energized_by_id[3] == 0
        assert energized_by_id.get(1) != 0
        assert energized_by_id.get(2) != 0

    def test_fault_current_published(self, tester):
        tester.update(0, None)
        result, _ = _activate_fault(tester)
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert faults["electrical.fault_current"][0] > 0

    def test_trip_is_latching(self, tester):
        """Once tripped, the breaker stays open on subsequent updates."""
        tester.update(0, None)
        _activate_fault(tester)
        tester.new_time(2)
        result, _ = tester.update(2, None)
        # No new data published for an unchanged breaker is fine; verify via
        # energized state that the island is still dead
        if result and DATASET_NAME in result:
            nodes = result[DATASET_NAME].get("electrical_node_entities", {})
            if "electrical.energized" in nodes:
                energized_by_id = dict(zip(nodes["id"], nodes["electrical.energized"]))
                assert energized_by_id.get(3, 0) == 0


class TestExternalSwitching:
    """Branch status is OPT|PUB on the cascade model: trips are published,
    and switching done by other models is still picked up."""

    def test_externally_opened_line_is_respected(self, tester):
        """Line L2 opened by an external update: n3 dead without any trip, and
        a fault on the dead island afterwards draws no current."""
        tester.update(0, None)
        tester.new_time(1)
        result, _ = tester.update(
            1,
            {
                DATASET_NAME: {
                    "electrical_line_entities": {"id": [32], "electrical.to_status": [0]}
                }
            },
        )
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert dict(zip(nodes["id"], nodes["electrical.energized"]))[3] == 0
        assert "electrical_branch_protection_entities" not in result[DATASET_NAME]

        result, _ = _activate_fault(tester, timestamp=2)
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert faults["electrical.fault_current"][0] == 0.0
        assert "electrical_branch_protection_entities" not in result[DATASET_NAME]

    def test_trip_survives_later_updates(self, tester):
        """The breaker opened by a trip is not re-closed by a later, unrelated
        update that makes the model re-apply its subscribed changes."""
        tester.update(0, None)
        _activate_fault(tester)
        tester.new_time(2)
        result, _ = tester.update(
            2,
            {
                DATASET_NAME: {
                    "electrical_load_entities": {
                        "id": [20],
                        "electrical.active_power_specified": [50000.0],
                    }
                }
            },
        )
        # nothing changed for the nodes, so nothing is published: read the state
        assert result is None or "electrical_node_entities" not in result[DATASET_NAME]
        nodes = tester.model.dataset.nodes
        energized = dict(zip(nodes.index.ids.tolist(), nodes.energized.array.tolist()))
        assert energized == {1: 1, 2: 1, 3: 0}
        lines = tester.model.dataset.lines
        assert lines.from_status.array[lines.get_indices([32])][0] == 0

    def test_external_reclose_after_trip(self, tester):
        """Another model may close the breaker again (repair): n3 comes back."""
        tester.update(0, None)
        _activate_fault(tester)
        tester.new_time(2)
        result, _ = tester.update(
            2,
            {
                DATASET_NAME: {
                    "electrical_fault_entities": {"id": [41], "electrical.status": [0]},
                    "electrical_line_entities": {"id": [32], "electrical.from_status": [1]},
                }
            },
        )
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert dict(zip(nodes["id"], nodes["electrical.energized"]))[3] == 1


class TestCascadeSelectivity:
    def test_backup_trips_when_primary_absent(self, cascade_config, cascade_data, global_schema):
        """Without R2, backup relay R1 trips and takes out the whole feeder."""
        prot = cascade_data["electrical_branch_protection_entities"]
        for key in list(prot):
            prot[key] = prot[key][:1]  # keep only R1 (on L1, 0.6 s)

        model = CascadeModel(cascade_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", cascade_data)
            )
            tester.initialize()
            tester.update(0, None)
            result, _ = _activate_fault(tester)

        prot_result = result[DATASET_NAME]["electrical_branch_protection_entities"]
        assert dict(zip(prot_result["id"], prot_result["electrical.tripped"]))[51] == 1
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        energized_by_id = dict(zip(nodes["id"], nodes["electrical.energized"]))
        assert energized_by_id[2] == 0
        assert energized_by_id[3] == 0


class TestCascadeWithoutProtection:
    def test_fault_without_relays_reports_current(
        self, cascade_config, cascade_data, global_schema
    ):
        """No protection entities: SC results are reported, nothing trips."""
        del cascade_data["electrical_branch_protection_entities"]

        model = CascadeModel(cascade_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", cascade_data)
            )
            tester.initialize()
            tester.update(0, None)
            result, _ = _activate_fault(tester)

        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert faults["electrical.fault_current"][0] > 0
        # Nothing tripped: the power flow restores the pre-fault state, so no
        # node changes (energized or otherwise) are published at all
        assert "electrical_node_entities" not in result[DATASET_NAME]


class TestFaultActivation:
    @pytest.fixture
    def activation_config(self):
        return {
            "name": "test_fault_activation",
            "type": "power_grid_fault_activation",
            "dataset": DATASET_NAME,
            "monitor_attribute": "flooding.water_depth",
            "threshold": 0.3,
        }

    @pytest.fixture
    def activation_data(self):
        return {
            "electrical_node_entities": {
                "id": [1, 2, 3],
                "geometry.x": [0.0, 1.0, 2.0],
                "geometry.y": [0.0, 0.0, 0.0],
                "electrical.rated_voltage": [10000.0, 10000.0, 10000.0],
            },
            "electrical_fault_entities": {
                "id": [41, 42, 43],
                "connection.to_id": [1, 2, 3],
                "electrical.status": [0, 0, 0],
                "electrical.fault_type": [0, 0, 0],
            },
        }

    @pytest.fixture
    def activation_tester(self, activation_config, activation_data, global_schema):
        model = FaultActivationModel(activation_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", activation_data)
            )
            tester.initialize()
            yield tester

    def _depth_update(self, depths):
        return {
            DATASET_NAME: {
                "electrical_node_entities": {
                    "id": [1, 2, 3],
                    "flooding.water_depth": depths,
                }
            }
        }

    def test_activates_faults_over_threshold(self, activation_tester):
        result, _ = activation_tester.update(0, self._depth_update([0.0, 0.5, 0.2]))
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert faults["id"] == [42]
        assert faults["electrical.status"] == [1]

    def test_no_activation_below_threshold(self, activation_tester):
        result, _ = activation_tester.update(0, self._depth_update([0.0, 0.1, 0.2]))
        assert not result or "electrical_fault_entities" not in result.get(DATASET_NAME, {})

    def test_latching(self, activation_tester):
        """A fault stays active when the water recedes."""
        activation_tester.update(0, self._depth_update([0.0, 0.5, 0.2]))
        activation_tester.new_time(1)
        result, _ = activation_tester.update(1, self._depth_update([0.0, 0.0, 0.0]))
        # No deactivation is published
        if result and DATASET_NAME in result:
            faults = result[DATASET_NAME].get("electrical_fault_entities", {})
            assert 0 not in faults.get("electrical.status", [])

    def test_rising_water_activates_more(self, activation_tester):
        activation_tester.update(0, self._depth_update([0.0, 0.5, 0.2]))
        activation_tester.new_time(1)
        result, _ = activation_tester.update(1, self._depth_update([0.4, 0.6, 0.35]))
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert sorted(faults["id"]) == [41, 43]


class TestEndToEndChain:
    """Fault activation output drives the cascade model (via manual update)."""

    def test_activation_output_format_matches_cascade_input(
        self, cascade_config, cascade_data, global_schema
    ):
        """The exact update dict the activation model publishes must trip the
        cascade when fed to it."""
        model = CascadeModel(cascade_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", cascade_data)
            )
            tester.initialize()
            tester.update(0, None)
            # This is the shape of the fault activation model's output
            result, _ = tester.update(
                1,
                {
                    DATASET_NAME: {
                        "electrical_fault_entities": {
                            "id": [41],
                            "electrical.status": [1],
                        }
                    }
                },
            )
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        energized_by_id = dict(zip(nodes["id"], nodes["electrical.energized"]))
        assert energized_by_id[3] == 0
