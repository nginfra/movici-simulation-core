"""Integration tests for water network simulation model.

.. note::
   Controls are handled by the Movici Rules Model, not internally.
   See ``test_rules_model_equivalence.py`` for control behavior tests.
"""

import numpy as np
import pytest
import wntr
from jsonschema import ValidationError

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.models.drinking_water.model import Model
from movici_simulation_core.testing.model_tester import ModelTester


def wn_from_tester(tester: ModelTester):
    """returns the wntr network from a ModelTester configured with the drinking_water model"""
    return tester.model.network.wn


class TestConfigSchema:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 1800,
            },
        }

        model = Model(config)
        assert model.dataset_name == "water_network"
        assert model.hydraulic_timestep == 1800

    def test_invalid_configuration(self):
        with pytest.raises(ValidationError):
            Model({})


class TestHydraulicOptionsFromDataset:
    """Test that WNTR options are read from the dataset general section."""

    @pytest.fixture
    def additional_attributes(self):
        return Model.get_schema_attributes()

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    def _make_network_data(self, general=None, roughness=100.0):
        data = {
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
                    "id": [2],
                    "reference": ["J1"],
                    "geometry.x": [100.0],
                    "geometry.y": [0.0],
                    "geometry.z": [10.0],
                    "drinking_water.base_demand": [0.001],
                },
                "water_pipe_entities": {
                    "id": [101],
                    "reference": ["PIPE1"],
                    "topology.from_node_id": [1],
                    "topology.to_node_id": [2],
                    "shape.diameter": [0.3],
                    "shape.length": [100.0],
                    "drinking_water.roughness": [roughness],
                },
            },
        }
        if general is not None:
            data["general"] = general
        return data

    @pytest.fixture
    def model_config(self):
        return {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
            },
        }

    def test_options_applied_from_general_section(self, create_model_tester, model_config):
        """Test that data options from dataset general section are applied."""
        network = self._make_network_data(
            general={
                "hydraulic": {
                    "viscosity": 1.5,
                    "specific_gravity": 0.98,
                }
            },
        )

        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", network)
        tester.initialize()

        wn = wn_from_tester(tester)
        assert wn.options.hydraulic.headloss == "H-W"
        assert wn.options.hydraulic.viscosity == 1.5
        assert wn.options.hydraulic.specific_gravity == 0.98

    def test_defaults_when_no_general_section(self, create_model_tester, model_config):
        """Test that WNTR defaults are used when no general section."""
        network = self._make_network_data()

        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", network)
        tester.initialize()

        wn = wn_from_tester(tester)
        assert wn.options.hydraulic.headloss == "H-W"
        assert wn.options.hydraulic.viscosity == 1.0
        assert wn.options.hydraulic.specific_gravity == 1.0

    def test_solver_options_from_model_config(self, create_model_tester):
        """Test that solver options from model config 'options' key are applied."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic": {
                    "trials": 100,
                    "accuracy": 0.01,
                },
            },
        }
        network = self._make_network_data()

        tester = create_model_tester(Model, config)
        tester.add_init_data("water_network", network)
        tester.initialize()

        wn = wn_from_tester(tester)
        assert wn.options.hydraulic.trials == 100
        assert wn.options.hydraulic.accuracy == 0.01

    def test_config_and_general_combined(self, create_model_tester):
        """Test that model config and dataset general are combined."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic": {
                    "trials": 100,
                    "accuracy": 0.01,
                },
            },
        }
        network = self._make_network_data(general={"hydraulic": {"viscosity": 1.5}})

        tester = create_model_tester(Model, config)
        tester.add_init_data("water_network", network)
        tester.initialize()

        wn = wn_from_tester(tester)
        assert wn.options.hydraulic.viscosity == 1.5
        assert wn.options.hydraulic.trials == 100
        assert wn.options.hydraulic.accuracy == 0.01


@pytest.fixture
def additional_attributes():
    """Register drinking water network attributes with schema."""
    # Return the list of AttributeSpec objects from the model
    return Model.get_schema_attributes()


