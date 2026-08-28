import pathlib
from uuid import UUID

from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import Scenario, ScenarioStateFilter
from movici_data_core.exceptions import InvalidAction, ResourceDoesNotExist, UnsupportedFileType
from movici_data_core.file_helpers import tempfile_delete_on_error
from movici_data_core.validators import ModelConfigValidator
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


class ScenarioService:
    def __init__(
        self,
        repository: SQLAlchemyRepository,
        single_scenario_mode: bool,
        serializer: ExternalSerializationStrategy,
        tmpfile_dir: pathlib.Path,
    ):
        self.repository = repository
        self.single_scenario_mode = single_scenario_mode
        self.serializer = serializer
        self.tmpfile_dir = tmpfile_dir

    async def list(self):
        return await self.repository.scenarios.list()

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
            assert result.id is not None
            result.has_updates = await self.repository.for_scenario(result.id).updates.exists()
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

    async def get_state_as_file(
        self, state_filter: ScenarioStateFilter, filetype=FileType.JSON
    ) -> pathlib.Path | None:
        if not (await self.repository.scenarios.exists()):
            return None

        with tempfile_delete_on_error(
            suffix=filetype.default_extension,
            prefix=f"scenario-state-{state_filter.dataset}",
            dir=self.tmpfile_dir,
        ) as outfile:
            if filetype not in self.serializer.supported_file_types():
                raise UnsupportedFileType(filetype)

            data = await self.repository.scenarios.get_state(state_filter)

            outfile.write(
                self.serializer.dumps(
                    {"data": data},
                    filetype=filetype,
                )
            )

        return pathlib.Path(outfile.name)
