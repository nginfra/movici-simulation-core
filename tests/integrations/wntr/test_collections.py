"""Tests for collection classes"""

import numpy as np
import pytest

from movici_simulation_core.integrations.wntr.collections import (
    JunctionCollection,
    PipeCollection,
    SimulationResults,
)


class TestJunctionCollection:
    def test_create_junction_collection(self):
        coll = JunctionCollection(
            node_names=["j1", "j2", "j3"],
            elevations=np.array([10.0, 20.0, 30.0]),
            base_demands=np.array([0.1, 0.2, 0.3]),
            demand_patterns=["pat1", "pat1", None],
            coordinates=np.array([[0, 0], [1, 1], [2, 2]]),
        )

        assert len(coll) == 3
        assert coll.node_names == ["j1", "j2", "j3"]
        assert coll.demand_patterns[2] is None


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

    def test_get_link_results(self):
        results = SimulationResults(
            node_names=["j1"],
            node_pressures=np.array([50.0]),
            link_names=["p1", "p2"],
            link_flows=np.array([0.1, 0.2]),
            link_velocities=np.array([1.0, 1.5]),
        )

        link_res = results.get_link_results("p2")

        assert link_res["flow"] == 0.2
        assert link_res["velocity"] == 1.5

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