class TestDrinkingWaterModelBase:
    @pytest.fixture
    def model_config(self):
        return {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
            },
        }

    @pytest.fixture
    def tester(self, create_model_tester, model_config):
        return create_model_tester(Model, model_config)

    @pytest.fixture
    def network_data(self):
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
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [50.0],
                },
                "water_junction_entities": {
                    "id": [2, 3],
                    "geometry.x": [100.0, 200.0],
                    "geometry.y": [0.0, 0.0],
                    "geometry.z": [10.0, 10.0],
                    "drinking_water.base_demand": [0.001, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
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
    def global_timeline_info(self):
        """Use 1-second time scale for these tests."""
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def init_data(self, network_data):
        """Provide init data for model tester."""
        return [("water_network", network_data)]

    @pytest.fixture
    def wntr_network(self, network_data):
        wn = wntr.network.WaterNetworkModel()

        data = network_data["data"]
        elements_by_entity_id: dict[int, str] = {}
        if reservoirs := data.get("water_reservoir_entities"):
            for idx, id in enumerate(reservoirs["id"]):
                name = elements_by_entity_id[id] = f"R{id}"
                wn.add_reservoir(name, base_head=reservoirs["drinking_water.base_head"][idx])

        if junctions := data.get("water_junction_entities"):
            for idx, id in enumerate(junctions["id"]):
                name = elements_by_entity_id[id] = f"J{id}"
                wn.add_junction(
                    name,
                    base_demand=junctions["drinking_water.base_demand"][idx],
                    elevation=junctions["geometry.z"][idx],
                )

        if pipes := data.get("water_pipe_entities"):
            for idx, id in enumerate(pipes["id"]):
                name = elements_by_entity_id[id] = f"P{id}"
                operational_status = (
                    pipes["operational_status"][idx] if "operational_status" in pipes else True
                )
                wn.add_pipe(
                    name,
                    start_node_name=elements_by_entity_id[pipes["topology.from_node_id"][idx]],
                    end_node_name=elements_by_entity_id[pipes["topology.to_node_id"][idx]],
                    length=pipes["shape.length"][idx],
                    diameter=pipes["shape.diameter"][idx],
                    roughness=pipes["drinking_water.roughness"][idx],
                    minor_loss=pipes["drinking_water.minor_loss"][idx],
                    initial_status="OPEN" if operational_status else "CLOSED",
                )
        return wn

    def _run_wntr_simulation(
        self,
        wn: wntr.network.WaterNetworkModel,
        duration=3600,
        hydraulic_timestep=3600,
        report_timestep=3600,
    ):
        """Run WNTR simulation and extract results.

        :param wn: WNTR WaterNetworkModel
        :param duration: Simulation duration in seconds
        :param hydraulic_timestep: Simulation hydraulic timestep in seconds
        :param report_timestep: Simulation report timestep in seconds
        :return: WNTR SimulationResults
        """
        wn.options.time.duration = duration
        wn.options.time.hydraulic_timestep = hydraulic_timestep
        wn.options.time.report_timestep = report_timestep

        sim = wntr.sim.WNTRSimulator(wn)
        return sim.run_sim()


class TestSimpleNetwork(TestDrinkingWaterModelBase):
    """Test pipe status control equivalence with WNTR."""

    def test_initial_network_matches_wntr(self, tester, wntr_network, model_config):
        """Test that Movici network produces same results as pure WNTR."""

        # Run Movici simulation
        tester.initialize()
        result, _ = tester.update(0, None)
        assert result is not None, "Movici simulation should return results"
        junctions = result.get("water_network", {}).get("water_junction_entities", {})
        pipes = result.get("water_network", {}).get("water_pipe_entities", {})

        # Run WNTR simulation
        wntr_results = self._run_wntr_simulation(wntr_network, 0)
        wntr_pressure = wntr_results.node["pressure"].loc[0, ["J2", "J3"]].values
        wntr_flowrate = wntr_results.link["flowrate"].loc[0, ["P101", "P102"]].values

        assert "drinking_water.pressure" in junctions, "Junction results should contain pressure"
        np.testing.assert_array_equal(np.array(junctions["drinking_water.pressure"]) > 0, True)

        np.testing.assert_allclose(junctions["drinking_water.pressure"], wntr_pressure)
        np.testing.assert_allclose(pipes["drinking_water.flow"], wntr_flowrate)

    def test_close_pipe(self, tester):
        """Test that pipe closure via external update sets the flow to 0.

        Scenario:
        - t=0: Both pipes open
        - t=3600: Close PIPE2 (change queued, simulation still uses old state)
        - t=7200: Closure takes effect, compare with WNTR closed-pipe results
        """
        tester.initialize()

        # Initial state - both pipes open
        result_open, _ = tester.update(0, None)

        # Verify initial state has flow in both pipes
        assert result_open is not None, "Initial simulation should return results"
        pipes_open = result_open["water_network"]["water_pipe_entities"]

        np.testing.assert_array_equal(np.array(pipes_open["drinking_water.flow"]) > 1e-6, True)

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

        # Extract and compare results
        assert result_closed is not None, "Closed pipe simulation should return results"
        pipes_closed = result_closed["water_network"]["water_pipe_entities"]
        flowrate = pipes_closed["drinking_water.flow"]

        # Verify pipe2 has no flow
        assert flowrate[0] > 1e-6, "P101 should have flow when open"
        assert flowrate[1] < 1e-6, "P102 should have no flow when closed"


class TestBranchedNetworkControl(TestDrinkingWaterModelBase):
    """Test control logic on a branched network."""

    @pytest.fixture
    def network_data(self):
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
                },
            },
        }

    def test_branch_isolation(self, tester):
        """Test that closing a branch pipe isolates that branch correctly.

        Changes take effect one timestep after they are sent:
        - t=0: All open
        - t=3600: Queue PIPE3 closure
        - t=7200: Closure takes effect
        """
        """Test that closing a branch pipe isolates that branch correctly."""
        tester.initialize()

        # Initial state - all pipes open
        result_open, _ = tester.update(0, None)
        assert result_open is not None, "Initial simulation should return results"

        # Verify initial state
        flow_open = result_open["water_network"]["water_pipe_entities"]["drinking_water.flow"]
        np.testing.assert_array_equal(np.array(flow_open) > 1e-6, True)

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
        assert result_closed is not None, "Closed pipe simulation should return results"

        # Verify closed state
        pipes_closed = result_closed["water_network"]["water_pipe_entities"]

        assert pipes_closed["id"] == [101, 103]  # pipe 102 should not be changed, so not in update
        flow_closed = pipes_closed["drinking_water.flow"]

        # Pipe 103 should have no flow
        np.testing.assert_allclose(np.array(flow_closed) > 1e-6, [True, False])

        # PIPE1 flow should be less than before (no longer serving J3)
        assert flow_closed[0] < flow_open[0], "PIPE1 flow should decrease after closing PIPE3"

    def test_close_and_reopen_pipe_results_in_no_change(self, tester):
        tester.initialize()

        # Initial state - all pipes open
        result_open, _ = tester.update(0, None)
        assert result_open is not None, "Initial simulation should return results"

        # Close and reopen pipe
        tester.new_time(3600)
        tester.update(
            3600,
            {
                "water_network": {
                    "water_pipe_entities": {
                        "id": [103],  # PIPE3
                        "operational.status": [False],
                    }
                }
            },
        )
        tester.update(
            3600,
            {
                "water_network": {
                    "water_pipe_entities": {
                        "id": [103],  # PIPE3
                        "operational.status": [True],
                    }
                }
            },
        )

        # t=7200: No net effect expected
        tester.new_time(7200)
        result_closed, _ = tester.update(7200, None)
        assert result_closed is None, "No change expected"


