import json

import pytest

from movici_simulation_core.core.moment import TimelineInfo
from movici_simulation_core.models.data_collector.data_collector import DataCollector
from movici_simulation_core.models.tape_player.model import Model as TapePlayer
from movici_simulation_core.simulation import Simulation
from movici_simulation_core.testing.helpers import list_dir


@pytest.fixture
def data_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("init_data")


@pytest.fixture
def storage_dir(tmp_path_factory):
    return tmp_path_factory.mktemp("storage")


@pytest.fixture
def tapefile(data_dir):
    name = "tapefile"
    target_dataset = "dataset"
    content = {
        "name": name,
        "type": "tabular",
        "format": "unstructured",
        "data": {
            "tabular_data_name": target_dataset,
            "time_series": [0, 1],
            "data_series": [
                {"entities": {"id": [1], "attribute": [10]}},
                {"entities": {"id": [1], "attribute": [11]}},
            ],
        },
    }
    data_dir.joinpath(name).with_suffix(".json").write_text(json.dumps(content))
    return name


def test_simulation_with_tape_player_and_data_collector(tmp_path, data_dir, storage_dir, tapefile):
    sim = Simulation(data_dir=data_dir, storage_dir=storage_dir, debug=True)
    sim.add_model("data_collector", DataCollector, {})
    sim.add_model("tape_player", TapePlayer, {"tabular": [tapefile]})
    sim.set_timeline_info(TimelineInfo(0, 1, 0, duration=1))
    sim.run()
    assert {"t0_0_dataset.json", "t1_0_dataset.json"}.issubset(set(list_dir(storage_dir)))
