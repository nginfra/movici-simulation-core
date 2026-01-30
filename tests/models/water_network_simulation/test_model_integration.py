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
from movici_simulation_core.models.water_network_simulation.model import Model


class TestWaterNetworkSimulation:
    def test_model_name(self):
        """Test model is registered with correct name."""
        model = Model({"dataset": "water_network"})

        # Model should be registered as "water_network_simulation"
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
        """Check if entity class has a field with given name."""
        return name in entity_cls.attributes

    def test_junction_attributes(self):
        """Verify junction entity has correct attribute names."""
        from movici_simulation_core.models.water_network_simulation.dataset import (
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
        from movici_simulation_core.models.water_network_simulation.dataset import (
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
        from movici_simulation_core.models.water_network_simulation.dataset import (
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
        assert self._has_attribute(WaterPipeEntity, "headloss")

    def test_pump_attributes(self):
        """Verify pump entity has correct attribute names."""
        from movici_simulation_core.models.water_network_simulation.dataset import (
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
        from movici_simulation_core.models.water_network_simulation.dataset import (
            WaterValveEntity,
        )

        # Check attributes
        assert self._has_attribute(WaterValveEntity, "valve_type")
        assert self._has_attribute(WaterValveEntity, "diameter")
        assert self._has_attribute(WaterValveEntity, "valve_pressure")
        assert self._has_attribute(WaterValveEntity, "valve_flow")
        assert self._has_attribute(WaterValveEntity, "valve_loss_coefficient")
        assert self._has_attribute(WaterValveEntity, "valve_curve")
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
            "entity_groups": ["junctions", "pipes", "reservoirs"],
            "hydraulic_timestep": 3600,
            "simulation_duration": 3600,
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
            "entity_groups": ["junctions", "pipes", "reservoirs"],
            "hydraulic_timestep": 3600,
            "simulation_duration": 3600,
            "options": {
                "hydraulic": {
                    "trials": 100,
                    "accuracy": 0.01,
                }
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
            "entity_groups": ["junctions", "pipes", "reservoirs"],
            "hydraulic_timestep": 3600,
            "simulation_duration": 3600,
            "options": {
                "hydraulic": {
                    "trials": 100,
                    "accuracy": 0.01,
                }
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
