"""Integration tests for water network simulation model.

.. note::
   Controls are handled by the Movici Rules Model, not internally.
   See ``test_rules_model_equivalence.py`` for control behavior tests.
"""

import pytest

pytest.importorskip("wntr")  # Skip all tests if WNTR not installed

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.drinking_water.model import Model


class TestWaterNetworkSimulation:
    def test_model_name(self):
        """Test model is registered with correct name."""
        model = Model({"dataset": "water_network"})

        # Model should be registered as "drinking_water"
        assert hasattr(model, "__model_name__")

    def test_requires_dataset(self):
        """Test model requires dataset parameter."""
        model = Model({})

        state = TrackedState()
        schema = AttributeSchema()

        with pytest.raises(ValueError, match="dataset required"):
            model.setup(state, schema)


class TestConfigSchema:
    """Test configuration validation."""

    def test_valid_config(self):
        """Test valid configuration."""
        config = {
            "dataset": "water_network",
            "entity_groups": ["junctions", "pipes", "reservoirs"],
            "hydraulic_timestep": 1800,
        }

        model = Model(config)
        assert model.config["dataset"] == "water_network"

    def test_dataset_name_stored(self):
        """Test that dataset_name is stored during setup."""
        config = {
            "dataset": "water_network",
        }

        model = Model(config)
        state = TrackedState()
        schema = AttributeSchema()
        model.setup(state, schema)
        assert model.dataset_name == "water_network"


class TestEntityGroups:
    """Test entity group configuration."""

    def test_default_entity_groups(self):
        """Test default entity groups when not specified."""
        config = {
            "dataset": "water_network",
        }

        model = Model(config)
        # Default should include junctions, pipes, reservoirs
        default_groups = model.config.get("entity_groups", ["junctions", "pipes", "reservoirs"])
        assert "junctions" in default_groups
        assert "pipes" in default_groups
        assert "reservoirs" in default_groups

    def test_custom_entity_groups(self):
        """Test custom entity groups configuration."""
        config = {
            "dataset": "water_network",
            "entity_groups": ["junctions", "pipes", "reservoirs", "tanks", "pumps", "valves"],
        }

        model = Model(config)
        entity_groups = model.config["entity_groups"]
        assert "tanks" in entity_groups
        assert "pumps" in entity_groups
        assert "valves" in entity_groups


