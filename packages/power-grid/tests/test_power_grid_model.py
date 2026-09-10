"""Tests for power grid calculation model."""

import numpy as np
import pytest

from movici_power_grid_model import Model
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


@pytest.fixture
def model_config():
    return {
        "name": "test_power_grid",
        "type": "power_grid_calculation",
        "dataset": DATASET_NAME,
    }


def _simple_network_data():
    """Simple 2-node network: Source -> Line -> Load."""
    return {
        "electrical_node_entities": {
            "id": [1, 2],
            "geometry.x": [0.0, 1.0],
            "geometry.y": [0.0, 0.0],
            "electrical.rated_voltage": [10000.0, 10000.0],
        },
        "electrical_source_entities": {
            "id": [10],
            "connection.to_id": [1],
            "electrical.reference_voltage": [1.0],
        },
        "electrical_load_entities": {
            "id": [20],
            "connection.to_id": [2],
            "electrical.active_power_specified": [100000.0],
            "electrical.reactive_power_specified": [0.0],
        },
        "electrical_line_entities": {
            "id": [30],
            "topology.from_node_id": [1],
            "topology.to_node_id": [2],
            "electrical.resistance": [0.1],
            "electrical.reactance": [0.05],
            "electrical.capacitance": [0.0],
            "electrical.tan_delta": [0.0],
        },
    }


@pytest.fixture
def simple_network():
    return get_dataset(DATASET_NAME, "electrical_network", _simple_network_data())


@pytest.fixture
def init_data(simple_network):
    return [{"name": DATASET_NAME, "data": simple_network}]


@pytest.fixture
def tester(model_config, init_data, global_schema):
    model = Model(model_config)
    with ModelTester(model, schema=global_schema) as tester:
        for ds in init_data:
            tester.add_init_data(ds["name"], ds["data"])
        tester.initialize()
        yield tester


class TestPowerFlow:
    """Power flow calculation tests."""

    def test_simple_network_produces_results(self, tester):
        """Model produces voltage results for all nodes."""
        result, _ = tester.update(0, None)
        assert result is not None
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert "electrical.voltage_pu" in nodes

    def test_source_node_at_reference_voltage(self, tester):
        """Source node voltage should be ~1.0 p.u."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        source_idx = nodes["id"].index(1)
        assert abs(nodes["electrical.voltage_pu"][source_idx] - 1.0) < 0.01

    def test_load_node_voltage_drop(self, tester):
        """Load node should have voltage drop due to line impedance."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        source_idx = nodes["id"].index(1)
        load_idx = nodes["id"].index(2)
        assert (
            nodes["electrical.voltage_pu"][load_idx] < nodes["electrical.voltage_pu"][source_idx]
        )

    def test_line_results(self, tester):
        """Line results include current and power flow."""
        result, _ = tester.update(0, None)
        lines = result[DATASET_NAME]["electrical_line_entities"]
        assert lines["electrical.current_from"][0] > 0
        assert lines["electrical.current_to"][0] > 0
        assert lines["electrical.power_from"][0] != 0

    def test_line_loading_with_rated_current(self, model_config, global_schema):
        """Line loading is calculated when rated current is specified."""
        data = _simple_network_data()
        data["electrical_line_entities"]["electrical.rated_current"] = [100.0]
        dataset = get_dataset(DATASET_NAME, "electrical_network", data)

        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, dataset)
            tester.initialize()
            result, _ = tester.update(0, None)

        lines = result[DATASET_NAME]["electrical_line_entities"]
        assert lines["electrical.loading"][0] > 0


class TestDynamicUpdates:
    """Tests for dynamic load/generator updates.

    PGM is a steady-state model: incoming changes are applied before
    calculation, so results immediately reflect the new state.
    """

    def test_increased_load_causes_more_voltage_drop(self, tester):
        """Doubling load should immediately increase voltage drop."""
        # Update 0: initial calculation
        result1, _ = tester.update(0, None)
        nodes1 = result1[DATASET_NAME]["electrical_node_entities"]
        load_idx = nodes1["id"].index(2)
        voltage1 = nodes1["electrical.voltage_pu"][load_idx]

        # Update 1: send load change - results immediately reflect new state
        tester.new_time(1)
        result2, _ = tester.update(
            1,
            {
                DATASET_NAME: {
                    "electrical_load_entities": {
                        "id": [20],
                        "electrical.active_power_specified": [200000.0],
                        "electrical.reactive_power_specified": [0.0],
                    }
                }
            },
        )
        nodes2 = result2[DATASET_NAME]["electrical_node_entities"]
        voltage2 = nodes2["electrical.voltage_pu"][load_idx]

        # Higher load should cause more voltage drop
        assert voltage2 < voltage1


