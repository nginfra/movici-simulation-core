"""Integration tests for water network simulation model"""

import pytest

pytest.importorskip("wntr")  # Skip all tests if WNTR not installed

from pathlib import Path

import numpy as np

from movici_simulation_core.core.moment import Moment
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.water_network_simulation.model import Model


class TestWaterNetworkSimulation:
    @pytest.fixture
    def simple_inp_file(self, tmp_path):
        """Create a simple INP file for testing"""
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
        """Test model initialization in INP file mode"""
        config = {"mode": "inp_file", "inp_file": str(simple_inp_file)}

        model = Model(config)

        assert model.mode == "inp_file"
        assert model.network is None  # Not initialized until setup

    def test_model_name(self):
        """Test model is registered with correct name"""
        config = {"mode": "inp_file", "inp_file": "dummy.inp"}
        model = Model(config)

        # Model should be registered as "water_network_simulation"
        assert hasattr(model, "__model_name__")

    def test_model_requires_mode(self):
        """Test model requires mode parameter"""
        with pytest.raises(KeyError):
            model = Model({})  # No mode specified

    def test_inp_mode_requires_inp_file(self):
        """Test INP mode requires inp_file parameter"""
        config = {"mode": "inp_file"}
        model = Model(config)

        # Should raise error during setup when inp_file is missing
        state = TrackedState()
        schema = AttributeSchema()

        with pytest.raises(ValueError, match="inp_file required"):
            model.setup(state, schema, init_data_handler=None)

    def test_movici_network_mode_requires_dataset(self):
        """Test movici_network mode requires dataset parameter"""
        config = {"mode": "movici_network"}
        model = Model(config)

        state = TrackedState()
        schema = AttributeSchema()

        with pytest.raises(ValueError, match="dataset required"):
            model.setup(state, schema, init_data_handler=None)


class TestConfigSchema:
    """Test configuration validation"""

    def test_valid_inp_mode_config(self):
        """Test valid INP mode configuration"""
        config = {
            "mode": "inp_file",
            "inp_file": "network.inp",
            "hydraulic_timestep": 3600,
        }

        model = Model(config)
        assert model.config["mode"] == "inp_file"
        assert model.config["hydraulic_timestep"] == 3600

    def test_valid_movici_network_mode_config(self):
        """Test valid movici_network mode configuration"""
        config = {
            "mode": "movici_network",
            "dataset": "water_network",
            "demand_patterns": ["demand_tape"],
            "hydraulic_timestep": 1800,
        }

        model = Model(config)
        assert model.config["mode"] == "movici_network"
        assert model.config["dataset"] == "water_network"

    def test_control_rules_config(self):
        """Test control rules in configuration"""
        config = {
            "mode": "movici_network",
            "dataset": "water_network",
            "control_rules": [
                {
                    "type": "time",
                    "target": "PU1",
                    "value": 1,
                    "time": 3600,
                },
                {
                    "type": "conditional",
                    "target": "PU1",
                    "value": 0,
                    "source": "T1",
                    "source_attribute": "level",
                    "operator": ">",
                    "threshold": 20.0,
                },
            ],
        }

        model = Model(config)
        assert len(model.config["control_rules"]) == 2
        assert model.config["control_rules"][0]["type"] == "time"
        assert model.config["control_rules"][1]["type"] == "conditional"