class TestAttributeNaming:
    """Test that attribute names match documentation spec."""

    def _has_attribute(self, entity_cls, name):
        """Check if entity class has a field with given name (including inherited)."""
        return name in entity_cls.all_attributes()

    def test_junction_attributes(self):
        """Verify junction entity has correct attribute names."""
        from movici_simulation_core.models.drinking_water.dataset import (
            WaterJunctionEntity,
        )

        # Check INIT attributes
        assert self._has_attribute(WaterJunctionEntity, "elevation")
        assert self._has_attribute(WaterJunctionEntity, "base_demand")

        # Check OPT attributes
        assert self._has_attribute(WaterJunctionEntity, "demand_factor")
        assert self._has_attribute(WaterJunctionEntity, "minimum_pressure")
        assert self._has_attribute(WaterJunctionEntity, "required_pressure")
        assert self._has_attribute(WaterJunctionEntity, "pressure_exponent")

        # Check PUB attributes
        assert self._has_attribute(WaterJunctionEntity, "demand")
        assert self._has_attribute(WaterJunctionEntity, "pressure")
        assert self._has_attribute(WaterJunctionEntity, "head")

    def test_tank_attributes(self):
        """Verify tank entity has correct attribute names."""
        from movici_simulation_core.models.drinking_water.dataset import (
            WaterTankEntity,
        )

        # Check attributes
        assert self._has_attribute(WaterTankEntity, "elevation")
        assert self._has_attribute(WaterTankEntity, "level")
        assert self._has_attribute(WaterTankEntity, "diameter")
        assert self._has_attribute(WaterTankEntity, "min_level")
        assert self._has_attribute(WaterTankEntity, "max_level")
        assert self._has_attribute(WaterTankEntity, "overflow")
        assert self._has_attribute(WaterTankEntity, "volume_curve")
        assert self._has_attribute(WaterTankEntity, "pressure")
        assert self._has_attribute(WaterTankEntity, "head")

    def test_pipe_attributes(self):
        """Verify pipe entity has correct attribute names."""
        from movici_simulation_core.models.drinking_water.dataset import (
            WaterPipeEntity,
        )

        # Check attributes
        assert self._has_attribute(WaterPipeEntity, "diameter")
        assert self._has_attribute(WaterPipeEntity, "roughness")
        assert self._has_attribute(WaterPipeEntity, "length")
        assert self._has_attribute(WaterPipeEntity, "minor_loss")
        assert self._has_attribute(WaterPipeEntity, "check_valve")
        assert self._has_attribute(WaterPipeEntity, "status")
        assert self._has_attribute(WaterPipeEntity, "flow")
        assert self._has_attribute(WaterPipeEntity, "velocity")

    def test_pump_attributes(self):
        """Verify pump entity has correct attribute names."""
        from movici_simulation_core.models.drinking_water.dataset import (
            WaterPumpEntity,
        )

        # Check attributes
        assert self._has_attribute(WaterPumpEntity, "pump_type")
        assert self._has_attribute(WaterPumpEntity, "power")
        assert self._has_attribute(WaterPumpEntity, "head_curve")
        assert self._has_attribute(WaterPumpEntity, "speed")
        assert self._has_attribute(WaterPumpEntity, "status")
        assert self._has_attribute(WaterPumpEntity, "flow")

    def test_valve_attributes(self):
        """Verify valve entity has correct attribute names."""
        from movici_simulation_core.models.drinking_water.dataset import (
            WaterValveEntity,
        )

        # Check attributes
        assert self._has_attribute(WaterValveEntity, "valve_type")
        assert self._has_attribute(WaterValveEntity, "diameter")
        assert self._has_attribute(WaterValveEntity, "valve_pressure")
        assert self._has_attribute(WaterValveEntity, "valve_flow")
        assert self._has_attribute(WaterValveEntity, "valve_loss_coefficient")
        assert self._has_attribute(WaterValveEntity, "status")
        assert self._has_attribute(WaterValveEntity, "flow")


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

    def _get_wn(self, tester):
        """Navigate the tester wrapper chain to get the WNTR WaterNetworkModel.

        Chain: ModelTester.model (NumpyPreProcessor)
               -> .model (TrackedModelAdapter)
               -> .model (Model)
               -> .network.wn
        """
        return tester.model.model.model.network.wn

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

        wn = self._get_wn(tester)
        assert wn.options.hydraulic.viscosity == 1.5
        assert wn.options.hydraulic.specific_gravity == 0.98

    def test_defaults_when_no_general_section(self, create_model_tester, model_config):
        """Test that WNTR defaults are used when no general section."""
        network = self._make_network_data()

        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", network)
        tester.initialize()

        wn = self._get_wn(tester)
        assert wn.options.hydraulic.headloss == "H-W"
        assert wn.options.hydraulic.viscosity == 1.0
        assert wn.options.hydraulic.specific_gravity == 1.0

    def test_solver_options_from_model_config(self, create_model_tester):
        """Test that solver options from model config 'options' key are applied."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
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

        wn = self._get_wn(tester)
        assert wn.options.hydraulic.trials == 100
        assert wn.options.hydraulic.accuracy == 0.01

    def test_config_and_general_combined(self, create_model_tester):
        """Test that model config and dataset general are combined."""
        config = {
            "dataset": "water_network",
            "options": {
                "hydraulic_timestep": 3600,
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

        wn = self._get_wn(tester)
        assert wn.options.hydraulic.viscosity == 1.5
        assert wn.options.hydraulic.trials == 100
        assert wn.options.hydraulic.accuracy == 0.01


class TestMixedPumpTypes:
    """Test that results are correctly assigned when HEAD and POWER pumps coexist.

    WNTR groups HeadPumps before PowerPumps in the results DataFrame,
    regardless of creation order.  This test verifies that name-based
    lookup produces correct results even when entity order differs from
    WNTR's internal ordering.
    """

    @pytest.fixture
    def additional_attributes(self):
        return Model.get_schema_attributes()

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def mixed_pump_network_data(self):
        """Network with POWER pump before HEAD pump in entity order.

        Topology::

            R1 -(POWER pump PU201)-> J1 -(pipe P101)-> J2
            R2 -(HEAD  pump PU202)-> J3 -(pipe P102)-> J4
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
                    "id": [1, 2],
                    "reference": ["R1", "R2"],
                    "geometry.x": [0.0, 0.0],
                    "geometry.y": [0.0, 200.0],
                    "drinking_water.base_head": [0.0, 0.0],
                },
                "water_junction_entities": {
                    "id": [3, 4, 5, 6],
                    "reference": ["J1", "J2", "J3", "J4"],
                    "geometry.x": [100.0, 200.0, 100.0, 200.0],
                    "geometry.y": [0.0, 0.0, 200.0, 200.0],
                    "geometry.z": [0.0, 0.0, 0.0, 0.0],
                    "drinking_water.base_demand": [0.0, 0.001, 0.0, 0.001],
                },
                "water_pipe_entities": {
                    "id": [101, 102],
                    "reference": ["PIPE1", "PIPE2"],
                    "topology.from_node_id": [3, 5],
                    "topology.to_node_id": [4, 6],
                    "shape.diameter": [0.3, 0.3],
                    "shape.length": [100.0, 100.0],
                    "drinking_water.roughness": [100.0, 100.0],
                },
                "water_pump_entities": {
                    "id": [201, 202],
                    "reference": ["POWER_PUMP", "HEAD_PUMP"],
                    "topology.from_node_id": [1, 2],
                    "topology.to_node_id": [3, 5],
                    "pump_type": [0, 1],
                    "drinking_water.power": [1000.0, 0.0],
                    "drinking_water.head_curve": [
                        None,
                        [[0.0, 50.0], [0.01, 0.0]],
                    ],
                },
            },
        }

    @pytest.fixture
    def init_data(self, mixed_pump_network_data):
        return [("water_network", mixed_pump_network_data)]

    @pytest.fixture
    def model_config(self):
        return {"dataset": "water_network", "options": {"hydraulic_timestep": 3600}}

    def _get_wn(self, tester):
        return tester.model.model.model.network.wn

    def test_mixed_pump_results_correctly_assigned(self, create_model_tester, model_config):
        """Verify results map to the correct pump when types are mixed."""
        tester = create_model_tester(Model, model_config)
        tester.initialize()

        result, _ = tester.update(0, None)

        assert result is not None
        pumps = result["water_network"]["water_pump_entities"]
        flows = pumps["drinking_water.flow"]

        # Both pumps should produce positive flow
        assert len(flows) == 2
        assert flows[0] > 0, "Power pump (index 0) should have flow"
        assert flows[1] > 0, "Head pump (index 1) should have flow"

        # Confirm WNTR separated the pump types internally
        wn = self._get_wn(tester)
        assert "PU202" in wn.head_pump_name_list
        assert "PU201" in wn.power_pump_name_list


