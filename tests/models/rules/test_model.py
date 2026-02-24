"""Tests for the Rules Model."""

import datetime
import tempfile
from pathlib import Path

import pytest

from movici_simulation_core.attributes import GlobalAttributes
from movici_simulation_core.core.moment import TimelineInfo, set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.models.csv_player.csv_player import CSVPlayer
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


def test_standalone_rules():
    schema = get_schema()
    model_config = get_model_config()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    model = Model(model_config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("sensors", get_sensors_dataset())
            tester.add_init_data("actuators", get_actuators_dataset())
            tester.initialize()

            # t=0: simtime=0, sensor 1 level=25, sensor 2 level=15, threshold=20
            tester.new_time(0)
            result_t0, next_moment_t0 = tester.update(0, None)

            # t=3600: simtime >= 3600 so control.active flips to True
            tester.new_time(3600)
            result_t3600, next_moment_t3600 = tester.update(3600, None)

    actuators_t0 = result_t0["actuators"]["actuator_entities"]
    assert actuators_t0["control.active"] == [False, None]
    assert actuators_t0["control.pump_speed"] == [1.5, None]
    assert actuators_t0["control.valve_open"] == [None, False]
    assert actuators_t0["control.alarm"] == [None, True]

    assert next_moment_t0 == 3600

    actuators_t3600 = result_t3600["actuators"]["actuator_entities"]
    assert actuators_t3600["control.active"] == [True]

    assert next_moment_t3600 is None


def test_paired_with_csv_player():
    schema = get_schema()

    sensors_dataset = get_sensors_dataset()
    actuators_dataset = get_actuators_dataset()

    rules_config = {
        "name": "rules_paired",
        "type": "rules",
        "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
        "rules": [
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
        ],
    }

    csv_config = {
        "name": "csv_player_example",
        "type": "csv_player",
        "entity_group": ["sensors", "sensor_entities"],
        "csv_tape": "level_tape",
        "csv_parameters": [
            {"parameter": "level", "target_attribute": "sensor.level"},
        ],
    }

    csv_content = "seconds,level\n0,25\n3600,15\n"

    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    with set_timeline_info(timeline_info):
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = Path(tmp_dir)

            csv_model = CSVPlayer(csv_config)
            csv_tester = ModelTester(csv_model, tmp_dir=tmp_path, schema=schema)
            csv_tester.add_init_data("sensors", sensors_dataset)
            csv_tester.add_init_data("actuators", actuators_dataset)

            csv_file = tmp_path / "level_tape.csv"
            csv_file.write_text(csv_content)

            rules_model = Model(rules_config)
            rules_tester = ModelTester(rules_model, tmp_dir=tmp_path, schema=schema)

            csv_tester.initialize()
            rules_tester.initialize()

            # t=0: csv_player publishes level=25 for all sensor entities
            csv_tester.new_time(0)
            csv_result_t0, _ = csv_tester.update(0, None)

            rules_tester.new_time(0)
            rules_result_t0, _ = rules_tester.update(0, csv_result_t0)

            # t=3600: csv_player publishes level=15
            csv_tester.new_time(3600)
            csv_result_t3600, _ = csv_tester.update(3600, None)

            rules_tester.new_time(3600)
            rules_result_t3600, _ = rules_tester.update(3600, csv_result_t3600)

            csv_tester.close()
            rules_tester.close()
            csv_tester.cleanup()
            rules_tester.cleanup()

    # t=0: level=25 for all entities
    #   sensor 1 (id=1): 25 >= 23 -> actuator 10: pump_speed=1.5
    #   sensor 2 (id=2): 25 > 20  -> actuator 20: valve_open=True
    act_t0 = rules_result_t0["actuators"]["actuator_entities"]
    assert act_t0["control.pump_speed"] == [1.5, None]
    assert act_t0["control.valve_open"] == [None, True]

    # t=3600: level=15 for all entities
    #   sensor 1: 15 < 23 -> actuator 10: pump_speed=0.0
    #   sensor 2: 15 not > 20 -> actuator 20: valve_open=False
    act_t3600 = rules_result_t3600["actuators"]["actuator_entities"]
    assert act_t3600["control.pump_speed"] == [0.0, None]
    assert act_t3600["control.valve_open"] == [None, False]


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


@pytest.mark.xfail(
    reason="rules dataset 'data' section is incompatible with EntityInitDataFormat.read_dict()",
    raises=TypeError,
)
def test_rules_from_dataset():
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200)

    config = {
        "name": "rules_from_ds",
        "type": "rules",
        "rules_dataset": "my_rules",
    }

    rules_dataset = {
        "name": "my_rules",
        "type": "rules",
        "data": {
            "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
            "rules": [
                {
                    "if": "sensor.level >= 20",
                    "from_id": 1,
                    "to_id": 10,
                    "output": "control.pump_speed",
                    "value": 1.5,
                    "else_value": 0.0,
                },
            ],
        },
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("sensors", get_sensors_dataset())
            tester.add_init_data("actuators", get_actuators_dataset())
            tester.add_init_data("my_rules", rules_dataset)
            tester.initialize()

            tester.new_time(0)
            result, _ = tester.update(0, None)

    actuators = result["actuators"]["actuator_entities"]
    assert actuators["control.pump_speed"] == [1.5, None]


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


def test_missing_to_dataset_raises():
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=100)

    config = {
        "name": "rules_bad",
        "type": "rules",
        "rules": [
            {
                "if": "<simtime> >= 10",
                "to_id": 10,
                "output": "control.active",
                "value": True,
            },
        ],
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("actuators", get_actuators_dataset())
            with pytest.raises(RuleValidationError, match="to_dataset"):
                tester.initialize()


def test_missing_from_dataset_for_attribute_condition_raises():
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=100)

    config = {
        "name": "rules_bad",
        "type": "rules",
        "rules": [
            {
                "if": "sensor.level >= 20",
                "to_dataset": "actuators",
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.5,
            },
        ],
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("actuators", get_actuators_dataset())
            with pytest.raises(RuleValidationError, match="from_dataset"):
                tester.initialize()


def test_unknown_reference_raises():
    schema = get_schema()
    timeline_info = TimelineInfo(reference=0, time_scale=1, start_time=0, duration=100)

    config = {
        "name": "rules_bad",
        "type": "rules",
        "rules": [
            {
                "if": "<simtime> >= 10",
                "to_dataset": "actuators",
                "to_reference": "nonexistent",
                "output": "control.active",
                "value": True,
            },
        ],
    }

    model = Model(config)
    with set_timeline_info(timeline_info):
        with ModelTester(model, schema=schema) as tester:
            tester.add_init_data("actuators", get_actuators_dataset_with_refs())
            with pytest.raises(RuleValidationError, match="nonexistent"):
                tester.initialize()