class TestTankLevelProgression(TestDrinkingWaterModelBase):
    """Verify that tank levels carry forward across timesteps via WNTR pause/restart.

    With the persistent simulator pattern, WNTR's internal tank state is preserved
    between simulation steps.  A tank with net outflow should show progressive
    level decreases rather than resetting to ``init_level`` every step.
    """

    @pytest.fixture
    def network_data(self):
        """A Tank draining into a reservoir

        Topology::

            T1 -(pipe1)-> R1

        The tank has a higher elevation than the reservoir, so it drains into it.
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
                    "drinking_water.base_head": [0.0],
                },
                "water_tank_entities": {
                    "id": [2],
                    "reference": ["T1"],
                    "geometry.x": [100.0],
                    "geometry.y": [0.0],
                    "geometry.z": [1.0],
                    "shape.diameter": [5.0],
                    "drinking_water.level": [5.0],
                    "drinking_water.min_level": [0.0],
                    "drinking_water.max_level": [5.0],
                },
                "water_pipe_entities": {
                    "id": [101],
                    "reference": ["PIPE1"],
                    "topology.from_node_id": [2],
                    "topology.to_node_id": [1],
                    # with the pipe diameter we tweak how quickly the tank drains
                    "shape.diameter": [0.05],
                    "shape.length": [100.0],
                    "drinking_water.roughness": [100.0],
                },
            },
        }

    @pytest.mark.xfail
    def test_tank_level_at_initial_value(self, tester):
        """At t=0, the tank should be at initial level, so no update to its level is expected"""

        tester.initialize()
        tester.new_time(0)
        result, _ = tester.update(0, None)

        assert "water_tank_entities" not in result["water_network"]

    def test_tank_level_changes_across_timesteps(self, tester, model_config):
        """Tank level should change progressively, not reset to init_level each step."""
        timestep = model_config["options"]["hydraulic_timestep"]

        tester.initialize()

        levels = []
        num_steps = 4

        for step in range(num_steps):
            t = step * timestep
            if step > 0:
                tester.new_time(t)
            result, _ = tester.update(t, None)
            assert result is not None
            levels.append(
                result["water_network"]["water_tank_entities"]["drinking_water.level"][0]
            )
        assert np.all(np.diff(levels) < 0)


class TestMixedPumpTypes(TestDrinkingWaterModelBase):
    """Test that results are correctly assigned when HEAD and POWER pumps coexist.

    WNTR groups HeadPumps before PowerPumps in the results DataFrame,
    regardless of creation order.  This test verifies that name-based
    lookup produces correct results even when entity order differs from
    WNTR's internal ordering.
    """

    @pytest.fixture
    def model_config(self):
        return {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 10,
            },
        }

    @pytest.fixture
    def network_data(self):
        r"""Network with mixed POWER and HEAD pumps.

        Topology::

            R1 -(POWER pump PU201)-> T21
               \(HEAD  pump PU202)-> T22
               \(POWER pump PU203)-> T23
        """
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "general": {
                "enum": {
                    "pump_type": ["power", "head"],
                    "link_status": ["Closed", "Open", "Active", "CV"],
                },
            },
            "data": {
                "water_reservoir_entities": {
                    "id": [1],
                    "reference": ["R1"],
                    "geometry.x": [0.0],
                    "geometry.y": [0.0],
                    "drinking_water.base_head": [0.0],
                },
                "water_tank_entities": {
                    "id": [21, 22, 23],
                    "reference": ["T21", "T22", "T23"],
                    "geometry.x": [0.0] * 3,
                    "geometry.y": [0.0] * 3,
                    "geometry.z": [1.0] * 3,
                    "shape.diameter": [0.3] * 3,
                    "drinking_water.level": [0.0] * 3,
                    "drinking_water.min_level": [0.0] * 3,
                    "drinking_water.max_level": [5000.0] * 3,
                },
                "water_pump_entities": {
                    "id": [201, 202, 203],
                    "reference": ["PU201-POWER", "PU202-HEAD", "PU203-POWER"],
                    "topology.from_node_id": [1, 1, 1],
                    "topology.to_node_id": [21, 22, 23],
                    "drinking_water.pump_type": [0, 1, 0],
                    "drinking_water.power": [1000.0, 0.0, 500],
                    "drinking_water.head_curve": [
                        None,
                        [[0.0, 50.0], [0.01, 0.0]],
                        None,
                    ],
                },
            },
        }

    def test_mixed_pump_results_correctly_assigned(self, tester):
        """Verify results map to the correct pump when types are mixed."""
        tester.initialize()
        result, _ = tester.update(0, None)

        assert result is not None
        pumps = result["water_network"]["water_pump_entities"]
        flows = pumps["drinking_water.flow"]

        # assert we have nonzero flow
        np.testing.assert_equal(np.array(flows) > 0, True)
        assert len(np.unique(flows)) == len(flows)

        # Confirm we've assigend the correct pump to the correct position
        wn = wn_from_tester(tester)
        assert wn.get_link("PU201").flow == pytest.approx(flows[0])
        assert wn.get_link("PU202").flow == pytest.approx(flows[1])
        assert wn.get_link("PU203").flow == pytest.approx(flows[2])


class TestValveStatus(TestDrinkingWaterModelBase):
    """Test valve operational.status for initial state and dynamic changes."""

    @pytest.fixture
    def valve_open(self):
        return True

    @pytest.fixture
    def network_data(self, valve_open):
        """Network with a PRV valve.

        Topology::

            R1 -(pipe P101)-> J1 -(PRV V301)-> J2 -(pipe P102)-> J3
        """
        return {
            "version": 4,
            "name": "water_network",
            "type": "water_network",
            "general": {
                "enum": {
                    "valve_type": ["PRV", "PSV", "FCV", "TCV"],
                    "link_status": ["Closed", "Open", "Active", "CV"],
                },
            },
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
                    "geometry.x": [100.0, 200.0, 300.0],
                    "geometry.y": [0.0, 0.0, 0.0],
                    "geometry.z": [10.0, 10.0, 10.0],
                    "drinking_water.base_demand": [0.0, 0.0, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
                    "reference": ["PIPE1", "PIPE2"],
                    "topology.from_node_id": [1, 3],
                    "topology.to_node_id": [2, 4],
                    "shape.diameter": [0.3, 0.3],
                    "shape.length": [100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0],
                },
                "water_valve_entities": {
                    "id": [301],
                    "reference": ["PRV1"],
                    "topology.from_node_id": [2],
                    "topology.to_node_id": [3],
                    "drinking_water.valve_type": [0],
                    "shape.diameter": [0.3],
                    "drinking_water.valve_pressure": [30.0],
                    "operational.status": [valve_open],
                },
            },
        }

    @pytest.mark.parametrize("valve_open", [True, False, None])
    def test_valve_initial_status(self, tester, valve_open):
        """Valves should be open according to operational.status, or default open when that
        attribute is undefined"""

        tester.initialize()
        result, _ = tester.update(0, None)
        assert result is not None

        expected_open = valve_open if valve_open is not None else True
        valves = result["water_network"]["water_valve_entities"]
        assert (abs(valves["drinking_water.flow"][0]) > 1e-10) is expected_open

    @pytest.mark.parametrize("valve_open", [False])  # a single parametrization to change fixture
    def test_valve_status_change_reopens(self, tester):
        """Changing valve status from closed to active should restore flow."""

        tester.initialize()

        # t=0: valve closed
        result_closed, _ = tester.update(0, None)
        assert (
            abs(result_closed["water_network"]["water_valve_entities"]["drinking_water.flow"][0])
            < 1e-10
        )

        # t=3600: send status change to reopen
        tester.new_time(3600)
        update = {
            "water_network": {
                "water_valve_entities": {
                    "id": [301],
                    "operational.status": [True],
                }
            }
        }
        tester.update(3600, update)

        # t=7200: valve active, flow should resume
        tester.new_time(7200)
        result_open, _ = tester.update(7200, None)

        assert result_open is not None
        valve_flow = result_open["water_network"]["water_valve_entities"]["drinking_water.flow"][0]
        assert abs(valve_flow) > 1e-6, f"Reopened valve should have flow, got {valve_flow}"
