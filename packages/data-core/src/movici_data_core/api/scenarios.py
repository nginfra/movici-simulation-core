import typing as t
from uuid import UUID

from fastapi import APIRouter, Depends, Query

from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.marshalling import (
    DatasetSummaryOut,
    OperationSuccess,
    ScenarioIn,
    ScenarioListOut,
    ScenarioOut,
)
from movici_data_core.validators import ModelConfigValidator

from .dependencies import DepBackend, DepWorkspaceBackend, allow_in_modes

scenario_router = APIRouter(prefix="/scenarios")


async def model_config_validator(backend: DepBackend):
    attribute_types = await backend.attribute_types.list()
    entity_types = await backend.entity_types.list()
    return ModelConfigValidator.from_list_data(
        attribute_types=attribute_types, entity_types=entity_types
    )


DepModelConfigValidator = t.Annotated[ModelConfigValidator, Depends(model_config_validator)]


@scenario_router.get("")
async def get_scenarios(backend: DepWorkspaceBackend) -> ScenarioListOut:
    scenarios = await backend.scenarios.list()
    return ScenarioListOut.from_domain(scenarios)


@scenario_router.post(
    "",
    dependencies=[
        allow_in_modes(
            "create scenario", [DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.MULTIPLE_WORKSPACES]
        )
    ],
)
async def create_scenario(
    scenario: ScenarioIn,
    backend: DepWorkspaceBackend,
    validator: DepModelConfigValidator,
) -> OperationSuccess:
    result = await backend.scenarios.create(scenario.to_domain(), validator)
    return OperationSuccess.for_path_operation(resource="scenario", id=result, verb="created")


@scenario_router.get("/{scenario_id}")
async def get_scenario(scenario_id: UUID, backend: DepBackend) -> ScenarioOut:
    scenario = await backend.scenarios.get(id=scenario_id)
    if scenario is None:
        raise ResourceDoesNotExist("scenario", id=scenario_id)
    return ScenarioOut.from_domain(scenario)


@scenario_router.put("/{scenario_id}")
async def update_scenario(
    scenario_id: UUID,
    scenario: ScenarioIn,
    backend: DepBackend,
    validator: DepModelConfigValidator,
) -> OperationSuccess:
    await backend.for_scenario(scenario_id).scenarios.update(scenario.to_domain(), validator)
    return OperationSuccess.for_path_operation(resource="scenario", id=scenario_id, verb="updated")


@scenario_router.delete(
    "/{scenario_id}",
    dependencies=[
        allow_in_modes(
            "delete scenario", [DatabaseMode.SINGLE_WORKSPACE, DatabaseMode.MULTIPLE_WORKSPACES]
        )
    ],
)
async def delete_scenario(scenario_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.for_scenario(scenario_id).scenarios.delete()
    return OperationSuccess.for_path_operation(resource="scenario", id=scenario_id, verb="deleted")


@scenario_router.get("/{scenario_id}/summary")
async def get_scenario_summary(
    scenario_id: UUID, dataset_q: t.Annotated[str, Query(alias="dataset")], backend: DepBackend
) -> DatasetSummaryOut:
    result = await backend.for_scenario(scenario_id).scenarios.get_summary(dataset_q)
    return DatasetSummaryOut.from_domain(result)
