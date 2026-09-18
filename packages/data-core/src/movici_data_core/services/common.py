import typing as t
from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.database.repository.common import GenericResourceRepository
from movici_data_core.domain_model import Scenario, Workspace
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist

T_dom = t.TypeVar("T_dom")


class GenericService(t.Generic[T_dom]):
    def __init__(self, repository: SQLAlchemyRepository):
        self.repository = repository

    @property
    def _repository(self) -> GenericResourceRepository[T_dom]:
        raise NotImplementedError

    async def list(self):
        return await self._repository.list()

    async def get(self, name: str | None = None, id: UUID | None = None) -> T_dom | None:
        if name is not None:
            result = await self._repository.get_by_name(name)
        elif id is not None:
            result = await self._repository.get_by_id(id)
        else:
            raise InvalidAction("name or id is required")

        return result

    async def create(self, obj: T_dom):
        return await self._repository.create(obj)

    async def update(self, id: UUID, obj: T_dom):
        return await self._repository.update(id=id, obj=obj)

    async def delete(self, id: UUID):
        return await self._repository.delete(id)


async def ensure_valid_workspace(
    name_or_id: str | None, repository: SQLAlchemyRepository
) -> Workspace:
    if not name_or_id:
        raise InvalidAction("supply a workspace name or id")

    # try workspace as a UUID
    try:
        workspace_id = UUID(name_or_id)
    except ValueError:
        workspace_id = None

    if workspace_id is not None:
        # workspace was given as a uuid
        workspace_obj = await repository.workspaces.get_by_id(id=workspace_id)
        if workspace_obj is None:
            raise ResourceDoesNotExist("workspace", id=workspace_id)
    else:
        # workspace was given as a name
        workspace_obj = await repository.workspaces.get_by_name(name_or_id)
        if workspace_obj is None:
            raise ResourceDoesNotExist("workspace", name=name_or_id)

    return workspace_obj


async def ensure_valid_scenario(
    scenario_name_or_id: str | None,
    workspace_name_or_id: str | None,
    repository: SQLAlchemyRepository,
) -> Scenario:

    if not scenario_name_or_id:
        raise InvalidAction("supply a scenario name or id")

    # try scenario as a UUID
    try:
        scenario_id = UUID(scenario_name_or_id)
    except ValueError:
        scenario_id = None

    if scenario_id is not None:
        # scenario was given as a uuid
        scenario_obj = await repository.scenarios.for_id(scenario_id).get()
        if scenario_obj is None:
            raise ResourceDoesNotExist("scenario", id=scenario_id)
    else:
        # scenario was given as a name, we also need the workspace
        if repository.workspace_id is None:
            try:
                workspace = await ensure_valid_workspace(workspace_name_or_id, repository)
            except InvalidAction:
                raise InvalidAction(
                    "when supplying a scenario by name, also supply a workspace name or id"
                ) from None
            assert workspace.id is not None
            repository = repository.for_workspace(workspace.id)

        scenario_obj = await repository.scenarios.get_by_name(scenario_name_or_id)
        if scenario_obj is None:
            raise ResourceDoesNotExist("scenario", name=scenario_name_or_id)

    return scenario_obj
