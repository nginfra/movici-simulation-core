import asyncio
import dataclasses
import typing as t
from uuid import UUID

from fastapi import APIRouter, Depends

from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.schema import OperationSuccess, ScenarioIn, ScenarioList, ScenarioOut
from movici_data_core.validators import ModelConfigValidator

from .dependencies import DepBackend, DepWorkspaceBackend

scenario_router = APIRouter(prefix="/scenarios")


async def model_config_validator(backend: DepBackend):
    attribute_types, entity_types = await asyncio.gather(
        backend.attribute_types.list(), backend.entity_types.list()
    )
    return ModelConfigValidator.from_list_data(
        attribute_types=attribute_types, entity_types=entity_types
    )


DepModelConfigValidator = t.Annotated[ModelConfigValidator, Depends(model_config_validator)]


@scenario_router.get("/")
async def get_scenarios(backend: DepWorkspaceBackend) -> ScenarioList:
    scenarios = await backend.scenarios.list()
    return ScenarioList.from_domain(scenarios)


@scenario_router.post("/")
async def create_scenario(
    scenario: ScenarioIn, backend: DepWorkspaceBackend, validator: DepModelConfigValidator
) -> OperationSuccess:
    result = await backend.scenarios.create(scenario.to_domain(), validator)
    return OperationSuccess(resource="scenario", id=result, verb="created")


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

    await backend.for_scenario(scenario_id).scenarios.update(
        dataclasses.replace(scenario.to_domain()), validator
    )
    return OperationSuccess(resource="scenario", id=scenario_id, verb="updated")


@scenario_router.delete("/{scenario_id}")
async def delete_scenario(scenario_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.for_scenario(scenario_id).scenarios.delete()
    return OperationSuccess(resource="scenario", id=scenario_id, verb="deleted")
