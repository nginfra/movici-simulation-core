import datetime
from datetime import timedelta

import pytest

from movici_data_core.domain_model import (
    ModelType,
    Scenario,
    ScenarioDataset,
    ScenarioModel,
    ScenarioStatus,
    SimulationStatus,
    SimulationStatusInfo,
)


@pytest.mark.parametrize(
    "config, error_message",
    [
        ({"name": "whoops"}, "Prohibited keys in found in ScenarioModel.config: name"),
        ({"type": "whoops"}, "Prohibited keys in found in ScenarioModel.config: type"),
        (
            {"name": "whoops", "type": "whoops"},
            "Prohibited keys in found in ScenarioModel.config: name, type",
        ),
    ],
)
def test_prohibited_scenario_model_keys(config, error_message):
    with pytest.raises(ValueError, match=error_message):
        ScenarioModel("some name", ModelType("sometype"), config=config)


@pytest.mark.parametrize(
    [
        "simulation_status",
        "status_timestamp_delta",
        "scenario_dataset_has_data",
        "scenario_has_updates",
        "expected_status",
    ],
    [
        (None, None, False, False, ScenarioStatus.INVALID),
        (None, None, True, False, ScenarioStatus.READY),
        (None, None, False, True, ScenarioStatus.INVALID),
        (None, None, True, True, ScenarioStatus.SUCCEEDED),
        (SimulationStatus.RUNNING, timedelta(seconds=9), False, False, ScenarioStatus.INVALID),
        (SimulationStatus.RUNNING, timedelta(seconds=9), True, False, ScenarioStatus.RUNNING),
        (SimulationStatus.RUNNING, timedelta(seconds=9), False, True, ScenarioStatus.INVALID),
        (SimulationStatus.RUNNING, timedelta(seconds=9), True, True, ScenarioStatus.RUNNING),
        (SimulationStatus.RUNNING, timedelta(seconds=11), False, False, ScenarioStatus.INVALID),
        (SimulationStatus.RUNNING, timedelta(seconds=11), True, False, ScenarioStatus.FAILED),
        (SimulationStatus.RUNNING, timedelta(seconds=11), False, True, ScenarioStatus.INVALID),
        (SimulationStatus.RUNNING, timedelta(seconds=11), True, True, ScenarioStatus.FAILED),
        (SimulationStatus.FAILED, None, False, False, ScenarioStatus.INVALID),
        (SimulationStatus.FAILED, None, True, False, ScenarioStatus.FAILED),
        (SimulationStatus.FAILED, None, False, True, ScenarioStatus.INVALID),
        (SimulationStatus.FAILED, None, True, True, ScenarioStatus.FAILED),
        (SimulationStatus.SUCCEEDED, None, False, False, ScenarioStatus.INVALID),
        (SimulationStatus.SUCCEEDED, None, True, False, ScenarioStatus.SUCCEEDED),
        (SimulationStatus.SUCCEEDED, None, False, True, ScenarioStatus.INVALID),
        (SimulationStatus.SUCCEEDED, None, True, True, ScenarioStatus.SUCCEEDED),
    ],
)
def test_scenario_status(
    simulation_status,
    status_timestamp_delta,
    scenario_dataset_has_data,
    scenario_has_updates,
    expected_status,
):
    now = datetime.datetime.now(tz=datetime.timezone.utc)
    status_timestamp_delta = status_timestamp_delta or timedelta(0)
    scenario = Scenario(
        "scenario",
        "Scenario",
        "",
        simulation_status_info=(
            SimulationStatusInfo(simulation_status, now - status_timestamp_delta)
            if simulation_status is not None
            else None
        ),
        datasets=[ScenarioDataset("a_dataset", has_data=scenario_dataset_has_data)],
        has_updates=scenario_has_updates,
    )
    assert scenario.status == expected_status
