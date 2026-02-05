"""Tests for NetworkWrapper WNTR options configuration."""

import logging

import pytest

pytest.importorskip("wntr")

from movici_simulation_core.models.drinking_water.network_wrapper import NetworkWrapper


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


