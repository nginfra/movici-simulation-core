"""Tests for NetworkWrapper WNTR options configuration."""

import logging

import pytest
import wntr

from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.state import TrackedState
from movici_simulation_core.models.drinking_water.model import Model as DrinkingWaterModel
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


@pytest.fixture
def schema(global_schema):
    global_schema.register_attributes(DrinkingWaterModel.get_schema_attributes())
    return global_schema


@pytest.fixture
def state(schema):
    return TrackedState(schema=schema)


@pytest.fixture
def initialize_wrapper(schema, state):
    converter = EntityInitDataFormat(schema)

    def _initialize(init_data: dict, dataset_name="drinking_water") -> NetworkWrapper:
        dataset = DrinkingWaterModel._register_dataset(state, dataset_name=dataset_name)
        state.receive_update(converter.load_json(init_data), is_initial=True)
        wrapper = NetworkWrapper()
        wrapper.initialize(dataset)
        return wrapper

    return _initialize


class TestProcessingBase:
    @pytest.fixture
    def wrapper(self, network_data, initialize_wrapper) -> NetworkWrapper:
        return initialize_wrapper(network_data)

    @staticmethod
    def apply_update(state: TrackedState, json_update: dict, is_initial=False):
        """apply an update to the state. The update is expected to be json data and will be
        converted to a numpy array data update"""
        converter = EntityInitDataFormat(state.schema)
        state.receive_update(converter.load_json(json_update), is_initial=is_initial)


class TestJunctionProcessing(TestProcessingBase):
    @pytest.fixture
    def network_data(self):
        return {
            "drinking_water": {
                "water_junction_entities": {
                    "id": [1, 2],
                    "geometry.x": [0] * 2,
                    "geometry.y": [0] * 2,
                    "geometry.z": [0] * 2,
                    "drinking_water.base_demand": [1] * 2,
                    "drinking_water.minimum_pressure": [None, 1],
                    "drinking_water.required_pressure": [None, 2],
                    "drinking_water.pressure_exponent": [None, 3],
                }
            }
        }

    def test_create_junction_with_pressure_attributes(self, wrapper):
        j1: wntr.network.Junction = wrapper.wn.get_node("J1")
        assert j1.minimum_pressure is None
        assert j1.required_pressure is None
        assert j1.pressure_exponent is None

        j2: wntr.network.Junction = wrapper.wn.get_node("J2")
        assert j2.minimum_pressure == 1
        assert j2.required_pressure == 2
        assert j2.pressure_exponent == 3

    def test_update_junction(self, wrapper: NetworkWrapper, state):
        j1: wntr.network.Junction = wrapper.wn.get_node("J1")
        j2: wntr.network.Junction = wrapper.wn.get_node("J2")
        assert j1.base_demand == 1
        assert j2.base_demand == 1

        self.apply_update(
            state,
            {
                "drinking_water": {
                    "water_junction_entities": {
                        "id": [1],
                        "drinking_water.base_demand": [2],
                        "drinking_water.demand_factor": [1.5],
                    }
                }
            },
        )
        wrapper.process_changes()

        assert j1.base_demand == 3
        assert j2.base_demand == 1


class TestTankProcessing(TestProcessingBase):
    @pytest.fixture
    def network_data(self):
        return {
            "drinking_water": {
                "water_tank_entities": {
                    "id": [1, 2],
                    "geometry.x": [0] * 2,
                    "geometry.y": [0] * 2,
                    "geometry.z": [0] * 2,
                    "shape.diameter": [2, None],
                    "shape.volume_curve": [None, [(0, 1), (5, 2)]],
                    "drinking_water.min_level": [1, None],
                    "drinking_water.max_level": [5] * 2,
                }
            }
        }

    def test_create_tank_with_diameter_or_volume_curve(self, wrapper):
        t1: wntr.network.Tank = wrapper.wn.get_node("T1")
        assert t1.diameter == 2
        assert t1.min_level == 1
        assert t1.max_level == 5
        assert t1.vol_curve_name is None

        t2: wntr.network.Tank = wrapper.wn.get_node("T2")
        assert t2.vol_curve.points == [(0, 1), (5, 2)]
        assert t2.min_level == 0  # default min_level
        assert t2.max_level == 5


