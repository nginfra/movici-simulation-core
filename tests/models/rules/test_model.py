"""Tests for the Rules Model."""

import datetime
import logging

import pytest

from movici_simulation_core.attributes import GlobalAttributes
from movici_simulation_core.core.moment import TimelineInfo, set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.models.rules.model import Model, RuleValidationError
from movici_simulation_core.testing.model_tester import ModelTester


def get_schema():
    schema = AttributeSchema()
    schema.use(GlobalAttributes)
    return schema


def get_sensors_dataset():
    return {
        "name": "sensors",
        "data": {
            "sensor_entities": {
                "id": [1, 2],
                "sensor.level": [25.0, 15.0],
                "sensor.threshold": [20.0, 20.0],
            }
        },
    }


def get_actuators_dataset():
    return {
        "name": "actuators",
        "data": {
            "actuator_entities": {
                "id": [10, 20],
            }
        },
    }


def get_model_config():
    return {
        "name": "rules_example",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": [
            {
                "if": "<simtime> >= 3600",
                "from_id": 1,
                "to_id": 10,
                "output": "control.active",
                "value": True,
                "else_value": False,
            },
            {
                "if": "sensor.level >= 23",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.5,
                "else_value": 0.0,
            },
            {
                "if": "sensor.level > sensor.threshold",
                "from_id": 2,
                "to_id": 20,
                "output": "control.valve_open",
                "value": True,
                "else_value": False,
            },
            {
                "if": "20 > sensor.level",
                "from_id": 2,
                "to_id": 20,
                "output": "control.alarm",
                "value": True,
                "else_value": False,
            },
        ],
    }


def test_run_scenario():
    schema = get_schema()
    model_config = get_model_config()

    expected_t0 = {
        "actuators": {
            "actuator_entities": {
                "id": [10, 20],
                "control.active": [False, None],
                "control.pump_speed": [1.5, None],
                "control.valve_open": [None, False],
                "control.alarm": [None, True],
            }
        }
    }

    expected_t3600 = {
        "actuators": {
            "actuator_entities": {
                "id": [10],
                "control.active": [True],
            }
        }
    }

    scenario = {
        "config": {
            "simulation_info": {
                "reference_time": 0,
                "start_time": 0,
                "time_scale": 1,
                "duration": 7200,
            },
            "models": [model_config],
        },
        "init_data": [
            {"name": "sensors", "data": get_sensors_dataset()},
            {"name": "actuators", "data": get_actuators_dataset()},
        ],
        "updates": [
            {"time": 0, "data": None},
            {"time": 3600, "data": None},
        ],
        "expected_results": [
            {"time": 0, "data": expected_t0, "next_time": 3600},
            {"time": 3600, "data": expected_t3600, "next_time": None},
        ],
    }

    ModelTester.run_scenario(Model, "rules_example", scenario, global_schema=schema)


def get_sensors_dataset_with_refs():
    return {
        "name": "sensors",
        "data": {
            "sensor_entities": {
                "id": [1, 2],
                "reference": ["sensor_A", "sensor_B"],
                "sensor.level": [25.0, 15.0],
            }
        },
    }


def get_actuators_dataset_with_refs():
    return {
        "name": "actuators",
        "data": {
            "actuator_entities": {
                "id": [10, 20],
                "reference": ["pump_1", "valve_1"],
            }
        },
    }


def test_entity_lookup_by_reference():
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    config = {
        "name": "rules_ref",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": [
            {
                "if": "sensor.level >= 20",
                "from_reference": "sensor_A",
                "to_reference": "pump_1",
                "output": "control.pump_speed",
                "value": 1.5,
                "else_value": 0.0,
            },
            {
                "if": "sensor.level >= 20",
                "from_reference": "sensor_B",
                "to_reference": "valve_1",
                "output": "control.valve_open",
                "value": True,
                "else_value": False,
            },
        ],
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("sensors", get_sensors_dataset_with_refs())
            tester.add_init_data("actuators", get_actuators_dataset_with_refs())
            tester.initialize()

            tester.new_time(0)
            result, _ = tester.update(0, None)

    actuators = result["actuators"]["actuator_entities"]
    # sensor_A level=25 >= 20 -> pump_1 (idx 0): pump_speed=1.5
    assert actuators["control.pump_speed"] == [1.5, None]
    # sensor_B level=15 < 20 -> valve_1 (idx 1): valve_open=False
    assert actuators["control.valve_open"] == [None, False]


