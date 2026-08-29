import typing as t
from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import Scenario, SimulationStatus, Workspace
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator


class ScenarioService:
    def __init__(self, repository: SQLAlchemyRepository, single_scenario_mode: bool):
        self.repository = repository
        self.single_scenario_mode = single_scenario_mode

    async def list(self):
        scenarios = await self.repository.scenarios.list()
        datasets_have_data = await self._datasets_have_data()
        return [s.with_status(datasets_have_data) for s in scenarios]

    async def get(self, name: str | None = None, id: UUID | None = None) -> Scenario | None:
        if name is not None:
            result = await self.repository.scenarios.get_by_name(name)
        elif id is not None:
            result = await self.repository.scenarios.for_id(id).get()
        elif self.repository.scenario_id is not None:
            result = await self.repository.scenarios.get()
        else:
            raise InvalidAction("Scenario name or id is required")
        if result is not None:
            datasets_have_data = await self._datasets_have_data(result.workspace)
            result = result.with_status(datasets_have_data)
        return result

    async def create(self, scenario: Scenario, validator: ModelConfigValidator):
        if self.single_scenario_mode:
            raise InvalidAction("Unsupported operation in this mode")
        return await self.repository.scenarios.create(scenario, validator)

    async def update(self, scenario: Scenario, validator: ModelConfigValidator):
        return await self.repository.scenarios.update(scenario, validator)

    async def delete(self):
        if self.single_scenario_mode:
            raise InvalidAction("Unsupported operation in this mode")
        if not await self.repository.scenarios.exists():
            raise ResourceDoesNotExist("scenario", id=self.repository.scenario_id)
        return await self.repository.scenarios.delete()

    async def get_summary(self, dataset_name_or_id: str):
        scenario_dataset = await self.repository.scenarios.ensure_valid_scenario_dataset(
            dataset_name_or_id
        )
        assert scenario_dataset.id is not None
        return await self.repository.scenarios.get_summary(scenario_dataset.id)

    async def update_simulation_status(self, status: SimulationStatus):
        await self.repository.scenarios.update_simulation_status(status)

    async def _datasets_have_data(self, workspace: Workspace | None = None) -> dict[UUID, bool]:
        """
        Return a dictionary of dataset id and wether they have data that can be used to calculate
        a ScenarioStatus for a Scenario. See also :meth:``Scenario.with_status``

        :param workspace: the workspace to retrieve the datasets for. Can be omitted if the
            repository is already properly configured, such as within the ``ScenarioService.list``
            method

        :return: A dictionary with Dataset ``UUID`` as keys and ``bool`` as values indicating
            whether these these datasets have data.
        """
        if workspace is None:
            if self.repository.workspace_id is None:
                raise ValueError("Please supply a workspace")
            repository = self.repository
        else:
            if workspace.id is None:
                raise ValueError("Workspace.id may not be None")
            repository = self.repository.for_workspace(workspace.id)
        all_datasets = await repository.datasets.list()
        return {t.cast(UUID, ds.id): ds.has_data for ds in all_datasets}