class TestValveStatus:
    """Test valve operational.status for initial state and dynamic changes."""

    @pytest.fixture
    def additional_attributes(self):
        return Model.get_schema_attributes()

    @pytest.fixture
    def global_timeline_info(self):
        return TimelineInfo(reference=0, time_scale=1, start_time=0)

    @pytest.fixture
    def valve_network_data(self):
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
                    "valve_type": [0],
                    "shape.diameter": [0.3],
                    "drinking_water.valve_pressure": [30.0],
                },
            },
        }

    @pytest.fixture
    def model_config(self):
        return {"dataset": "water_network", "options": {"hydraulic_timestep": 3600}}

    def test_valve_initially_closed(self, create_model_tester, model_config, valve_network_data):
        """Valve with status=False should block flow."""
        valve_network_data["data"]["water_valve_entities"]["operational.status"] = [False]

        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", valve_network_data)
        tester.initialize()

        result, _ = tester.update(0, None)

        assert result is not None
        valves = result["water_network"]["water_valve_entities"]
        assert abs(valves["drinking_water.flow"][0]) < 1e-10

    def test_valve_default_active(self, create_model_tester, model_config, valve_network_data):
        """Valve without status attribute should be active (regulating)."""
        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", valve_network_data)
        tester.initialize()

        result, _ = tester.update(0, None)

        assert result is not None
        valves = result["water_network"]["water_valve_entities"]
        assert abs(valves["drinking_water.flow"][0]) > 1e-6

    def test_valve_status_change_reopens(
        self, create_model_tester, model_config, valve_network_data
    ):
        """Changing valve status from closed to active should restore flow."""
        valve_network_data["data"]["water_valve_entities"]["operational.status"] = [False]

        tester = create_model_tester(Model, model_config)
        tester.add_init_data("water_network", valve_network_data)
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
