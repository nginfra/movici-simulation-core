from __future__ import annotations

import contextlib
import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from movici_data_core.exceptions import (
    InconsistentDatabase,
    InvalidAction,
)
from movici_data_core.services import (
    AttributeTypeService,
    DatasetService,
    DatasetTypeService,
    EntityTypeService,
    ModelTypeService,
    ScenarioService,
    WorkspaceService,
)
from movici_simulation_core.types import ExternalSerializationStrategy

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
    def workspaces(self):
        if self.single_workspace_mode:
            raise InvalidAction("workspaces are not supported in this mode")
        return WorkspaceService(self.repository)

    @property
    def dataset_types(self):
        return DatasetTypeService(self.repository)

    @property
    def entity_types(self):
        return EntityTypeService(self.repository)

    @property
    def attribute_types(self):
        return AttributeTypeService(self.repository)

    @property
    def model_types(self):
        return ModelTypeService(self.repository)

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