class TestCalculationMethods:
    """Tests for different calculation methods."""

    @pytest.fixture(params=["newton_raphson", "iterative_current"])
    def method_config(self, request):
        return {
            "name": "test_power_grid",
            "type": "power_grid_calculation",
            "dataset": DATASET_NAME,
            "algorithm": request.param,
        }

    def test_methods_produce_similar_results(self, method_config, init_data, global_schema):
        """Different methods should produce similar voltage results."""
        model = Model(method_config)
        with ModelTester(model, schema=global_schema) as tester:
            for ds in init_data:
                tester.add_init_data(ds["name"], ds["data"])
            tester.initialize()
            result, _ = tester.update(0, None)

        nodes = result[DATASET_NAME]["electrical_node_entities"]
        load_idx = nodes["id"].index(2)
        # All methods should produce a load node voltage near 1.0 p.u.
        assert 0.9 < nodes["electrical.voltage_pu"][load_idx] < 1.0


class TestVirtualNodesAndLinks:
    """Tests for virtual nodes and zero-impedance links."""

    @pytest.fixture
    def network_with_virtual_nodes(self):
        """Network: Source -> VirtualNode --(Link)--> Node1 --(Line)--> Node2 -> Load."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2],
                "geometry.x": [0.0, 1.0],
                "geometry.y": [0.0, 0.0],
                "electrical.rated_voltage": [10000.0, 10000.0],
            },
            "electrical_virtual_node_entities": {
                "id": [100],
                "electrical.rated_voltage": [10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [100],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [2],
                "electrical.active_power_specified": [100000.0],
                "electrical.reactive_power_specified": [0.0],
            },
            "electrical_link_entities": {
                "id": [50],
                "topology.from_node_id": [100],
                "topology.to_node_id": [1],
            },
            "electrical_line_entities": {
                "id": [30],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.resistance": [0.1],
                "electrical.reactance": [0.05],
                "electrical.capacitance": [0.0],
                "electrical.tan_delta": [0.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_virtual_nodes):
        return [{"name": DATASET_NAME, "data": network_with_virtual_nodes}]

    def test_virtual_node_at_reference_voltage(self, tester):
        """Virtual node (source) should be at ~1.0 p.u."""
        result, _ = tester.update(0, None)
        vnodes = result[DATASET_NAME]["electrical_virtual_node_entities"]
        idx = vnodes["id"].index(100)
        assert abs(vnodes["electrical.voltage_pu"][idx] - 1.0) < 0.01

    def test_link_minimal_voltage_drop(self, tester):
        """Link (zero-impedance) should have minimal voltage drop."""
        result, _ = tester.update(0, None)
        vnodes = result[DATASET_NAME]["electrical_virtual_node_entities"]
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        v_virtual = vnodes["electrical.voltage_pu"][vnodes["id"].index(100)]
        v_node1 = nodes["electrical.voltage_pu"][nodes["id"].index(1)]
        assert abs(v_virtual - v_node1) < 0.001

    def test_voltage_decreases_along_network(self, tester):
        """Voltage should drop from source through the network."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        v_node1 = nodes["electrical.voltage_pu"][nodes["id"].index(1)]
        v_node2 = nodes["electrical.voltage_pu"][nodes["id"].index(2)]
        assert v_node2 < v_node1


