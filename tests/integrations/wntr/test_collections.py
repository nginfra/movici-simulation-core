"""Tests for WNTR collection classes."""

import numpy as np
import pytest

from movici_simulation_core.integrations.wntr.collections import (
    JunctionCollection,
    PipeCollection,
    PumpCollection,
    ReservoirCollection,
    SimulationResults,
    TankCollection,
    ValveCollection,
)


class TestJunctionCollection:
    def test_create_junction_collection(self):
        coll = JunctionCollection(
            node_names=["j1", "j2", "j3"],
            elevations=np.array([10.0, 20.0, 30.0]),
            base_demands=np.array([0.1, 0.2, 0.3]),
            demand_factors=np.array([1.0, 1.5, 0.8]),
            coordinates=np.array([[0, 0], [1, 1], [2, 2]]),
        )

        assert len(coll) == 3
        assert coll.node_names == ["j1", "j2", "j3"]
        assert coll.demand_factors[1] == 1.5

    def test_junction_collection_without_optional_fields(self):
        coll = JunctionCollection(
            node_names=["j1"],
            elevations=np.array([10.0]),
            base_demands=np.array([0.1]),
        )

        assert len(coll) == 1
        assert coll.demand_factors is None
        assert coll.coordinates is None


class TestTankCollection:
    def test_create_tank_collection_cylindrical(self):
        coll = TankCollection(
            node_names=["t1"],
            elevations=np.array([50.0]),
            init_levels=np.array([5.0]),
            min_levels=np.array([1.0]),
            max_levels=np.array([10.0]),
            diameters=np.array([10.0]),
        )

        assert len(coll) == 1
        assert coll.diameters[0] == 10.0
        assert coll.volume_curves is None

    def test_create_tank_collection_with_overflow(self):
        coll = TankCollection(
            node_names=["t1", "t2"],
            elevations=np.array([50.0, 60.0]),
            init_levels=np.array([5.0, 6.0]),
            overflows=np.array([True, False]),
        )

        assert coll.overflows[0]
        assert not coll.overflows[1]


class TestReservoirCollection:
    def test_create_reservoir_collection(self):
        coll = ReservoirCollection(
            node_names=["r1"],
            base_heads=np.array([100.0]),
            head_factors=np.array([1.2]),
        )

        assert len(coll) == 1
        assert coll.base_heads[0] == 100.0
        assert coll.head_factors[0] == 1.2


class TestPipeCollection:
    def test_create_pipe_collection(self):
        coll = PipeCollection(
            link_names=["p1", "p2"],
            from_nodes=["j1", "j2"],
            to_nodes=["j2", "j3"],
            lengths=np.array([100.0, 150.0]),
            diameters=np.array([0.3, 0.4]),
            roughnesses=np.array([100.0, 100.0]),
        )

        assert len(coll) == 2
        assert coll.from_nodes == ["j1", "j2"]
        assert coll.to_nodes == ["j2", "j3"]

    def test_pipe_collection_with_check_valves(self):
        coll = PipeCollection(
            link_names=["p1", "p2"],
            from_nodes=["j1", "j2"],
            to_nodes=["j2", "j3"],
            lengths=np.array([100.0, 150.0]),
            diameters=np.array([0.3, 0.4]),
            roughnesses=np.array([100.0, 100.0]),
            check_valves=np.array([True, False]),
        )

        assert coll.check_valves[0]
        assert not coll.check_valves[1]


class TestPumpCollection:
    def test_create_power_pump_collection(self):
        coll = PumpCollection(
            link_names=["pump1"],
            from_nodes=["r1"],
            to_nodes=["j1"],
            pump_types=["power"],
            powers=np.array([1000.0]),
        )

        assert len(coll) == 1
        assert coll.pump_types[0] == "power"
        assert coll.powers[0] == 1000.0
        assert coll.head_curves is None

    def test_create_head_pump_collection(self):
        head_curve = np.array([[0.0, 100.0], [0.1, 80.0], [0.2, 50.0]])
        coll = PumpCollection(
            link_names=["pump1"],
            from_nodes=["r1"],
            to_nodes=["j1"],
            pump_types=["head"],
            head_curves=[head_curve],
            speeds=np.array([1.0]),
        )

        assert coll.pump_types[0] == "head"
        assert coll.head_curves[0].shape == (3, 2)
        assert coll.speeds[0] == 1.0