class TestReservoirProcessing(TestProcessingBase):
    @pytest.fixture
    def network_data(self):
        return {
            "drinking_water": {
                "water_reservoir_entities": {
                    "id": [1, 2],
                    "geometry.x": [0] * 2,
                    "geometry.y": [0] * 2,
                    "drinking_water.base_head": [1, 10],
                }
            }
        }

    def test_update_reservoir(self, wrapper, state):
        r1: wntr.network.Reservoir = wrapper.wn.get_node("R1")
        r2: wntr.network.Reservoir = wrapper.wn.get_node("R2")
        assert r1.base_head == 1
        assert r2.base_head == 10

        self.apply_update(
            state,
            {
                "drinking_water": {
                    "water_reservoir_entities": {
                        "id": [1, 2],
                        "drinking_water.base_head": [2, None],
                        "drinking_water.head_factor": [None, 1.5],
                    }
                }
            },
        )
        wrapper.process_changes()

        assert r1.base_head == 2
        assert r2.base_head == 15


class TestPipeProcessing(TestProcessingBase):
    @pytest.fixture
    def network_data(self):
        return {
            "drinking_water": {
                "water_junction_entities": {
                    "id": [10, 20, 30],
                    "drinking_water.base_demand": [2] * 3,
                    "geometry.z": [0] * 3,
                },
                "water_pipe_entities": {
                    "id": [1, 2],
                    "topology.from_node_id": [10, 20],
                    "topology.to_node_id": [20, 30],
                    "shape.diameter": [1, 1],
                    "shape.length": [10, 10],
                    "drinking_water.roughness": [100.0, 100.0],
                    "drinking_water.check_valve": [None, True],
                },
            }
        }

    def test_create_pipe_with_check_valve(self, wrapper):
        p1: wntr.network.Pipe = wrapper.wn.get_link("P1")
        p2: wntr.network.Pipe = wrapper.wn.get_link("P2")

        assert not p1.check_valve
        assert p2.check_valve


class TestPumpProcessing(TestProcessingBase):
    OPEN = wntr.network.LinkStatus.Open
    CLOSED = wntr.network.LinkStatus.Closed

    @pytest.fixture
    def network_data(self):
        return {
            "general": {
                "enum": {"pump_type": ["power", "head"]},
            },
            "drinking_water": {
                "water_junction_entities": {
                    "id": [10, 20, 30],
                    "drinking_water.base_demand": [2] * 3,
                    "geometry.z": [0] * 3,
                },
                "water_pump_entities": {
                    "id": [1, 2],
                    "topology.from_node_id": [10, 20],
                    "topology.to_node_id": [20, 30],
                    "drinking_water.pump_type": [0, 1],
                    "drinking_water.power": [100, None],
                    "drinking_water.head_curve": [None, [(0, 25), (1, 13)]],
                    "operational.status": [None, False],
                },
            },
        }

    def test_create_power_and_head_pumps(self, wrapper):
        p1: wntr.network.elements.PowerPump = wrapper.wn.get_link("PU1")
        p2: wntr.network.elements.HeadPump = wrapper.wn.get_link("PU2")

        assert p1.pump_type == "POWER"
        assert p1.power == 100

        assert p2.pump_type == "HEAD"
        assert p2.get_pump_curve().points == [(0, 25), (1, 13)]

    @pytest.mark.xfail(reason="TODO: implement")
    def test_update_pump_power(self, wrapper, state):
        p1: wntr.network.elements.PowerPump = wrapper.wn.get_link("PU1")
        self.apply_update(
            state,
            {
                "drinking_water": {
                    "water_pump_entities": {
                        "id": [1],
                        "drinking_water.power": [200],
                    }
                }
            },
        )
        wrapper.process_changes()
        assert p1.power == 200

    def test_update_pump_status(self, wrapper, state):
        p1: wntr.network.elements.PowerPump = wrapper.wn.get_link("PU1")
        p2: wntr.network.elements.HeadPump = wrapper.wn.get_link("PU2")

        assert p1.status == self.OPEN
        assert p2.status == self.CLOSED

        self.apply_update(
            state,
            {
                "drinking_water": {
                    "water_pump_entities": {
                        "id": [1, 2],
                        # None in an update means: do not change
                        "operational.status": [False, None],
                    }
                }
            },
        )
        wrapper.process_changes()
        assert p1.status == self.CLOSED
        assert p2.status == self.CLOSED
