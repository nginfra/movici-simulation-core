"""Example: Running the Rules Model in a Simulation.

Demonstrates how to set up a rules model inside a full Simulation with:
- A rules model that applies time-based and attribute-based conditions
- A data collector to store the results

The rules model updates actuator attributes based on sensor readings and
simulation time.
"""

import json
import sys
import tempfile
from pathlib import Path

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.models.data_collector.data_collector import DataCollector
from movici_simulation_core.models.rules.model import Model as RulesModel
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.testing.helpers import list_dir


def write_dataset(data_dir: Path, dataset: dict):
    """Write a dataset dict as a JSON file in data_dir."""
    (data_dir / dataset["name"]).with_suffix(".json").write_text(json.dumps(dataset))


def main():
    with tempfile.TemporaryDirectory() as tmp:
        data_dir = Path(tmp) / "data"
        storage_dir = Path(tmp) / "storage"
        data_dir.mkdir()
        storage_dir.mkdir()

        # -- Datasets --------------------------------------------------------
        write_dataset(
            data_dir,
            {
                "name": "sensors",
                "data": {
                    "sensor_entities": {
                        "id": [1, 2],
                        "reference": ["sensor_A", "sensor_B"],
                        "sensor.level": [25.0, 15.0],
                    }
                },
            },
        )

        write_dataset(
            data_dir,
            {
                "name": "actuators",
                "data": {
                    "actuator_entities": {
                        "id": [10, 20],
                        "reference": ["pump_1", "valve_1"],
                    }
                },
            },
        )

        # -- Model configs ---------------------------------------------------
        rules_config = {
            "name": "rules",
            "type": "rules",
            "defaults": {"from_dataset": "sensors", "to_dataset": "actuators"},
            "rules": [
                # Time-based: activate pump after 1 hour
                {
                    "if": "<simtime> >= 1h",
                    "to_reference": "pump_1",
                    "output": "control.active",
                    "value": True,
                    "else_value": False,
                },
                # Attribute-based: set pump speed when sensor level is high
                {
                    "if": "sensor.level >= 20",
                    "from_reference": "sensor_A",
                    "to_reference": "pump_1",
                    "output": "control.pump_speed",
                    "value": 1.5,
                    "else_value": 0.0,
                },
            ],
        }

        data_collector_config = {
            "name": "data_collector",
            "type": "data_collector",
            "gather_filter": "*",
        }

        # -- Simulation ------------------------------------------------------
        sim = Simulation(data_dir=data_dir, storage_dir=storage_dir)
        sim.add_model("rules", RulesModel, rules_config)
        sim.add_model("data_collector", DataCollector, data_collector_config)
        sim.set_timeline_info(TimelineInfo(reference=0, time_scale=1, start_time=0, duration=7200))

        exit_code = sim.run()

        # -- Inspect results -------------------------------------------------
        result_files = sorted(list_dir(storage_dir))
        print(f"Result files: {result_files}")
        for name in result_files:
            data = json.loads((storage_dir / name).read_text())
            print(f"\n{name}:")
            print(json.dumps(data, indent=2))

        return exit_code


if __name__ == "__main__":
    sys.exit(main())