def test_clocktime_condition():
    schema = get_schema()
    # reference = midnight UTC on 2026-01-01, time_scale=1 so timestamp == seconds
    midnight = datetime.datetime(2026, 1, 1, tzinfo=datetime.timezone.utc).timestamp()
    timeline_info = TimelineInfo(reference=midnight, time_scale=1, start_time=0, duration=86400)

    config = {
        "name": "rules_clock",
        "type": "rules",
        "rules": [
            {
                "if": "<clocktime> >= 8:00",
                "to_dataset": "actuators",
                "to_id": 10,
                "output": "control.active",
                "value": True,
                "else_value": False,
            },
        ],
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("actuators", get_actuators_dataset())
            tester.initialize()

            # t=0 -> 00:00 UTC, clocktime < 8:00
            tester.new_time(0)
            result_0, next_0 = tester.update(0, None)

            # t=28800 -> 08:00 UTC, clocktime >= 8:00
            tester.new_time(28800)
            result_8h, _ = tester.update(28800, None)

    act_0 = result_0["actuators"]["actuator_entities"]
    assert act_0["control.active"] == [False]
    assert next_0 == 28800  # next trigger at 8:00

    act_8h = result_8h["actuators"]["actuator_entities"]
    assert act_8h["control.active"] == [True]


@pytest.mark.parametrize(
    "rule, actuators_dataset, match",
    [
        pytest.param(
            {"if": "<simtime> >= 10", "to_id": 10, "output": "control.active", "value": True},
            get_actuators_dataset(),
            "to_dataset",
            id="missing_to_dataset",
        ),
        pytest.param(
            {
                "if": "sensor.level >= 20",
                "to_dataset": "actuators",
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.5,
            },
            get_actuators_dataset(),
            "from_dataset",
            id="missing_from_dataset",
        ),
        pytest.param(
            {
                "if": "<simtime> >= 10",
                "to_dataset": "actuators",
                "to_reference": "nonexistent",
                "output": "control.active",
                "value": True,
            },
            get_actuators_dataset_with_refs(),
            "nonexistent",
            id="unknown_reference",
        ),
    ],
)
def test_invalid_rule_raises(rule, actuators_dataset, match):
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=100)

    config = {"name": "rules_bad", "type": "rules", "rules": [rule]}

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("actuators", actuators_dataset)
            with pytest.raises((RuleValidationError, ValueError), match=match):
                tester.initialize()


@pytest.mark.parametrize(
    "rules, dataset_rules, update, expected_pump_speed",
    [
        pytest.param(
            [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 1.5,
                    "else_value": 0.0,
                }
            ],
            None,
            {"sensors": {"sensor_entities": {"id": [1, 2], "sensor.level": [25.0, 15.0]}}},
            [1.5],
            id="condition_true",
        ),
        pytest.param(
            [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 1.5,
                    "else_value": 0.0,
                }
            ],
            None,
            {"sensors": {"sensor_entities": {"id": [1, 2], "sensor.level": [10.0, 15.0]}}},
            [0.0],
            id="else_value",
        ),
        pytest.param(
            [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 1.0,
                },
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 2.0,
                },
            ],
            None,
            {"sensors": {"sensor_entities": {"id": [1, 2], "sensor.level": [25.0, 15.0]}}},
            [2.0],
            id="later_rule_overrides",
        ),
        pytest.param(
            [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 5.0,
                }
            ],
            [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 1.0,
                }
            ],
            {"sensors": {"sensor_entities": {"id": [1, 2], "sensor.level": [25.0, 15.0]}}},
            [5.0],
            id="config_overrides_dataset",
        ),
    ],
)
def test_rule_triggered_by_update(rules, dataset_rules, update, expected_pump_speed):
    """Rule evaluates against updated attribute values from an incoming update."""
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    config = {
        "name": "rules_update_test",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": rules,
    }

    dataset_rules = dataset_rules or []
    config["rules_dataset"] = "my_rules"

    model = Model(config)
    with set_timeline_info(timeline_info), ModelTester(model, schema=schema) as tester:
        tester.add_init_data("sensors", get_sensors_dataset())
        tester.add_init_data("actuators", get_actuators_dataset())
        tester.add_init_data(
            "my_rules",
            {
                "name": "my_rules",
                "type": "rules",
                "data": {
                    "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
                    "rules": dataset_rules,
                },
            },
        )
        tester.initialize()

        tester.new_time(0)
        result, _ = tester.update(0, update)

    assert result["actuators"]["actuator_entities"]["control.pump_speed"] == expected_pump_speed


def test_overlapping_rules_emit_warning(caplog):
    """When multiple rules target the same entity+attribute, a warning is logged."""
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    config = {
        "name": "rules_overlap_warn",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": [
            {
                "if": "sensor.level >= 20",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.0,
            },
            {
                "if": "sensor.level < 20",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 0.0,
            },
        ],
    }

    model = Model(config)
    with (
        set_timeline_info(timeline_info),
        ModelTester(model, schema=schema) as tester,
        caplog.at_level(logging.WARNING),
    ):
        tester.add_init_data("sensors", get_sensors_dataset())
        tester.add_init_data("actuators", get_actuators_dataset())
        tester.initialize()

    assert "Multiple rules target" in caplog.text
    assert "control.pump_speed" in caplog.text
    assert "override" in caplog.text


def test_non_overlapping_rules_no_warning(caplog):
    """Rules targeting different entities or attributes produce no warning."""
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    config = {
        "name": "rules_no_warn",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": [
            {
                "if": "sensor.level >= 20",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.0,
            },
            {
                "if": "sensor.level >= 20",
                "from_id": 1,
                "to_id": 20,
                "output": "control.pump_speed",
                "value": 2.0,
            },
        ],
    }

    model = Model(config)
    with (
        set_timeline_info(timeline_info),
        ModelTester(model, schema=schema) as tester,
        caplog.at_level(logging.WARNING),
    ):
        tester.add_init_data("sensors", get_sensors_dataset())
        tester.add_init_data("actuators", get_actuators_dataset())
        tester.initialize()

    assert not caplog.text
