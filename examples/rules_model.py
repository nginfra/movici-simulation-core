"""Example usage of the Rules Model.

Demonstrates:
1. Standalone rules model with all condition types (simtime, attribute vs literal,
   attribute vs attribute, literal on left side)
2. Pairing rules model with csv_player to react to changing attribute values
3. Using ModelTester.run_scenario() for declarative scenario testing
"""

import tempfile
from pathlib import Path

from movici_simulation_core.attributes import GlobalAttributes
from movici_simulation_core.core.moment import TimelineInfo, set_timeline_info
from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.models.csv_player.csv_player import CSVPlayer
from movici_simulation_core.models.rules.model import Model
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
            # Time-based: activate after 1h (targets actuator 10 only)
            {
                "if": "<simtime> >= 3600",
                "from_id": 1,
                "to_id": 10,
                "output": "control.active",
                "value": True,
                "else_value": False,
            },
            # Attribute vs literal (targets actuator 10 only)
            {
                "if": "sensor.level >= 23",
                "from_id": 1,
                "to_id": 10,
                "output": "control.pump_speed",
                "value": 1.5,
                "else_value": 0.0,
            },
            # Attribute vs attribute (targets actuator 20 only)
            {
                "if": "sensor.level > sensor.threshold",
                "from_id": 2,
                "to_id": 20,
                "output": "control.valve_open",
                "value": True,
                "else_value": False,
            },
            # Literal on left side (targets actuator 20 only)
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


# ---------------------------------------------------------------------------
# Part 1: Standalone rules model with ModelTester
# ---------------------------------------------------------------------------


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
            print("=== Part 1: Standalone rules model ===")
            print(f"t=0 result: {result_t0}")
            print(f"t=0 next_moment: {next_moment_t0}")
            # Each rule targets one specific actuator entity:
            #   actuator 10: active=False (simtime 0 < 3600), pump_speed=1.5 (level 25 >= 23)
            #   actuator 20: valve_open=False (level 15 not > 20), alarm=True (20 > 15)

            # t=3600: simtime >= 3600 so control.active flips to True
            tester.new_time(3600)
            result_t3600, next_moment_t3600 = tester.update(3600, None)
            print(f"t=3600 result: {result_t3600}")
            print(f"t=3600 next_moment: {next_moment_t3600}")
            # Only the changed value is returned: active flipped from False to True

    actuators_t0 = result_t0["actuators"]["actuator_entities"]
    # Rule 1 targets actuator 10 (idx 0): active=False; actuator 20 (idx 1) is None (no rule)
    assert actuators_t0["control.active"] == [False, None], actuators_t0
    # Rule 2 targets actuator 10: pump_speed=1.5; actuator 20 is None
    assert actuators_t0["control.pump_speed"] == [1.5, None], actuators_t0
    # Rule 3 targets actuator 20: valve_open=False; actuator 10 is None
    assert actuators_t0["control.valve_open"] == [None, False], actuators_t0
    # Rule 4 targets actuator 20: alarm=True (20 > 15); actuator 10 is None
    assert actuators_t0["control.alarm"] == [None, True], actuators_t0

    # At t=0, next trigger should be at timestamp=3600 (the "<simtime> >= 3600" threshold)
    # ModelTester converts the returned Moment to a timestamp (int)
    assert next_moment_t0 == 3600, next_moment_t0

    # At t=3600 only control.active changed (False -> True)
    actuators_t3600 = result_t3600["actuators"]["actuator_entities"]
    assert actuators_t3600["control.active"] == [True], actuators_t3600

    # At t=3600, simtime threshold (3600) is no longer in the future, so no next trigger
    assert next_moment_t3600 is None


# ---------------------------------------------------------------------------
# Part 2: Paired with csv_player
# ---------------------------------------------------------------------------


def test_paired_with_csv_player():
    schema = get_schema()

    sensors_dataset = get_sensors_dataset()
    actuators_dataset = get_actuators_dataset()

    # Two attribute-based rules for clarity
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

    # CSV tape: at t=0 level=25 for all entities, at t=3600 level=15
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

            print("\n=== Part 2: Paired with csv_player ===")

            # t=0: csv_player publishes level=25 for all sensor entities
            csv_tester.new_time(0)
            csv_result_t0, csv_next = csv_tester.update(0, None)
            print(f"csv_player t=0 output: {csv_result_t0}")

            # Feed csv output into rules model
            rules_tester.new_time(0)
            rules_result_t0, _ = rules_tester.update(0, csv_result_t0)
            print(f"rules t=0 result: {rules_result_t0}")
            # level=25 for all entities:
            #   sensor 1 (id=1): 25 >= 23 -> actuator 10: pump_speed=1.5
            #   sensor 2 (id=2): 25 > 20  -> actuator 20: valve_open=True

            # t=3600: csv_player publishes level=15
            csv_tester.new_time(3600)
            csv_result_t3600, _ = csv_tester.update(3600, None)
            print(f"csv_player t=3600 output: {csv_result_t3600}")

            rules_tester.new_time(3600)
            rules_result_t3600, _ = rules_tester.update(3600, csv_result_t3600)
            print(f"rules t=3600 result: {rules_result_t3600}")
            # level=15 for all entities:
            #   sensor 1: 15 < 23 -> actuator 10: pump_speed=0.0
            #   sensor 2: 15 not > 20 -> actuator 20: valve_open=False

            csv_tester.close()
            rules_tester.close()
            csv_tester.cleanup()
            rules_tester.cleanup()

    # t=0: first update, all assignments are new
    act_t0 = rules_result_t0["actuators"]["actuator_entities"]
    assert act_t0["control.pump_speed"] == [1.5, None], act_t0
    assert act_t0["control.valve_open"] == [None, True], act_t0

    # t=3600: values flip — pump_speed 1.5->0.0, valve_open True->False
    act_t3600 = rules_result_t3600["actuators"]["actuator_entities"]
    assert act_t3600["control.pump_speed"] == [0.0, None], act_t3600
    assert act_t3600["control.valve_open"] == [None, False], act_t3600


# ---------------------------------------------------------------------------
# Part 3: run_scenario
# ---------------------------------------------------------------------------


def test_run_scenario():
    schema = get_schema()
    model_config = get_model_config()
    sensors_dataset = get_sensors_dataset()
    actuators_dataset = get_actuators_dataset()

    # Expected at t=0 (first update — all values are new):
    #   actuator 10 (idx 0): active=False, pump_speed=1.5
    #   actuator 20 (idx 1): valve_open=False, alarm=True
    #   Non-targeted slots are None
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

    # Expected at t=3600: only control.active changed (False -> True)
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
            {"name": "sensors", "data": sensors_dataset},
            {"name": "actuators", "data": actuators_dataset},
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

    print("\n=== Part 3: run_scenario ===")
    ModelTester.run_scenario(Model, "rules_example", scenario, global_schema=schema)
    print("run_scenario passed!")


def test_all():
    test_standalone_rules()
    test_paired_with_csv_player()
    test_run_scenario()


if __name__ == "__main__":
    test_all()
    print("\nAll examples passed!")
