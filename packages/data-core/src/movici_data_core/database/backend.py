from __future__ import annotations

import contextlib
import dataclasses
from uuid import UUID

from movici_data_core.domain_model import Scenario
from movici_data_core.exceptions import InconsistentDatabase, InvalidAction, ResourceDoesNotExist
from movici_data_core.validators import ModelConfigValidator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from . import model as db
from .general import get_options
from .repository import SQLAlchemyRepository


class SQLAlchemyBackendFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        pass

    @contextlib.asynccontextmanager
    async def get_backend(self, **kwargs):
        async with self.session_factory(**kwargs) as session:
            options = await get_options(session)
            yield self._build_backend(session, options)

    @staticmethod
    def _build_backend(session: AsyncSession, options: db.Options):
        if options.mode == db.DatabaseMode.MULTIPLE_WORKSPACES:
            return SQLAlchemyBackend(session, options)

        if (workspace_id := options.default_workspace_id) is None:
            raise InconsistentDatabase("a default workspace is required")

        if options.mode == db.DatabaseMode.SINGLE_WORKSPACE:
            return SQLAlchemyBackend(
                session, options, workspace_id=workspace_id, single_workspace_mode=True
            )
        if options.mode == db.DatabaseMode.SINGLE_SCENARIO:
            if (scenario_id := options.default_scenario_id) is None:
                raise InconsistentDatabase("a default scenario is required")
            return SQLAlchemyBackend(
                session,
                options,
                workspace_id=workspace_id,
                scenario_id=scenario_id,
                single_workspace_mode=True,
                single_scenario_mode=True,
            )

        assert False, f"Unknown database mode {options.mode}"


@dataclasses.dataclass
class SQLAlchemyBackend:
    session: AsyncSession
    options: db.Options
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None
    single_scenario_mode: bool = False
    single_workspace_mode: bool = False

    @property
    def repository(self):
        return SQLAlchemyRepository(
            self.session, self.options, self.workspace_id, self.scenario_id
        )

    def for_workspace(self, workspace_id: UUID):
        return dataclasses.replace(self, workspace_id=workspace_id)

    def for_scenario(self, scenario_id: UUID):
        return dataclasses.replace(self, scenario_id=scenario_id)

    @property
    def workspaces(self) -> WorkspaceService:
        if self.single_workspace_mode:
            raise InvalidAction("workspaces are not supported in this mode")
        return WorkspaceService(self.repository)

    @property
    def scenarios(self):
        return ScenarioService(self.repository, single_scenario_mode=self.single_scenario_mode)

    def set_options(
        self,
        strict_dataset_types: bool | None = None,
        strict_entity_types: bool | None = None,
        strict_attributes: bool | None = None,
        strict_model_types: bool | None = None,
        strict_scenario_datasets: bool | None = None,
    ):
        if strict_dataset_types is not None:
            self.options.STRICT_DATASET_TYPES = strict_dataset_types
        if strict_entity_types is not None:
            self.options.STRICT_ENTITY_TYPES = strict_entity_types
        if strict_attributes is not None:
            self.options.STRICT_ATTRIBUTES = strict_attributes
        if strict_model_types is not None:
            self.options.STRICT_MODEL_TYPES = strict_model_types
        if strict_scenario_datasets is not None:
            self.options.STRICT_SCENARIO_DATASETS = strict_scenario_datasets

    def get_dataset_schema(self):
        pass


class WorkspaceService:
    def __init__(self, repository: SQLAlchemyRepository):
        self.repository = repository

    async def list(self):
        return await self.repository.workspaces.list()


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