class TestValveCollection:
    def test_create_prv_collection(self):
        coll = ValveCollection(
            link_names=["v1"],
            from_nodes=["j1"],
            to_nodes=["j2"],
            valve_types=["PRV"],
            diameters=np.array([0.3]),
            valve_pressures=np.array([50.0]),
        )

        assert len(coll) == 1
        assert coll.valve_types[0] == "PRV"
        assert coll.get_setting(0) == 50.0

    def test_create_fcv_collection(self):
        coll = ValveCollection(
            link_names=["v1"],
            from_nodes=["j1"],
            to_nodes=["j2"],
            valve_types=["FCV"],
            diameters=np.array([0.3]),
            valve_flows=np.array([0.05]),
        )

        assert coll.get_setting(0) == 0.05

    def test_create_tcv_collection(self):
        coll = ValveCollection(
            link_names=["v1"],
            from_nodes=["j1"],
            to_nodes=["j2"],
            valve_types=["TCV"],
            diameters=np.array([0.3]),
            valve_loss_coefficients=np.array([10.0]),
        )

        assert coll.get_setting(0) == 10.0

    def test_gpv_setting_returns_zero(self):
        coll = ValveCollection(
            link_names=["v1"],
            from_nodes=["j1"],
            to_nodes=["j2"],
            valve_types=["GPV"],
            diameters=np.array([0.3]),
            valve_curves=[np.array([[0.0, 0.0], [0.1, 5.0]])],
        )

        # GPV uses curve, not scalar setting
        assert coll.get_setting(0) == 0.0

    def test_get_setting_missing_raises(self):
        coll = ValveCollection(
            link_names=["v1"],
            from_nodes=["j1"],
            to_nodes=["j2"],
            valve_types=["PRV"],
            diameters=np.array([0.3]),
            # No valve_pressures provided
        )

        with pytest.raises(ValueError, match="No setting available"):
            coll.get_setting(0)


class TestSimulationResults:
    def test_get_node_results(self):
        results = SimulationResults(
            node_names=["j1", "j2"],
            node_pressures=np.array([50.0, 60.0]),
            node_heads=np.array([110.0, 120.0]),
            node_demands=np.array([0.1, 0.2]),
            link_names=["p1"],
            link_flows=np.array([0.15]),
        )

        node_res = results.get_node_results("j1")

        assert node_res["pressure"] == 50.0
        assert node_res["head"] == 110.0
        assert node_res["demand"] == 0.1

    def test_get_node_results_with_level(self):
        results = SimulationResults(
            node_names=["t1"],
            node_pressures=np.array([0.0]),
            node_heads=np.array([55.0]),
            node_demands=np.array([0.0]),
            node_levels=np.array([5.0]),
            link_names=[],
        )

        node_res = results.get_node_results("t1")
        assert node_res["level"] == 5.0

    def test_get_link_results(self):
        results = SimulationResults(
            node_names=["j1"],
            node_pressures=np.array([50.0]),
            link_names=["p1", "p2"],
            link_flows=np.array([0.1, 0.2]),
            link_velocities=np.array([1.0, 1.5]),
            link_headlosses=np.array([2.0, 3.0]),
        )

        link_res = results.get_link_results("p2")

        assert link_res["flow"] == 0.2
        assert link_res["velocity"] == 1.5
        assert link_res["headloss"] == 3.0

    def test_get_missing_element(self):
        results = SimulationResults(
            node_names=["j1"],
            node_pressures=np.array([50.0]),
            link_names=["p1"],
            link_flows=np.array([0.1]),
        )

        node_res = results.get_node_results("j999")
        link_res = results.get_link_results("p999")

        assert node_res == {}
        assert link_res == {}