class TestCables:
    """Tests for underground cables."""

    @pytest.fixture
    def network_with_cables(self):
        """Network: Source -> Node1 --(Line)--> Node2 --(Cable)--> Node3 -> Load."""
        data = {
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
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [3],
                "electrical.active_power_specified": [50000.0],
                "electrical.reactive_power_specified": [10000.0],
            },
            "electrical_line_entities": {
                "id": [30],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.resistance": [0.1],
                "electrical.reactance": [0.05],
                "electrical.capacitance": [1e-9],
                "electrical.tan_delta": [0.0],
            },
            "electrical_cable_entities": {
                "id": [40],
                "topology.from_node_id": [2],
                "topology.to_node_id": [3],
                "electrical.resistance": [0.08],
                "electrical.reactance": [0.03],
                "electrical.capacitance": [1e-7],
                "electrical.tan_delta": [0.001],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_cables):
        return [{"name": DATASET_NAME, "data": network_with_cables}]

    def test_cables_produce_results(self, tester):
        """Cable entities get line-like results."""
        result, _ = tester.update(0, None)
        cables = result[DATASET_NAME]["electrical_cable_entities"]
        assert cables["electrical.current_from"][0] > 0

    def test_all_nodes_have_results(self, tester):
        """All 3 nodes should have voltage results."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert len(nodes["id"]) == 3


class TestMultipleSources:
    """Tests for meshed networks with multiple grid connections."""

    @pytest.fixture
    def meshed_network(self):
        """Meshed: VNode100 -> Node1 -> Node2 -> Node3 <- VNode200."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2, 3],
                "geometry.x": [0.0, 1.0, 2.0],
                "geometry.y": [0.0, 0.0, 0.0],
                "electrical.rated_voltage": [10000.0, 10000.0, 10000.0],
            },
            "electrical_virtual_node_entities": {
                "id": [100, 200],
                "electrical.rated_voltage": [10000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10, 11],
                "connection.to_id": [100, 200],
                "electrical.reference_voltage": [1.0, 1.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [2],
                "electrical.active_power_specified": [200000.0],
                "electrical.reactive_power_specified": [50000.0],
            },
            "electrical_link_entities": {
                "id": [50, 51],
                "topology.from_node_id": [100, 200],
                "topology.to_node_id": [1, 3],
            },
            "electrical_line_entities": {
                "id": [30, 31],
                "topology.from_node_id": [1, 2],
                "topology.to_node_id": [2, 3],
                "electrical.resistance": [0.1, 0.1],
                "electrical.reactance": [0.05, 0.05],
                "electrical.capacitance": [1e-9, 1e-9],
                "electrical.tan_delta": [0.0, 0.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, meshed_network):
        return [{"name": DATASET_NAME, "data": meshed_network}]

    def test_all_nodes_have_results(self, tester):
        """All 5 nodes (3 regular + 2 virtual) should have results."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        vnodes = result[DATASET_NAME]["electrical_virtual_node_entities"]
        assert len(nodes["id"]) == 3
        assert len(vnodes["id"]) == 2

    def test_virtual_nodes_at_reference_voltage(self, tester):
        """Both virtual nodes should be at reference voltage."""
        result, _ = tester.update(0, None)
        vnodes = result[DATASET_NAME]["electrical_virtual_node_entities"]
        for i, _vid in enumerate(vnodes["id"]):
            assert abs(vnodes["electrical.voltage_pu"][i] - 1.0) < 0.01


class TestFullTopology:
    """Test network with virtual nodes, links, cables, and lines combined."""

    @pytest.fixture
    def full_network(self):
        """VNode --(Link)--> Node1 --(Cable)--> Node2 --(Line)--> Node3 -> Load."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2, 3],
                "geometry.x": [0.0, 1.0, 2.0],
                "geometry.y": [0.0, 0.0, 0.0],
                "electrical.rated_voltage": [10000.0, 10000.0, 10000.0],
            },
            "electrical_virtual_node_entities": {
                "id": [100],
                "electrical.rated_voltage": [10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [100],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [3],
                "electrical.active_power_specified": [75000.0],
                "electrical.reactive_power_specified": [15000.0],
            },
            "electrical_link_entities": {
                "id": [50],
                "topology.from_node_id": [100],
                "topology.to_node_id": [1],
            },
            "electrical_cable_entities": {
                "id": [40],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.resistance": [0.05],
                "electrical.reactance": [0.02],
                "electrical.capacitance": [1e-7],
                "electrical.tan_delta": [0.001],
            },
            "electrical_line_entities": {
                "id": [30],
                "topology.from_node_id": [2],
                "topology.to_node_id": [3],
                "electrical.resistance": [0.1],
                "electrical.reactance": [0.05],
                "electrical.capacitance": [1e-9],
                "electrical.tan_delta": [0.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, full_network):
        return [{"name": DATASET_NAME, "data": full_network}]

    def test_voltage_profile(self, tester):
        """Voltage should decrease from virtual node through the network."""
        result, _ = tester.update(0, None)
        vnodes = result[DATASET_NAME]["electrical_virtual_node_entities"]
        nodes = result[DATASET_NAME]["electrical_node_entities"]

        v_virtual = vnodes["electrical.voltage_pu"][vnodes["id"].index(100)]
        v_node1 = nodes["electrical.voltage_pu"][nodes["id"].index(1)]
        v_node2 = nodes["electrical.voltage_pu"][nodes["id"].index(2)]
        v_node3 = nodes["electrical.voltage_pu"][nodes["id"].index(3)]

        assert abs(v_virtual - 1.0) < 0.01
        assert v_node1 >= v_node2 - 0.001
        assert v_node2 >= v_node3 - 0.001

    def test_all_branch_types_produce_results(self, tester):
        """Links, cables, and lines all produce current/power results."""
        result, _ = tester.update(0, None)
        lines = result[DATASET_NAME]["electrical_line_entities"]
        cables = result[DATASET_NAME]["electrical_cable_entities"]
        links = result[DATASET_NAME]["electrical_link_entities"]

        assert lines["electrical.current_from"][0] > 0
        assert cables["electrical.current_from"][0] > 0
        assert links["electrical.current_from"][0] > 0


class TestStateEstimation:
    """Tests for state estimation with sensors."""

    @pytest.fixture
    def model_config(self):
        return {
            "name": "test_power_grid",
            "type": "power_grid_calculation",
            "dataset": DATASET_NAME,
            "calculation_type": "state_estimation",
        }

    @pytest.fixture(params=["power_sensors", "current_sensor"])
    def sensor_network(self, request):
        """Network with voltage sensors + either power or current sensors."""
        data = _simple_network_data()
        data["electrical_voltage_sensor_entities"] = {
            "id": [80, 81],
            "connection.to_id": [1, 2],
            "electrical.voltage_sigma": [100.0, 100.0],
            "electrical.measured_voltage": [10000.0, 9900.0],
        }
        data["electrical_power_sensor_entities"] = {
            "id": [90],
            "connection.to_id": [20],  # references the load
            "electrical.measured_terminal_type": [4],  # sym_load
            "electrical.power_sigma": [10000.0],
            "electrical.measured_active_power": [100000.0],
            "electrical.measured_reactive_power": [0.0],
        }
        if request.param == "current_sensor":
            data["electrical_current_sensor_entities"] = {
                "id": [85],
                "connection.to_id": [30],  # references the line
                "electrical.measured_terminal_type": [0],  # branch_from
                "electrical.current_sigma": [1.0],
                "electrical.measured_current": [10.0],
                "electrical.angle_measurement_type": [0],  # local
                "electrical.measured_current_angle": [0.5],  # rad
                "electrical.current_angle_sigma": [0.1],  # rad
            }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    def test_state_estimation_produces_finite_voltages(
        self, model_config, sensor_network, global_schema
    ):
        """State estimation produces finite voltage results for all sensor configurations."""
        init_data = [{"name": DATASET_NAME, "data": sensor_network}]
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            for ds in init_data:
                tester.add_init_data(ds["name"], ds["data"])
            tester.initialize()
            result, _ = tester.update(0, None)

        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert len(nodes["electrical.voltage_pu"]) == 2
        for v in nodes["electrical.voltage_pu"]:
            assert np.isfinite(v)
        # Source node should be near 1.0 pu
        source_idx = nodes["id"].index(1)
        assert abs(nodes["electrical.voltage_pu"][source_idx] - 1.0) < 0.05


class TestShunt:
    """Tests for shunt elements."""

    @pytest.fixture
    def network_with_shunt(self):
        """Simple network with a capacitor shunt for reactive compensation."""
        data = _simple_network_data()
        data["electrical_shunt_entities"] = {
            "id": [70],
            "connection.to_id": [2],
            "electrical.conductance": [0.0],
            "electrical.susceptance": [1e-4],  # capacitive shunt
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_shunt):
        return [{"name": DATASET_NAME, "data": network_with_shunt}]

    def test_shunt_affects_reactive_power(self, tester):
        """Shunt element should contribute reactive power at its node."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        load_idx = nodes["id"].index(2)
        # With a capacitive shunt, the reactive power at node 2 should be nonzero
        assert nodes["electrical.reactive_power"][load_idx] != 0

    def test_shunt_improves_voltage(self, model_config, global_schema):
        """Capacitive shunt at load bus should improve (raise) voltage."""
        # Without shunt
        data_no_shunt = _simple_network_data()
        ds_no_shunt = get_dataset(DATASET_NAME, "electrical_network", data_no_shunt)
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, ds_no_shunt)
            tester.initialize()
            result_no_shunt, _ = tester.update(0, None)
        v_no_shunt = result_no_shunt[DATASET_NAME]["electrical_node_entities"][
            "electrical.voltage_pu"
        ][1]

        # With shunt
        data_shunt = _simple_network_data()
        data_shunt["electrical_shunt_entities"] = {
            "id": [70],
            "connection.to_id": [2],
            "electrical.conductance": [0.0],
            "electrical.susceptance": [1e-4],
        }
        ds_shunt = get_dataset(DATASET_NAME, "electrical_network", data_shunt)
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, ds_shunt)
            tester.initialize()
            result_shunt, _ = tester.update(0, None)
        v_shunt = result_shunt[DATASET_NAME]["electrical_node_entities"]["electrical.voltage_pu"][
            1
        ]

        assert v_shunt > v_no_shunt


class TestGeneratorDynamicUpdates:
    """Tests for dynamic generator updates."""

    @pytest.fixture
    def network_with_generator(self):
        """Network with source, generator, and load."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2],
                "geometry.x": [0.0, 1.0],
                "geometry.y": [0.0, 0.0],
                "electrical.rated_voltage": [10000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [1],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_generator_entities": {
                "id": [15],
                "connection.to_id": [2],
                "electrical.active_power_specified": [50000.0],
                "electrical.reactive_power_specified": [0.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [2],
                "electrical.active_power_specified": [100000.0],
                "electrical.reactive_power_specified": [0.0],
            },
            "electrical_line_entities": {
                "id": [30],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.resistance": [0.1],
                "electrical.reactance": [0.05],
                "electrical.capacitance": [0.0],
                "electrical.tan_delta": [0.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_generator):
        return [{"name": DATASET_NAME, "data": network_with_generator}]

    def test_generator_reduces_line_loading(self, tester, model_config, global_schema):
        """Local generator should reduce power flow through the line."""
        # With generator: net load at node 2 is 100kW - 50kW = 50kW
        result_gen, _ = tester.update(0, None)
        i_gen = result_gen[DATASET_NAME]["electrical_line_entities"]["electrical.current_from"][0]

        # Without generator
        data_no_gen = _simple_network_data()
        ds_no_gen = get_dataset(DATASET_NAME, "electrical_network", data_no_gen)
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as t2:
            t2.add_init_data(DATASET_NAME, ds_no_gen)
            t2.initialize()
            result_no_gen, _ = t2.update(0, None)
        i_no_gen = result_no_gen[DATASET_NAME]["electrical_line_entities"][
            "electrical.current_from"
        ][0]

        assert i_gen < i_no_gen

    def test_generator_dynamic_update(self, tester):
        """Increasing generator output should immediately reduce voltage drop."""
        # Update 0: initial calculation
        result1, _ = tester.update(0, None)
        v1 = result1[DATASET_NAME]["electrical_node_entities"]["electrical.voltage_pu"][1]

        # Update 1: increase generator - results immediately reflect new state
        tester.new_time(1)
        result2, _ = tester.update(
            1,
            {
                DATASET_NAME: {
                    "electrical_generator_entities": {
                        "id": [15],
                        "electrical.active_power_specified": [100000.0],
                        "electrical.reactive_power_specified": [0.0],
                    }
                }
            },
        )
        v2 = result2[DATASET_NAME]["electrical_node_entities"]["electrical.voltage_pu"][1]

        # More local generation -> less line current -> less voltage drop
        assert v2 > v1


class TestThreeWindingTransformer:
    """Tests for three-winding transformer (Branch3)."""

    @pytest.fixture
    def network_with_3w_trafo(self):
        """Network: Source -> Node1 --(3W Trafo)--> Node2, Node3 -> Load on Node3."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2, 3],
                "geometry.x": [0.0, 1.0, 2.0],
                "geometry.y": [0.0, 0.0, 0.0],
                "electrical.rated_voltage": [150000.0, 10000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [1],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20, 21],
                "connection.to_id": [2, 3],
                "electrical.active_power_specified": [1e6, 500000.0],
                "electrical.reactive_power_specified": [0.0, 0.0],
            },
            "electrical_three_winding_transformer_entities": {
                "id": [40],
                "electrical.node_1_id": [1],
                "electrical.node_2_id": [2],
                "electrical.node_3_id": [3],
                "electrical.primary_voltage": [150000.0],
                "electrical.secondary_voltage": [10000.0],
                "electrical.tertiary_voltage": [10000.0],
                "electrical.rated_power_1": [30e6],
                "electrical.rated_power_2": [15e6],
                "electrical.rated_power_3": [15e6],
                "electrical.short_circuit_voltage_12": [0.1],
                "electrical.short_circuit_voltage_13": [0.1],
                "electrical.short_circuit_voltage_23": [0.1],
                "electrical.copper_loss_12": [30000.0],
                "electrical.copper_loss_13": [30000.0],
                "electrical.copper_loss_23": [30000.0],
                "electrical.no_load_current": [0.005],
                "electrical.no_load_loss": [10000.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_3w_trafo):
        return [{"name": DATASET_NAME, "data": network_with_3w_trafo}]

    @pytest.mark.parametrize(
        "field",
        [
            "electrical.current_1",
            "electrical.current_2",
            "electrical.current_3",
            "electrical.power_1",
            "electrical.power_2",
            "electrical.power_3",
        ],
    )
    def test_3w_trafo_produces_results(self, tester, field):
        """Three-winding transformer should produce nonzero per-side results."""
        result, _ = tester.update(0, None)
        t3w = result[DATASET_NAME]["electrical_three_winding_transformer_entities"]
        assert t3w[field][0] != 0

    def test_3w_trafo_voltage_transformation(self, tester):
        """Nodes connected via 3W trafo should have proper voltage levels."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        # All nodes should have voltage near 1.0 pu despite different rated voltages
        for i in range(len(nodes["id"])):
            assert 0.8 < nodes["electrical.voltage_pu"][i] < 1.1

    def test_3w_trafo_loading(self, tester):
        """Three-winding transformer should produce a loading ratio."""
        result, _ = tester.update(0, None)
        t3w = result[DATASET_NAME]["electrical_three_winding_transformer_entities"]
        assert t3w["electrical.loading"][0] > 0

    def test_3w_trafo_short_circuit(self, model_config, global_schema):
        """Three-winding transformer in short circuit produces current results."""
        sc_config = {**model_config, "calculation_type": "short_circuit"}
        data = {
            "electrical_node_entities": {
                "id": [1, 2, 3],
                "geometry.x": [0.0, 1.0, 2.0],
                "geometry.y": [0.0, 0.0, 0.0],
                "electrical.rated_voltage": [150000.0, 10000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [1],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20, 21],
                "connection.to_id": [2, 3],
                "electrical.active_power_specified": [1e6, 500000.0],
                "electrical.reactive_power_specified": [0.0, 0.0],
            },
            "electrical_three_winding_transformer_entities": {
                "id": [40],
                "electrical.node_1_id": [1],
                "electrical.node_2_id": [2],
                "electrical.node_3_id": [3],
                "electrical.primary_voltage": [150000.0],
                "electrical.secondary_voltage": [10000.0],
                "electrical.tertiary_voltage": [10000.0],
                "electrical.rated_power_1": [30e6],
                "electrical.rated_power_2": [15e6],
                "electrical.rated_power_3": [15e6],
                "electrical.short_circuit_voltage_12": [0.1],
                "electrical.short_circuit_voltage_13": [0.1],
                "electrical.short_circuit_voltage_23": [0.1],
                "electrical.copper_loss_12": [30000.0],
                "electrical.copper_loss_13": [30000.0],
                "electrical.copper_loss_23": [30000.0],
                "electrical.no_load_current": [0.005],
                "electrical.no_load_loss": [10000.0],
            },
            "electrical_fault_entities": {
                "id": [60],
                "connection.to_id": [2],
                "electrical.fault_type": [0],
            },
        }
        dataset = get_dataset(DATASET_NAME, "electrical_network", data)
        model = Model(sc_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, dataset)
            tester.initialize()
            result, _ = tester.update(0, None)

        t3w = result[DATASET_NAME]["electrical_three_winding_transformer_entities"]
        assert t3w["electrical.current_1"][0] > 0
        assert t3w["electrical.current_2"][0] > 0
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert faults["electrical.fault_current"][0] > 0


class TestShortCircuitFaultOutput:
    """Tests for fault output in short-circuit analysis."""

    @pytest.fixture
    def model_config(self):
        return {
            "name": "test_power_grid",
            "type": "power_grid_calculation",
            "dataset": DATASET_NAME,
            "calculation_type": "short_circuit",
        }

    @pytest.fixture
    def network_with_fault(self):
        data = _simple_network_data()
        data["electrical_fault_entities"] = {
            "id": [60],
            "connection.to_id": [2],
            "electrical.fault_type": [0],  # three_phase
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_fault):
        return [{"name": DATASET_NAME, "data": network_with_fault}]

    @pytest.mark.parametrize(
        "field",
        ["electrical.fault_current", "electrical.fault_current_angle"],
    )
    def test_fault_output_field(self, tester, field):
        """Fault entity should have finite, nonzero result for each output field."""
        result, _ = tester.update(0, None)
        faults = result[DATASET_NAME]["electrical_fault_entities"]
        assert np.isfinite(faults[field][0])
        assert faults[field][0] != 0


class TestTapRegulator:
    """Tests for transformer tap regulator."""

    @pytest.fixture
    def network_with_regulator(self):
        """Network with transformer + tap regulator controlling voltage."""
        data = {
            "electrical_node_entities": {
                "id": [1, 2],
                "geometry.x": [0.0, 1.0],
                "geometry.y": [0.0, 0.0],
                "electrical.rated_voltage": [150000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [1],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [2],
                "electrical.active_power_specified": [1e6],
                "electrical.reactive_power_specified": [0.0],
            },
            "electrical_transformer_entities": {
                "id": [30],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.primary_voltage": [150000.0],
                "electrical.secondary_voltage": [10000.0],
                "electrical.rated_power": [30e6],
                "electrical.short_circuit_voltage": [0.1],
                "electrical.copper_loss": [30000.0],
                "electrical.no_load_current": [0.005],
                "electrical.no_load_loss": [10000.0],
                "electrical.tap_side": [1],
                "electrical.tap_position": [0],
                "electrical.tap_min": [-10],
                "electrical.tap_max": [10],
                "electrical.tap_nom": [0],
                "electrical.tap_size": [250.0],
            },
            "electrical_tap_regulator_entities": {
                "id": [70],
                "connection.to_id": [30],  # regulated transformer
                "electrical.regulator_control_side": [1],  # to-side
                "electrical.voltage_setpoint": [10000.0],
                "electrical.voltage_band": [200.0],
            },
        }
        return get_dataset(DATASET_NAME, "electrical_network", data)

    @pytest.fixture
    def init_data(self, network_with_regulator):
        return [{"name": DATASET_NAME, "data": network_with_regulator}]

    def test_tap_regulator_produces_tap_position(self, tester):
        """Tap regulator should produce an optimal tap position."""
        result, _ = tester.update(0, None)
        regs = result[DATASET_NAME]["electrical_tap_regulator_entities"]
        # tap_pos should be an integer within the transformer's tap range
        tap = regs["electrical.tap_position"][0]
        assert -10 <= tap <= 10

    def test_regulated_voltage_within_band(self, tester):
        """Regulated node voltage should be within the specified band."""
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        load_idx = nodes["id"].index(2)
        v_abs = nodes["electrical.voltage"][load_idx]
        # Voltage should be within setpoint +/- band/2
        assert abs(v_abs - 10000.0) < 200.0


class TestAnalyticalReference:
    """Verify integration doesn't corrupt values by checking against PGM reference output."""

    def test_simple_network_exact_values(self, tester):
        """Node and line results match PGM's direct output for the simple 2-node network.

        Reference values computed directly via power_grid_model for:
        Source(u_ref=1.0) -> Line(R=0.1, X=0.05) -> Load(P=100kW, Q=0)
        on a 10kV network.
        """
        result, _ = tester.update(0, None)
        nodes = result[DATASET_NAME]["electrical_node_entities"]
        lines = result[DATASET_NAME]["electrical_line_entities"]

        # Node voltages
        src_idx = nodes["id"].index(1)
        load_idx = nodes["id"].index(2)
        assert nodes["electrical.voltage_pu"][src_idx] == pytest.approx(0.999999, abs=1e-5)
        assert nodes["electrical.voltage_pu"][load_idx] == pytest.approx(0.99989899, abs=1e-5)
        assert nodes["electrical.voltage"][src_idx] == pytest.approx(9999.99, abs=0.1)
        assert nodes["electrical.voltage"][load_idx] == pytest.approx(9998.99, abs=0.1)

        # Line currents and power
        assert lines["electrical.current_from"][0] == pytest.approx(5.774, abs=0.01)
        assert lines["electrical.power_from"][0] == pytest.approx(100010.0, abs=1.0)


class TestStatusAtInit:
    """Test that OPT status flags are correctly passed to PGM init arrays."""

    def test_disabled_load_no_voltage_drop(self, model_config, global_schema):
        """Load with status=0 should not draw power -- no voltage drop on the line."""
        data = _simple_network_data()
        data["electrical_load_entities"]["electrical.status"] = [0]
        dataset = get_dataset(DATASET_NAME, "electrical_network", data)

        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, dataset)
            tester.initialize()
            result, _ = tester.update(0, None)

        nodes = result[DATASET_NAME]["electrical_node_entities"]
        v_source = nodes["electrical.voltage_pu"][nodes["id"].index(1)]
        v_load = nodes["electrical.voltage_pu"][nodes["id"].index(2)]
        # With no load, both nodes should be at reference voltage
        assert v_source == pytest.approx(1.0, abs=1e-6)
        assert v_load == pytest.approx(1.0, abs=1e-6)


class TestEmptyEntityGroups:
    """Test that empty optional entity groups don't crash the model."""

    def test_no_optional_entities(self, model_config, global_schema):
        """Model works with only required entities (nodes, source, load, line)."""
        dataset = get_dataset(DATASET_NAME, "electrical_network", _simple_network_data())
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            tester.add_init_data(DATASET_NAME, dataset)
            tester.initialize()
            result, _ = tester.update(0, None)

        nodes = result[DATASET_NAME]["electrical_node_entities"]
        assert len(nodes["electrical.voltage_pu"]) == 2
        for v in nodes["electrical.voltage_pu"]:
            assert np.isfinite(v)


class TestCleanup:
    """Test model lifecycle."""

    def test_close_cleanup(self, model_config, init_data, global_schema):
        """Closing the model cleans up resources."""
        model = Model(model_config)
        with ModelTester(model, schema=global_schema) as tester:
            for ds in init_data:
                tester.add_init_data(ds["name"], ds["data"])
            tester.initialize()

            inner = tester.model
            assert inner.wrapper.model is not None

            tester.close()
            assert inner.wrapper is None


class TestResultUnitConsistency:
    """``electrical.voltage`` and power results carry the same quantity in every
    calculation type.

    PGM reports node ``u`` as a line-to-line voltage in symmetric output but as
    a per-phase (line-to-neutral) voltage in asymmetric and short-circuit
    output, and reports ``p``/``q`` per phase rather than as a three-phase
    total.  Both are normalised on the way into the entity groups.
    """

    @staticmethod
    def _asym_transformer_network():
        """Source -> Transformer -> Load.

        Transformer-only, because asymmetric calculations need zero-sequence
        parameters and lines/cables do not carry them (see ``r0``/``x0``).
        """
        return {
            "electrical_node_entities": {
                "id": [1, 2],
                "geometry.x": [0.0, 1.0],
                "geometry.y": [0.0, 0.0],
                "electrical.rated_voltage": [150000.0, 10000.0],
            },
            "electrical_source_entities": {
                "id": [10],
                "connection.to_id": [1],
                "electrical.reference_voltage": [1.0],
            },
            "electrical_load_entities": {
                "id": [20],
                "connection.to_id": [2],
                "electrical.active_power_specified": [2000000.0],
                "electrical.reactive_power_specified": [500000.0],
            },
            "electrical_transformer_entities": {
                "id": [30],
                "topology.from_node_id": [1],
                "topology.to_node_id": [2],
                "electrical.primary_voltage": [150000.0],
                "electrical.secondary_voltage": [10000.0],
                "electrical.rated_power": [30000000.0],
                "electrical.short_circuit_voltage": [0.1],
                "electrical.copper_loss": [30000.0],
                "electrical.no_load_current": [0.005],
                "electrical.no_load_loss": [10000.0],
                "electrical.winding_from": [2],  # delta
                "electrical.winding_to": [1],  # wye_n
                "electrical.clock": [5],
            },
        }

    @staticmethod
    def _run(config, data, schema):
        model = Model(config)
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", data)
            )
            tester.initialize()
            result, _ = tester.update(0, None)
        return result[DATASET_NAME]

    def test_short_circuit_voltage_is_line_to_line(self, model_config, global_schema):
        """SC node voltage must satisfy ``voltage == voltage_pu * rated_voltage``.

        PGM's short circuit output is per-phase, so an unscaled result would be
        a factor sqrt(3) too low.
        """
        data = _simple_network_data()
        data["electrical_fault_entities"] = {
            "id": [60],
            "connection.to_id": [2],
            "electrical.fault_type": [0],  # three_phase
        }
        out = self._run({**model_config, "calculation_type": "short_circuit"}, data, global_schema)
        nodes = out["electrical_node_entities"]
        src_idx = nodes["id"].index(1)
        assert nodes["electrical.voltage"][src_idx] == pytest.approx(
            nodes["electrical.voltage_pu"][src_idx] * 10000.0, rel=1e-9
        )
        # Unfaulted node sits above nominal: IEC 60909 energises at c * u_rated
        assert nodes["electrical.voltage"][src_idx] > 10000.0

    def test_asymmetric_power_flow_matches_symmetric(self, model_config, global_schema):
        """A balanced network gives the same node/branch results either way."""
        data = self._asym_transformer_network()
        sym = self._run(model_config, data, global_schema)
        asym = self._run({**model_config, "symmetric": False}, data, global_schema)

        for eg_name, fields in (
            (
                "electrical_node_entities",
                ["electrical.voltage", "electrical.voltage_pu", "electrical.active_power"],
            ),
            (
                "electrical_transformer_entities",
                ["electrical.current_from", "electrical.power_from"],
            ),
        ):
            for f in fields:
                assert asym[eg_name][f] == pytest.approx(sym[eg_name][f], rel=1e-6), (
                    f"{eg_name}.{f} differs between symmetric and asymmetric"
                )


class TestZeroSequenceAndValidation:
    """Zero-sequence parameters unlock asymmetric calculations and unbalanced faults.

    Without them PGM's solver fails with an opaque ``SparseMatrixError``; the
    model validates up front instead and names the missing fields.
    """

    @staticmethod
    def _network(zero_sequence=False, fault_type=None):
        data = _simple_network_data()
        if zero_sequence:
            data["electrical_line_entities"].update(
                {
                    "electrical.zero_sequence_resistance": [0.3],
                    "electrical.zero_sequence_reactance": [0.15],
                    "electrical.zero_sequence_capacitance": [0.0],
                    "electrical.zero_sequence_tan_delta": [0.0],
                }
            )
        if fault_type is not None:
            data["electrical_fault_entities"] = {
                "id": [60],
                "connection.to_id": [2],
                "electrical.fault_type": [fault_type],
            }
        return data

    @staticmethod
    def _run(config, data, schema):
        model = Model(config)
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data(
                DATASET_NAME, get_dataset(DATASET_NAME, "electrical_network", data)
            )
            tester.initialize()
            result, _ = tester.update(0, None)
        return result[DATASET_NAME]

    def test_asymmetric_power_flow_with_zero_sequence(self, model_config, global_schema):
        """Lines carrying zero-sequence data support asymmetric power flow."""
        out = self._run(
            {**model_config, "symmetric": False}, self._network(zero_sequence=True), global_schema
        )
        nodes = out["electrical_node_entities"]
        assert all(np.isfinite(v) for v in nodes["electrical.voltage"])
        assert all(np.isfinite(p) for p in nodes["electrical.active_power"])

    def test_unbalanced_fault_with_zero_sequence(self, model_config, global_schema):
        """A single-phase-to-ground fault needs the zero-sequence network."""
        out = self._run(
            {**model_config, "calculation_type": "short_circuit"},
            self._network(zero_sequence=True, fault_type=1),  # single_phase_to_ground
            global_schema,
        )
        faults = out["electrical_fault_entities"]
        assert faults["electrical.fault_current"][0] > 0

    def test_missing_zero_sequence_asymmetric_raises_clear_error(
        self, model_config, global_schema
    ):
        """Asymmetric power flow without zero-sequence data names the missing fields."""
        with pytest.raises(ValueError) as exc:
            self._run({**model_config, "symmetric": False}, self._network(), global_schema)
        message = str(exc.value)
        assert "r0" in message and "x0" in message
        assert "line" in message

    def test_missing_zero_sequence_unbalanced_fault_raises_clear_error(
        self, model_config, global_schema
    ):
        """An unbalanced fault without zero-sequence data is rejected up front."""
        with pytest.raises(ValueError) as exc:
            self._run(
                {**model_config, "calculation_type": "short_circuit"},
                self._network(fault_type=2),  # two_phase
                global_schema,
            )
        assert "r0" in str(exc.value)

    def test_balanced_fault_needs_no_zero_sequence(self, model_config, global_schema):
        """A three-phase fault must keep working without zero-sequence data."""
        out = self._run(
            {**model_config, "calculation_type": "short_circuit"},
            self._network(fault_type=0),  # three_phase
            global_schema,
        )
        assert out["electrical_fault_entities"]["electrical.fault_current"][0] > 0
