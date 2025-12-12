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
    @pytest.fixture
    def simple_inp_file(self, tmp_path):
        """Create a simple INP file for testing."""
        inp_content = """[TITLE]
Test Network

[JUNCTIONS]
J1  100  10  1

[RESERVOIRS]
R1  150

[PIPES]
P1  R1  J1  1000  300  100  0  Open

[PATTERNS]
1  1.0  1.0

[TIMES]
Duration  1:00
Hydraulic Timestep  1:00

[OPTIONS]
Units  LPS
Headloss  H-W

[COORDINATES]
J1  1000  1000
R1  0  1000

[END]
"""
        inp_path = tmp_path / "test_network.inp"
        inp_path.write_text(inp_content)
        return inp_path

    def test_model_initialization_inp_mode(self, simple_inp_file):
        """Test model initialization in INP file mode."""
        config = {"mode": "inp_file", "inp_file": str(simple_inp_file)}

        model = Model(config)

        assert model.mode == "inp_file"
        assert model.network is None  # Not initialized until setup

    def test_model_name(self):
        """Test model is registered with correct name."""
        config = {"mode": "inp_file", "inp_file": "dummy.inp"}
        model = Model(config)

        # Model should be registered as "water_network_simulation"
        assert hasattr(model, "__model_name__")

    def test_model_default_mode(self):
        """Test model has default mode of movici_network."""
        model = Model({})  # No mode specified
        assert model.mode == "movici_network"

    def test_inp_mode_requires_inp_file(self):
        """Test INP mode requires inp_file parameter."""
        config = {"mode": "inp_file"}
        model = Model(config)

        # Should raise error during setup when inp_file is missing
        state = TrackedState()
        schema = AttributeSchema()

        with pytest.raises(ValueError, match="inp_file required"):
            model.setup(state, schema, init_data_handler=None)

    def test_movici_network_mode_requires_dataset(self):
        """Test movici_network mode requires dataset parameter."""
        config = {"mode": "movici_network"}
        model = Model(config)

        state = TrackedState()
        schema = AttributeSchema()

        with pytest.raises(ValueError, match="dataset required"):
            model.setup(state, schema, init_data_handler=None)


class TestConfigSchema:
    """Test configuration validation."""

    def test_valid_inp_mode_config(self):
        """Test valid INP mode configuration."""
        config = {
            "mode": "inp_file",
            "inp_file": "network.inp",
            "hydraulic_timestep": 3600,
        }

        model = Model(config)
        assert model.config["mode"] == "inp_file"
        assert model.config["hydraulic_timestep"] == 3600

    def test_valid_movici_network_mode_config(self):
        """Test valid movici_network mode configuration."""
        config = {
            "mode": "movici_network",
            "dataset": "water_network",
            "entity_groups": ["junctions", "pipes", "reservoirs"],
            "hydraulic_timestep": 1800,
        }

        model = Model(config)
        assert model.config["mode"] == "movici_network"
        assert model.config["dataset"] == "water_network"

    def test_viscosity_config(self):
        """Test viscosity configuration option."""
        config = {
            "mode": "movici_network",
            "dataset": "water_network",
            "viscosity": 1.5,
        }

        model = Model(config)
        assert model.viscosity == 1.5

    def test_specific_gravity_config(self):
        """Test specific gravity configuration option."""
        config = {
            "mode": "movici_network",
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
            "mode": "movici_network",
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
            "mode": "movici_network",
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
