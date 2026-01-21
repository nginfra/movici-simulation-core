"""Integration tests for water network simulation model.

.. note::
   Controls are handled by the Movici Rules Model, not internally.
   See ``test_rules_model_equivalence.py`` for control behavior tests.
"""

import pytest

pytest.importorskip("wntr")  # Skip all tests if WNTR not installed


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

    def test_viscosity_config(self):
        """Test viscosity configuration option."""
        config = {
            "dataset": "water_network",
            "viscosity": 1.5,
        }

        model = Model(config)
        assert model.viscosity == 1.5

    def test_specific_gravity_config(self):
        """Test specific gravity configuration option."""
        config = {
            "dataset": "water_network",
            "specific_gravity": 0.98,
        }

        model = Model(config)
        assert model.specific_gravity == 0.98

    def test_default_viscosity_and_specific_gravity(self):
        """Test default viscosity and specific gravity values."""
        model = Model({})

        assert model.viscosity == 1.0
        assert model.specific_gravity == 1.0


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
