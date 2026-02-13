"""Equivalence tests for Rules Model vs WNTR internal controls.

These tests verify that using Movici with external attribute updates
(simulating what the Rules Model does) produces equivalent results to
WNTR simulations with internal controls.

The goal is to demonstrate that control logic can be externalized to
the Rules Model while maintaining correct hydraulic simulation results.
"""

import numpy as np
import pytest
import wntr

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.models.drinking_water.model import Model


@pytest.fixture
def additional_attributes():
    """Register drinking water network attributes with schema."""
    # Return the list of AttributeSpec objects from the model
    return Model.get_schema_attributes()


class TestPipeStatusEquivalence:
    """Test pipe status control equivalence with WNTR."""

    @pytest.fixture
    def global_timeline_info(self):
        """Use 1-second time scale for these tests."""
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def simple_network_data(self):
        """Create a simple network: Reservoir -> Pipes -> Junctions.

        Network topology::

            R1 -(pipe1)-> J1 -(pipe2)-> J2

        This is a simple gravity-fed network suitable for testing
        pipe status control without pump convergence issues.
        """
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "data": {
                "water_reservoir_entities": {
                    "id": [1],
                    "reference": ["R1"],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [50.0],
                },
                "water_junction_entities": {
                    "id": [2, 3],
                    "reference": ["J1", "J2"],
                    "geometry.x": [100.0, 200.0],
                    "geometry.y": [0.0, 0.0],
                    "geometry.z": [10.0, 10.0],
                    "drinking_water.base_demand": [0.001, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
                    "reference": ["PIPE1", "PIPE2"],
                    "topology.from_node_id": [1, 2],
                    "topology.to_node_id": [2, 3],
                    "shape.diameter": [0.3, 0.3],
                    "shape.length": [100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0],
                    "drinking_water.minor_loss": [0.0, 0.0],
                    "operational.status": [True, True],
                },
            },
        }

    @pytest.fixture
    def init_data(self, simple_network_data):
        """Provide init data for model tester."""
        return [("water_network", simple_network_data)]

    def _build_wntr_network(self):
        """Build equivalent WNTR network for comparison.

        :return: WNTR WaterNetworkModel
        """
        wn = wntr.network.WaterNetworkModel()

        # Add reservoir
        wn.add_reservoir("n1", base_head=50.0, coordinates=(0.0, 0.0))

        # Add junctions
        wn.add_junction("n2", base_demand=0.001, elevation=10.0, coordinates=(100.0, 0.0))
        wn.add_junction("n3", base_demand=0.001, elevation=10.0, coordinates=(200.0, 0.0))

        # Add pipes
        wn.add_pipe(
            "l101",
            start_node_name="n1",
            end_node_name="n2",
            length=100.0,
            diameter=0.3,
            roughness=100.0,
            minor_loss=0.0,
        )
        wn.add_pipe(
            "l102",
            start_node_name="n2",
            end_node_name="n3",
            length=100.0,
            diameter=0.3,
            roughness=100.0,
            minor_loss=0.0,
        )

        return wn

    def _run_wntr_simulation(self, wn, duration: int = 3600) -> dict:
        """Run WNTR simulation and extract results.

        :param wn: WNTR WaterNetworkModel
        :param duration: Simulation duration in seconds
        :return: Dictionary of results
        """
        wn.options.time.duration = duration
        wn.options.time.hydraulic_timestep = 3600
        wn.options.time.report_timestep = 3600

        sim = wntr.sim.WNTRSimulator(wn)
        results = sim.run_sim()

        # Get final timestep results
        last_time = results.node["pressure"].index[-1]

        return {
            "j1_pressure": float(results.node["pressure"].loc[last_time, "n2"]),
            "j2_pressure": float(results.node["pressure"].loc[last_time, "n3"]),
            "pipe1_flow": float(results.link["flowrate"].loc[last_time, "l101"]),
            "pipe2_flow": float(results.link["flowrate"].loc[last_time, "l102"]),
        }

    def test_initial_network_matches_wntr(self, create_model_tester, init_data):
        """Test that Movici network produces same results as pure WNTR."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
            },
        }

        # Run Movici simulation
        tester = create_model_tester(Model, config)
        tester.initialize()
        result, _ = tester.update(0, None)

        # Run WNTR simulation
        wntr_network = self._build_wntr_network()
        wntr_results = self._run_wntr_simulation(wntr_network)

        # Extract Movici results
        assert result is not None, "Movici simulation should return results"
        junctions = result.get("water_network", {}).get("water_junction_entities", {})
        pipes = result.get("water_network", {}).get("water_pipe_entities", {})

        assert "drinking_water.pressure" in junctions, "Junction results should contain pressure"
        movici_j1_pressure = junctions["drinking_water.pressure"][0]
        movici_j2_pressure = junctions["drinking_water.pressure"][1]

        # Both Movici and reference use WNTR's solver, so results should match
        # within floating-point precision
        np.testing.assert_allclose(
            movici_j1_pressure,
            wntr_results["j1_pressure"],
            rtol=1e-6,
            err_msg="J1 pressure mismatch",
        )
        np.testing.assert_allclose(
            movici_j2_pressure,
            wntr_results["j2_pressure"],
            rtol=1e-6,
            err_msg="J2 pressure mismatch",
        )

        assert "drinking_water.flow" in pipes, "Pipe results should contain flow"
        movici_pipe1_flow = pipes["drinking_water.flow"][0]
        movici_pipe2_flow = pipes["drinking_water.flow"][1]

        np.testing.assert_allclose(
            movici_pipe1_flow,
            wntr_results["pipe1_flow"],
            rtol=1e-6,
            err_msg="PIPE1 flow mismatch",
        )
        np.testing.assert_allclose(
            movici_pipe2_flow,
            wntr_results["pipe2_flow"],
            rtol=1e-6,
            err_msg="PIPE2 flow mismatch",
        )

    def test_pipe_closure_matches_wntr(self, create_model_tester, init_data):
        """Test that pipe closure via external update matches WNTR control.

        Scenario:
        - t=0: Both pipes open
        - t=3600: Close PIPE2 (change queued, simulation still uses old state)
        - t=7200: Closure takes effect, compare with WNTR closed-pipe results
        """
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
            },
        }

        # Run Movici simulation
        tester = create_model_tester(Model, config)
        tester.initialize()

        # Initial state - both pipes open
        result_open, _ = tester.update(0, None)

        # Verify initial state has flow in both pipes
        assert result_open is not None, "Initial simulation should return results"
        pipes_open = result_open.get("water_network", {}).get("water_pipe_entities", {})
        assert "drinking_water.flow" in pipes_open, "Initial results should contain flow"
        # Both pipes should have positive flow when open
        assert pipes_open["drinking_water.flow"][0] > 1e-6, "PIPE1 should have flow when open"
        assert pipes_open["drinking_water.flow"][1] > 1e-6, "PIPE2 should have flow when open"

        # Close PIPE2 via external update (simulating Rules Model).
        # The change is queued; the simulation at t=3600 still uses the old state.
        tester.new_time(3600)
        pipe_close_update = {
            "water_network": {
                "water_pipe_entities": {
                    "id": [102],  # PIPE2
                    "operational.status": [False],
                }
            }
        }
        tester.update(3600, pipe_close_update)

        # t=7200: The closure takes effect in this simulation step
        tester.new_time(7200)
        result_closed, _ = tester.update(7200, None)

        # Build WNTR network with PIPE2 closed
        wntr_network = self._build_wntr_network()
        pipe2 = wntr_network.get_link("l102")
        pipe2.initial_status = wntr.network.LinkStatus.Closed
        wntr_closed_results = self._run_wntr_simulation(wntr_network)

        # Extract and compare results
        assert result_closed is not None, "Closed pipe simulation should return results"
        pipes = result_closed.get("water_network", {}).get("water_pipe_entities", {})
        assert "drinking_water.flow" in pipes, "Closed pipe results should contain flow"

        movici_pipe2_flow = pipes["drinking_water.flow"][1]  # PIPE2 index

        # PIPE2 flow should be ~0 when closed (use threshold for numerical residual)
        assert abs(movici_pipe2_flow) < 1e-6, (
            f"Closed pipe should have near-zero flow, got {movici_pipe2_flow}"
        )

        # WNTR closed pipe should also have ~0 flow
        assert abs(wntr_closed_results["pipe2_flow"]) < 1e-6, (
            "WNTR closed pipe should have near-zero flow"
        )


class TestBranchedNetworkControl:
    """Test control logic on a branched network."""

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def branched_network_data(self):
        """Create a branched network with three pipes.

        Network topology::

            R1 -(pipe1)-> J1 -(pipe2)-> J2
                            \\
                             (pipe3)-> J3

        This allows testing pipe closure isolating part of the network.
        """
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "data": {
                "water_reservoir_entities": {
                    "id": [1],
                    "reference": ["R1"],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [50.0],
                },
                "water_junction_entities": {
                    "id": [2, 3, 4],
                    "reference": ["J1", "J2", "J3"],
                    "geometry.x": [100.0, 200.0, 100.0],
                    "geometry.y": [0.0, 0.0, 100.0],
                    "geometry.z": [10.0, 10.0, 10.0],
                    "drinking_water.base_demand": [0.0, 0.001, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102, 103],
                    "reference": ["PIPE1", "PIPE2", "PIPE3"],
                    "topology.from_node_id": [1, 2, 2],
                    "topology.to_node_id": [2, 3, 4],
                    "shape.diameter": [0.3, 0.2, 0.2],
                    "shape.length": [100.0, 100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0, 100.0],
                    "drinking_water.minor_loss": [0.0, 0.0, 0.0],
                    "operational.status": [True, True, True],
                },
            },
        }

    @pytest.fixture
    def init_data(self, branched_network_data):
        return [("water_network", branched_network_data)]

    def test_branch_isolation(self, create_model_tester, init_data):
        """Test that closing a branch pipe isolates that branch correctly.

        Changes take effect one timestep after they are sent:
        - t=0: All open
        - t=3600: Queue PIPE3 closure
        - t=7200: Closure takes effect
        """
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
            },
        }

        tester = create_model_tester(Model, config)
        tester.initialize()

        def get_flow_by_id(pipe_data, pipe_id):
            """Get flow value for a specific pipe ID from result data."""
            ids = pipe_data.get("id", [])
            flows = pipe_data.get("drinking_water.flow", [])
            for i, eid in enumerate(ids):
                if eid == pipe_id:
                    return flows[i]
            return None

        # Initial state - all pipes open
        result_open, _ = tester.update(0, None)

        # Verify initial state
        assert result_open is not None, "Initial simulation should return results"
        pipe_data_open = result_open.get("water_network", {}).get("water_pipe_entities", {})
        assert "drinking_water.flow" in pipe_data_open, "Results should contain flow data"

        # Look up flows by ID (results only contain changed values)
        initial_pipe1_flow = get_flow_by_id(pipe_data_open, 101)
        initial_pipe3_flow = get_flow_by_id(pipe_data_open, 103)

        assert initial_pipe1_flow is not None, "PIPE1 should be in initial results"
        assert initial_pipe3_flow is not None, "PIPE3 should be in initial results"

        # All pipes should have flow when open
        assert initial_pipe1_flow > 1e-6, "PIPE1 should have flow when all pipes open"
        assert initial_pipe3_flow > 1e-6, "PIPE3 should have flow when open"

        # Close PIPE3 (to J3) — change is queued for next timestep
        tester.new_time(3600)
        pipe_close_update = {
            "water_network": {
                "water_pipe_entities": {
                    "id": [103],  # PIPE3
                    "operational.status": [False],
                }
            }
        }
        tester.update(3600, pipe_close_update)

        # t=7200: Closure takes effect
        tester.new_time(7200)
        result_closed, _ = tester.update(7200, None)

        # Verify closed state
        assert result_closed is not None, "Closed pipe simulation should return results"
        pipe_data_closed = result_closed.get("water_network", {}).get("water_pipe_entities", {})
        assert "drinking_water.flow" in pipe_data_closed, "Closed results should contain flow"

        # Look up flows by ID
        closed_pipe1_flow = get_flow_by_id(pipe_data_closed, 101)
        closed_pipe3_flow = get_flow_by_id(pipe_data_closed, 103)

        # PIPE3 should have zero flow after closing (use 1e-6 for numerical residual)
        assert closed_pipe3_flow is not None, "PIPE3 should be in closed results"
        assert abs(closed_pipe3_flow) < 1e-6, (
            f"Closed pipe should have zero flow, got {closed_pipe3_flow}"
        )

        # PIPE1 should still have flow (serving J2 through PIPE2)
        assert closed_pipe1_flow is not None, "PIPE1 should be in closed results"
        assert closed_pipe1_flow > 1e-6, "PIPE1 should still have flow"

        # PIPE1 flow should be less than before (no longer serving J3)
        assert closed_pipe1_flow < initial_pipe1_flow, (
            f"PIPE1 flow should decrease after closing PIPE3: "
            f"{closed_pipe1_flow} should be < {initial_pipe1_flow}"
        )


class TestWNTRTimeBasedControlEquivalence:
    """Test equivalence between Movici external updates and WNTR time-based controls.

    These tests run multi-timestep simulations comparing:
    - WNTR with internal SimTimeCondition controls
    - Movici with external status updates at the same times

    This demonstrates that the Rules Model approach produces equivalent results.
    """

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def simple_network_data(self):
        """Simple network for time-based control tests."""
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "data": {
                "water_reservoir_entities": {
                    "id": [1],
                    "reference": ["R1"],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [50.0],
                },
                "water_junction_entities": {
                    "id": [2, 3],
                    "reference": ["J1", "J2"],
                    "geometry.x": [100.0, 200.0],
                    "geometry.y": [0.0, 0.0],
                    "geometry.z": [10.0, 10.0],
                    "drinking_water.base_demand": [0.001, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
                    "reference": ["PIPE1", "PIPE2"],
                    "topology.from_node_id": [1, 2],
                    "topology.to_node_id": [2, 3],
                    "shape.diameter": [0.3, 0.3],
                    "shape.length": [100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0],
                    "drinking_water.minor_loss": [0.0, 0.0],
                    "operational.status": [True, True],
                },
            },
        }

    @pytest.fixture
    def init_data(self, simple_network_data):
        return [("water_network", simple_network_data)]

    def _build_wntr_network_with_time_control(self, close_time: int):
        """Build WNTR network with time-based control to close PIPE2.

        :param close_time: Time in seconds when to close PIPE2
        :return: WNTR WaterNetworkModel with control
        """
        wn = wntr.network.WaterNetworkModel()

        # Add reservoir
        wn.add_reservoir("n1", base_head=50.0, coordinates=(0.0, 0.0))

        # Add junctions
        wn.add_junction("n2", base_demand=0.001, elevation=10.0, coordinates=(100.0, 0.0))
        wn.add_junction("n3", base_demand=0.001, elevation=10.0, coordinates=(200.0, 0.0))

        # Add pipes
        wn.add_pipe(
            "l101",
            start_node_name="n1",
            end_node_name="n2",
            length=100.0,
            diameter=0.3,
            roughness=100.0,
        )
        wn.add_pipe(
            "l102",
            start_node_name="n2",
            end_node_name="n3",
            length=100.0,
            diameter=0.3,
            roughness=100.0,
        )

        # Add time-based control: close PIPE2 at close_time
        pipe2 = wn.get_link("l102")
        act = wntr.network.controls.ControlAction(pipe2, "status", wntr.network.LinkStatus.Closed)
        cond = wntr.network.controls.SimTimeCondition(wn, "=", close_time)
        ctrl = wntr.network.controls.Control(cond, act)
        wn.add_control("close_pipe2", ctrl)

        return wn

    def test_time_control_close_pipe_at_1h(self, create_model_tester, init_data):
        """Test time-based pipe closure: close PIPE2 at t=3600s (1 hour).

        WNTR's internal SimTimeCondition fires within the same timestep, so
        the closure is visible from t=3600 onward.  Movici's external change
        takes effect one step later (t=7200).  Both are compared at t=7200,
        when both systems have the pipe closed.
        """
        close_time = 3600  # 1 hour
        duration = 10800  # 3 hours
        timestep = 3600  # 1 hour timesteps

        # --- Run WNTR with internal time control ---
        wn = self._build_wntr_network_with_time_control(close_time)
        wn.options.time.duration = duration
        wn.options.time.hydraulic_timestep = timestep
        wn.options.time.report_timestep = timestep

        sim = wntr.sim.WNTRSimulator(wn)
        wntr_results = sim.run_sim()

        wntr_flows = {}
        for t in wntr_results.link["flowrate"].index:
            wntr_flows[int(t)] = {
                "pipe1": float(wntr_results.link["flowrate"].loc[t, "l101"]),
                "pipe2": float(wntr_results.link["flowrate"].loc[t, "l102"]),
            }

        # --- Run Movici with external updates ---
        config = {
            "dataset": "water_network",
            "options": {"hydraulic_timestep": timestep},
        }

        tester = create_model_tester(Model, config)
        tester.initialize()

        # t=0: Initial state (both pipes open)
        result_t0, _ = tester.update(0, None)
        assert result_t0 is not None
        pipes_t0 = result_t0["water_network"]["water_pipe_entities"]
        movici_pipe1_t0 = pipes_t0["drinking_water.flow"][0]
        movici_pipe2_t0 = pipes_t0["drinking_water.flow"][1]

        # t=3600: Send PIPE2 closure — queued, simulation uses old state
        tester.new_time(3600)
        pipe_close_update = {
            "water_network": {"water_pipe_entities": {"id": [102], "operational.status": [False]}}
        }
        tester.update(3600, pipe_close_update)

        # t=7200: Closure takes effect
        tester.new_time(7200)
        result_t7200, _ = tester.update(7200, None)
        assert result_t7200 is not None
        pipes_t7200 = result_t7200["water_network"]["water_pipe_entities"]
        movici_pipe1_t7200 = pipes_t7200["drinking_water.flow"][0]
        movici_pipe2_t7200 = pipes_t7200["drinking_water.flow"][1]

        # --- Compare at t=0: both open ---
        np.testing.assert_allclose(
            movici_pipe1_t0,
            wntr_flows[0]["pipe1"],
            rtol=1e-6,
            err_msg="PIPE1 flow mismatch at t=0",
        )
        np.testing.assert_allclose(
            movici_pipe2_t0,
            wntr_flows[0]["pipe2"],
            rtol=1e-6,
            err_msg="PIPE2 flow mismatch at t=0",
        )

        # --- Compare at t=7200: both have PIPE2 closed ---
        assert abs(wntr_flows[7200]["pipe2"]) < 1e-6, (
            f"WNTR PIPE2 should be closed at t=7200, got {wntr_flows[7200]['pipe2']}"
        )
        assert abs(movici_pipe2_t7200) < 1e-6, (
            f"Movici PIPE2 should be closed at t=7200, got {movici_pipe2_t7200}"
        )
        np.testing.assert_allclose(
            movici_pipe1_t7200,
            wntr_flows[7200]["pipe1"],
            rtol=1e-6,
            err_msg="PIPE1 flow mismatch at t=7200",
        )

    def test_time_control_reopen_pipe(self, create_model_tester, init_data):
        """Test time-based pipe open/close/reopen cycle.

        Movici external changes take effect one timestep after they are sent:
        - t=0: Both pipes open
        - t=3600: Queue close PIPE2 (still open in this step's simulation)
        - t=7200: Closure visible; queue reopen PIPE2
        - t=10800: Reopen visible

        WNTR internal controls fire within the same timestep:
        - t=3600: Close fires → pipe closed
        - t=7200: Reopen fires → pipe open

        The closed phase cannot be compared at the same timestamp (WNTR has
        already reopened at t=7200 while Movici just closed).  Instead we
        compare the closed-pipe Movici result against WNTR t=3600.  The
        reopened phase is compared at t=10800 where both have the pipe open.
        """
        timestep = 3600

        # --- Build WNTR with close and reopen controls ---
        wn = wntr.network.WaterNetworkModel()
        wn.add_reservoir("n1", base_head=50.0)
        wn.add_junction("n2", base_demand=0.001, elevation=10.0)
        wn.add_junction("n3", base_demand=0.001, elevation=10.0)
        wn.add_pipe("l101", "n1", "n2", length=100.0, diameter=0.3, roughness=100.0)
        wn.add_pipe("l102", "n2", "n3", length=100.0, diameter=0.3, roughness=100.0)

        pipe2 = wn.get_link("l102")

        act_close = wntr.network.controls.ControlAction(
            pipe2, "status", wntr.network.LinkStatus.Closed
        )
        cond_close = wntr.network.controls.SimTimeCondition(wn, "=", 3600)
        wn.add_control("close_pipe2", wntr.network.controls.Control(cond_close, act_close))

        act_open = wntr.network.controls.ControlAction(
            pipe2, "status", wntr.network.LinkStatus.Open
        )
        cond_open = wntr.network.controls.SimTimeCondition(wn, "=", 7200)
        wn.add_control("open_pipe2", wntr.network.controls.Control(cond_open, act_open))

        wn.options.time.duration = 10800
        wn.options.time.hydraulic_timestep = timestep
        wn.options.time.report_timestep = timestep

        sim = wntr.sim.WNTRSimulator(wn)
        wntr_results = sim.run_sim()

        # --- Run Movici with external updates ---
        config = {
            "dataset": "water_network",
            "options": {"hydraulic_timestep": timestep},
        }

        tester = create_model_tester(Model, config)
        tester.initialize()

        # t=0: Initial (open)
        result0, _ = tester.update(0, None)

        # t=3600: Queue close
        tester.new_time(3600)
        close_update = {
            "water_network": {"water_pipe_entities": {"id": [102], "operational.status": [False]}}
        }
        tester.update(3600, close_update)

        # t=7200: Closure takes effect; queue reopen
        tester.new_time(7200)
        open_update = {
            "water_network": {"water_pipe_entities": {"id": [102], "operational.status": [True]}}
        }
        result_closed, _ = tester.update(7200, open_update)

        # t=10800: Reopen takes effect
        tester.new_time(10800)
        result_reopened, _ = tester.update(10800, None)

        # --- Compare: closed phase ---
        # WNTR closed at t=3600, Movici closed at t=7200 (same hydraulic state)
        wntr_pipe2_t3600 = float(wntr_results.link["flowrate"].loc[3600, "l102"])
        assert abs(wntr_pipe2_t3600) < 1e-6, (
            f"WNTR PIPE2 should be closed at t=3600, got {wntr_pipe2_t3600}"
        )

        assert result_closed is not None
        pipes_closed = result_closed["water_network"]["water_pipe_entities"]
        movici_pipe2_closed = pipes_closed["drinking_water.flow"][1]
        assert abs(movici_pipe2_closed) < 1e-6, (
            f"Movici PIPE2 should be closed at t=7200, got {movici_pipe2_closed}"
        )

        # --- Compare: reopened phase at t=10800 (same timestamp) ---
        wntr_pipe2_t10800 = float(wntr_results.link["flowrate"].loc[10800, "l102"])
        wntr_pipe1_t10800 = float(wntr_results.link["flowrate"].loc[10800, "l101"])

        assert result_reopened is not None
        pipes_reopened = result_reopened["water_network"]["water_pipe_entities"]
        movici_pipe2_reopened = pipes_reopened["drinking_water.flow"][1]
        movici_pipe1_reopened = pipes_reopened["drinking_water.flow"][0]

        np.testing.assert_allclose(
            movici_pipe2_reopened,
            wntr_pipe2_t10800,
            rtol=1e-6,
            err_msg="PIPE2 flow mismatch at t=10800 after reopening",
        )
        np.testing.assert_allclose(
            movici_pipe1_reopened,
            wntr_pipe1_t10800,
            rtol=1e-6,
            err_msg="PIPE1 flow mismatch at t=10800 after reopening",
        )


class TestTankLevelProgression:
    """Verify that tank levels carry forward across timesteps via WNTR pause/restart.

    With the persistent simulator pattern, WNTR's internal tank state is preserved
    between simulation steps.  A tank with net outflow should show progressive
    level decreases rather than resetting to ``init_level`` every step.
    """

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def tank_drain_network_data(self):
        """Gravity-fed network with a tank that drains over time.

        Topology::

            R1 -(pipe1)-> T1 -(pipe2)-> J1

        The reservoir (head=30) feeds the tank (elev=20, init_level=5, head=25),
        while J1 (elev=0, demand=0.01) draws from the tank.  With a small inlet
        pipe and large demand, the tank should drain progressively.
        """
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "data": {
                "water_reservoir_entities": {
                    "id": [1],
                    "reference": ["R1"],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [30.0],
                },
                "water_tank_entities": {
                    "id": [2],
                    "reference": ["T1"],
                    "geometry.x": [100.0],
                    "geometry.y": [0.0],
                    "geometry.z": [20.0],
                    "shape.diameter": [5.0],
                    "drinking_water.level": [5.0],
                    "drinking_water.min_level": [0.5],
                    "drinking_water.max_level": [10.0],
                },
                "water_junction_entities": {
                    "id": [3],
                    "reference": ["J1"],
                    "geometry.x": [200.0],
                    "geometry.y": [0.0],
                    "geometry.z": [0.0],
                    "drinking_water.base_demand": [0.005],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
                    "reference": ["PIPE1", "PIPE2"],
                    "topology.from_node_id": [1, 2],
                    "topology.to_node_id": [2, 3],
                    "shape.diameter": [0.3, 0.3],
                    "shape.length": [100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0],
                },
            },
        }

    @pytest.fixture
    def init_data(self, tank_drain_network_data):
        return [("water_network", tank_drain_network_data)]

    def test_tank_level_changes_across_timesteps(self, create_model_tester, init_data):
        """Tank level should change progressively, not reset to init_level each step."""
        timestep = 3600
        config = {
            "dataset": "water_network",
            "options": {"hydraulic_timestep": timestep},
        }

        tester = create_model_tester(Model, config)
        tester.initialize()

        levels = []
        num_steps = 4

        for step in range(num_steps):
            t = step * timestep
            if step > 0:
                tester.new_time(t)
            result, _ = tester.update(t, None)
            if result is not None:
                tanks = result.get("water_network", {}).get("water_tank_entities", {})
                if "drinking_water.level" in tanks:
                    levels.append(tanks["drinking_water.level"][0])

        # We should have at least 2 distinct level readings
        assert len(levels) >= 2, f"Expected multiple level readings, got {len(levels)}"

        # Tank levels must not all be the same (would indicate reset to init_level)
        unique_levels = set(round(lv, 6) for lv in levels)
        assert len(unique_levels) > 1, (
            f"Tank level should change across timesteps but stayed at {levels}"
        )
