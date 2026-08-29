import dataclasses
import typing as t

import pytest

from movici_data_core.database.backend import SQLAlchemyBackend
from movici_data_core.database.model import DatabaseMode
from movici_data_core.domain_model import (
    Dataset,
    DatasetSummary,
    Scenario,
    ScenarioDataset,
    ScenarioStatus,
    SimulationStatus,
)
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.testing import dataset_data_to_numpy


async def test_get_scenario_by_name(backend: SQLAlchemyBackend, a_workspace, a_scenario):
    backend = backend.for_workspace(a_workspace.id)
    scenario = await backend.scenarios.get(name=a_scenario.name)
    assert scenario is not None
    assert scenario.id == a_scenario.id


async def test_get_scenario_by_id(backend: SQLAlchemyBackend, a_workspace, a_scenario):
    backend = backend.for_workspace(a_workspace.id)
    scenario = await backend.scenarios.get(id=a_scenario.id)
    assert scenario is not None
    assert scenario.name == a_scenario.name


async def test_get_active_scenario(backend: SQLAlchemyBackend, a_scenario):
    backend = backend.for_scenario(a_scenario.id)
    scenario = await backend.scenarios.get()
    assert scenario is not None
    assert scenario.name == a_scenario.name


async def test_get_summary_by_name(backend: SQLAlchemyBackend, a_scenario, a_dataset):
    summary = await backend.for_scenario(a_scenario.id).scenarios.get_summary(a_dataset.name)
    assert isinstance(summary, DatasetSummary)


async def test_get_summary_by_id(backend: SQLAlchemyBackend, a_scenario, a_dataset):
    summary = await backend.for_scenario(a_scenario.id).scenarios.get_summary(str(a_dataset.id))
    assert isinstance(summary, DatasetSummary)


@pytest.mark.database_mode(DatabaseMode.SINGLE_SCENARIO)
@pytest.mark.parametrize(
    "a_dataset_has_data, another_dataset_has_data, expected_status",
    [
        (False, False, ScenarioStatus.INVALID),
        (True, False, ScenarioStatus.INVALID),
        (False, True, ScenarioStatus.INVALID),
        (True, True, ScenarioStatus.READY),
    ],
)
async def test_calculate_scenario_status_from_scenario_datasets(
    backend: SQLAlchemyBackend,
    a_scenario,
    a_dataset,
    a_dataset_type,
    a_dataset_has_data,
    another_dataset_has_data,
    expected_status,
):
    dataset_data = dataset_data_to_numpy({"roads": {"id": [1]}})
    another_dataset = Dataset("antoher_dataset", "another dataset", a_dataset_type)
    another_dataset_id = await backend.datasets.create(another_dataset)
    await backend.scenarios.update(
        dataclasses.replace(
            a_scenario,
            datasets=[
                ScenarioDataset.from_dataset(a_dataset),
                ScenarioDataset.from_dataset(another_dataset),
            ],
        ),
        validator=ModelConfigValidator(),
    )

    if a_dataset_has_data:
        await backend.datasets.update(
            a_dataset.id, dataclasses.replace(a_dataset, data=dataset_data)
        )
    if another_dataset_has_data:
        await backend.datasets.update(
            another_dataset_id, dataclasses.replace(another_dataset, data=dataset_data)
        )

    scenario = await backend.scenarios.get()
    assert scenario is not None
    assert scenario.status == expected_status


@pytest.mark.database_mode(DatabaseMode.SINGLE_SCENARIO)
@pytest.mark.usefixtures("a_dataset_with_data")
async def test_updated_simulation_status_gets_reflected_in_scenario(backend: SQLAlchemyBackend):
    assert t.cast(Scenario, await backend.scenarios.get()).status == ScenarioStatus.READY
    await backend.scenarios.update_simulation_status(SimulationStatus.RUNNING)
    assert t.cast(Scenario, await backend.scenarios.get()).status == ScenarioStatus.RUNNING
