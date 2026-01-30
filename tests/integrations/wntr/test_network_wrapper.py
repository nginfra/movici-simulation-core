"""Tests for NetworkWrapper WNTR options configuration."""

import logging

import numpy as np
import pytest

pytest.importorskip("wntr")

from movici_simulation_core.integrations.wntr.collections import JunctionCollection
from movici_simulation_core.integrations.wntr.network_wrapper import NetworkWrapper


class TestConfigureOptions:
    """Test configure_options applies WNTR options correctly."""

    @pytest.fixture
    def wrapper(self):
        return NetworkWrapper()

    def test_set_headloss_formula(self, wrapper):
        wrapper.configure_options({"hydraulic": {"headloss": "D-W"}})
        assert wrapper.wn.options.hydraulic.headloss == "D-W"

    def test_set_demand_model(self, wrapper):
        wrapper.configure_options({"hydraulic": {"demand_model": "PDA"}})
        assert wrapper.wn.options.hydraulic.demand_model == "PDA"

    def test_set_viscosity(self, wrapper):
        wrapper.configure_options({"hydraulic": {"viscosity": 1.5}})
        assert wrapper.wn.options.hydraulic.viscosity == 1.5

    def test_set_specific_gravity(self, wrapper):
        wrapper.configure_options({"hydraulic": {"specific_gravity": 0.98}})
        assert wrapper.wn.options.hydraulic.specific_gravity == 0.98

    def test_set_multiple_hydraulic_options(self, wrapper):
        wrapper.configure_options(
            {
                "hydraulic": {
                    "headloss": "C-M",
                    "trials": 100,
                    "accuracy": 0.01,
                    "demand_multiplier": 2.0,
                }
            }
        )
        assert wrapper.wn.options.hydraulic.headloss == "C-M"
        assert wrapper.wn.options.hydraulic.trials == 100
        assert wrapper.wn.options.hydraulic.accuracy == 0.01
        assert wrapper.wn.options.hydraulic.demand_multiplier == 2.0

    def test_set_time_options(self, wrapper):
        wrapper.configure_options({"time": {"duration": 7200}})
        assert wrapper.wn.options.time.duration == 7200

    def test_set_multiple_sections(self, wrapper):
        wrapper.configure_options(
            {
                "hydraulic": {"headloss": "D-W"},
                "time": {"duration": 7200},
            }
        )
        assert wrapper.wn.options.hydraulic.headloss == "D-W"
        assert wrapper.wn.options.time.duration == 7200

    def test_none_values_are_skipped(self, wrapper):
        original = wrapper.wn.options.hydraulic.headloss
        wrapper.configure_options({"hydraulic": {"headloss": None}})
        assert wrapper.wn.options.hydraulic.headloss == original

    def test_empty_options_dict(self, wrapper):
        original_headloss = wrapper.wn.options.hydraulic.headloss
        wrapper.configure_options({})
        assert wrapper.wn.options.hydraulic.headloss == original_headloss

    def test_non_dict_section_values_are_skipped(self, wrapper):
        original_headloss = wrapper.wn.options.hydraulic.headloss
        wrapper.configure_options({"hydraulic": "not_a_dict"})
        assert wrapper.wn.options.hydraulic.headloss == original_headloss

    def test_unknown_section_warns(self, wrapper, caplog):
        with caplog.at_level(logging.WARNING):
            wrapper.configure_options({"nonexistent_section": {"key": "value"}})
        assert "Unknown WNTR options section 'nonexistent_section'" in caplog.text

    def test_unknown_option_key_warns(self, wrapper, caplog):
        with caplog.at_level(logging.WARNING):
            wrapper.configure_options({"hydraulic": {"nonexistent_key": 42}})
        assert "Unknown option 'nonexistent_key' in section 'hydraulic'" in caplog.text

    def test_defaults_unchanged_when_no_options(self, wrapper):
        assert wrapper.wn.options.hydraulic.headloss == "H-W"
        assert wrapper.wn.options.hydraulic.demand_model == "DDA"
        assert wrapper.wn.options.hydraulic.viscosity == 1.0
        assert wrapper.wn.options.hydraulic.specific_gravity == 1.0


class TestAddJunctionsWithPDD:
    """Test per-junction PDD attributes in add_junctions."""

    @pytest.fixture
    def wrapper(self):
        return NetworkWrapper()

    def _make_junctions(self, **kwargs):
        defaults = dict(
            node_names=["J1", "J2"],
            elevations=np.array([10.0, 20.0]),
            base_demands=np.array([0.001, 0.002]),
        )
        defaults.update(kwargs)
        return JunctionCollection(**defaults)

    def test_no_pdd_attributes(self, wrapper):
        """Junctions without PDD arrays leave WNTR defaults (None)."""
        wrapper.add_junctions(self._make_junctions())
        j1 = wrapper.wn.get_node("J1")
        assert j1.minimum_pressure is None
        assert j1.required_pressure is None
        assert j1.pressure_exponent is None

    def test_minimum_pressure_set(self, wrapper):
        wrapper.add_junctions(self._make_junctions(minimum_pressures=np.array([5.0, 10.0])))
        assert wrapper.wn.get_node("J1").minimum_pressure == 5.0
        assert wrapper.wn.get_node("J2").minimum_pressure == 10.0

    def test_required_pressure_set(self, wrapper):
        wrapper.add_junctions(self._make_junctions(required_pressures=np.array([20.0, 30.0])))
        assert wrapper.wn.get_node("J1").required_pressure == 20.0
        assert wrapper.wn.get_node("J2").required_pressure == 30.0

    def test_pressure_exponent_set(self, wrapper):
        wrapper.add_junctions(self._make_junctions(pressure_exponents=np.array([0.5, 1.0])))
        assert wrapper.wn.get_node("J1").pressure_exponent == 0.5
        assert wrapper.wn.get_node("J2").pressure_exponent == 1.0

    def test_nan_values_leave_none(self, wrapper):
        """NaN sentinel values leave WNTR junction attribute as None."""
        wrapper.add_junctions(
            self._make_junctions(
                minimum_pressures=np.array([5.0, np.nan]),
                required_pressures=np.array([np.nan, 30.0]),
            )
        )
        j1 = wrapper.wn.get_node("J1")
        j2 = wrapper.wn.get_node("J2")
        assert j1.minimum_pressure == 5.0
        assert j1.required_pressure is None
        assert j2.minimum_pressure is None
        assert j2.required_pressure == 30.0

    def test_all_nan_leaves_all_none(self, wrapper):
        """Array of all NaN leaves all junction attributes as None."""
        wrapper.add_junctions(self._make_junctions(minimum_pressures=np.array([np.nan, np.nan])))
        assert wrapper.wn.get_node("J1").minimum_pressure is None
        assert wrapper.wn.get_node("J2").minimum_pressure is None
