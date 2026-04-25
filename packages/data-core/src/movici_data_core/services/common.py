import typing as t

from movici_data_core.domain_model import (
    Scenario,
)
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist
from movici_data_core.types import MoviciDataRepository, ResourceRepository, T_id
from movici_data_core.validators import BaseModelConfigValidator

T_dom = t.TypeVar("T_dom")


class GenericService(t.Generic[T_id, T_dom]):
    repository: MoviciDataRepository[T_id]

    def __init__(self, repository: MoviciDataRepository[T_id]):
        self.repository = repository

    @property
    def _repository(self) -> ResourceRepository[T_id, T_dom]:
        raise NotImplementedError

    async def list(self):
        return await self._repository.list()

    async def get(self, name: str | None = None, id: T_id | None = None) -> T_dom | None:
        if name is not None:
            result = await self._repository.get_by_name(name)
        elif id is not None:
            result = await self._repository.get_by_id(id)
        else:
            raise InvalidAction("name or id is required")

        return result

    async def create(self, obj: T_dom):
        return await self._repository.create(obj)

    async def update(self, id: T_id, obj: T_dom):
        return await self._repository.update(id=id, obj=obj)

    async def delete(self, id: T_id):
        return await self._repository.delete(id)


class ScenarioService(t.Generic[T_id]):
    repository: MoviciDataRepository[T_id]

    def __init__(self, repository: MoviciDataRepository[T_id], single_scenario_mode: bool):
        self.repository = repository
        self.single_scenario_mode = single_scenario_mode

    async def list(self):
        return await self.repository.scenarios.list()

    async def get(self, name: str | None = None, id: T_id | None = None) -> Scenario | None:
        if name is not None:
            result = await self.repository.scenarios.get_by_name(name)
        elif id is not None:
            result = await self.repository.scenarios.for_id(id).get_by_id()
        elif self.repository.scenario_id is not None:
            result = await self.repository.scenarios.get_by_id()
        else:
            raise InvalidAction("Scenario name or id is required")

        if result is not None:
            result.has_updates = await self.repository.updates.exists()
        return result

    async def create(self, scenario: Scenario, validator: BaseModelConfigValidator):
        if self.single_scenario_mode:
            raise InvalidAction("Unsupported operation in this mode")
        return await self.repository.scenarios.create(scenario, validator)

    async def update(self, scenario: Scenario, validator):
        return await self.repository.scenarios.update(scenario, validator)

    async def delete(self):
        if self.single_scenario_mode:
            raise InvalidAction("Unsupported operation in this mode")
        if not await self.repository.scenarios.exists():
            raise ResourceDoesNotExist("scenario", id=self.repository.scenario_id)
        return await self.repository.scenarios.delete()
