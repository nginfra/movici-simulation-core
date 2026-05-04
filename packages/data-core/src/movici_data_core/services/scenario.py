from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import Scenario
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator


class ScenarioService:
    def __init__(self, repository: SQLAlchemyRepository, single_scenario_mode: bool):
        self.repository = repository
        self.single_scenario_mode = single_scenario_mode

    async def list(self):
        return await self.repository.scenarios.list()

    async def get(self, name: str | None = None, id: UUID | None = None) -> Scenario | None:
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

    async def create(self, scenario: Scenario, validator: ModelConfigValidator):
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
