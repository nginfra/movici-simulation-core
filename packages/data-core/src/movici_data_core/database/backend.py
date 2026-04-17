from __future__ import annotations

import contextlib
import dataclasses
import pathlib
import typing as t
from uuid import UUID

from movici_data_core.domain_model import Dataset, DatasetFormat, DatasetType, Scenario
from movici_data_core.exceptions import (
    InconsistentDatabase,
    InvalidAction,
    InvalidResource,
    ResourceDoesNotExist,
)
from movici_data_core.validators import ModelConfigValidator
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from movici_simulation_core.core import AttributeSchema
from movici_simulation_core.types import ExternalSerializationStrategy, FileType

from . import model as db
from .general import get_options
from .repository import SQLAlchemyRepository


class SQLAlchemyBackendFactory:
    def __init__(self, session_factory: async_sessionmaker[AsyncSession]):
        self.session_factory = session_factory
        pass

    @contextlib.asynccontextmanager
    async def get_backend(
        self,
        serializer: ExternalSerializationStrategy | None = None,
        session_kwargs: dict[str, t.Any] | None = None,
    ):
        async with self.session_factory(**(session_kwargs or {})) as session:
            options = await get_options(session)
            try:
                yield self._build_backend(session, options, serializer=serializer)
            except Exception:
                await session.rollback()
            else:
                await session.commit()

    @staticmethod
    def _build_backend(
        session: AsyncSession,
        options: db.Options,
        serializer: ExternalSerializationStrategy | None,
    ):
        backend = SQLAlchemyBackend(session, options, serializer)
        if options.mode == db.DatabaseMode.MULTIPLE_WORKSPACES:
            return backend

        if (workspace_id := options.default_workspace_id) is None:
            raise InconsistentDatabase("a default workspace is required")

        if options.mode == db.DatabaseMode.SINGLE_WORKSPACE:
            return dataclasses.replace(
                backend, workspace_id=workspace_id, single_workspace_mode=True
            )
        if options.mode == db.DatabaseMode.SINGLE_SCENARIO:
            if (scenario_id := options.default_scenario_id) is None:
                raise InconsistentDatabase("a default scenario is required")
            return dataclasses.replace(
                backend,
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
    serializer: ExternalSerializationStrategy | None = None
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

    @property
    def datasets(self):
        if self.serializer is None:
            raise RuntimeError("SQLAlchemyBackend.serializer must be set")
        return DatasetService(self.repository, self.serializer)

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

    async def get_attribute_schema(self):
        attribute_types = await self.repository.attribute_types.list()
        return AttributeSchema(a.to_attribute_spec() for a in attribute_types)


class WorkspaceService:
    def __init__(self, repository: SQLAlchemyRepository):
        self.repository = repository

    async def list(self):
        return await self.repository.workspaces.list()


class DatasetService:
    def __init__(
        self, repository: SQLAlchemyRepository, serializer: ExternalSerializationStrategy
    ):
        self.repository = repository
        self.serializer = serializer

    async def get(self, name: str | None = None, id: UUID | None = None) -> Dataset | None:
        if name is not None:
            result = await self.repository.datasets.get_by_name(name)
        elif id is not None:
            result = await self.repository.datasets.get_by_id(id)
        else:
            raise InvalidAction("Dataset name or id is required")

        if result is not None:
            assert result.id is not None
            result.has_data = await self.repository.dataset_data.exists_for(result.id)
        return result

    async def get_entity_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_entity_data(dataset_id)

    async def get_unstructured_data(self, dataset_id: UUID):
        return await self.repository.dataset_data.get_unstructured_data(dataset_id)

    async def stream_binary_data(self, dataset_id: UUID):
        return self.repository.dataset_data.stream_binary_data(dataset_id)

    async def update_from_file(
        self, dataset_id: UUID, path: pathlib.Path, mimetype: str | None = None
    ):
        existing = await self.repository.datasets.get_by_id(dataset_id)
        if existing is None:
            raise ResourceDoesNotExist("dataset", id=dataset_id)
        dataset_type = existing.dataset_type
        if dataset_type.format == DatasetFormat.ENTITY_BASED:
            file_type = FileType.from_extension(path.suffix)
            if file_type not in self.serializer.supported_file_types():
                raise InvalidResource(
                    "dataset",
                    id=dataset_id,
                    message=f"Unsupported file type '{path.suffix}' for"
                    f" dataset with type {dataset_type.name}",
                )
            dataset_dict = self.serializer.loads(path.read_bytes(), file_type)
            # TODO: use apilevel deserialization (eg pydantic) for deserialization
            if (
                new_dataset_type_name := (dataset_dict.get("type") or dataset_type.name)
            ) != dataset_type.name:
                dataset_type = await self.repository.dataset_types.ensure_dataset_type(
                    DatasetType(new_dataset_type_name, DatasetFormat.ENTITY_BASED)
                )

            dataset = Dataset(
                name=dataset_dict["name"],
                display_name=dataset_dict.get("display_name", dataset_dict["name"]),
                dataset_type=dataset_type,
                general=dataset_dict.get("general", {}),
                epsg_code=dataset_dict.get("epsg_code"),
                data=dataset_dict.get("data", {}),
            )

            return await self.repository.datasets.update_with_data(
                dataset_id, dataset, dataset_type.format
            )
        if dataset_type.format == DatasetFormat.UNSTRUCTURED:
            file_type = FileType.from_extension(path.suffix)
            if file_type not in (FileType.JSON, FileType.MSGPACK):
                raise InvalidResource(
                    "dataset",
                    id=dataset_id,
                    message=f"Unsupported file type '{path.suffix}' for"
                    f" dataset with type {dataset_type.name}",
                )


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
