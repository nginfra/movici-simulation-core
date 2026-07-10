from __future__ import annotations

import contextlib
import dataclasses
import pathlib
import typing as t
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncEngine, AsyncSession, async_sessionmaker

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
from movici_data_core.services.update import UpdateService
from movici_simulation_core import EntityInitDataFormat
from movici_simulation_core.core.data_format import NON_DATA_DICT_KEYS
from movici_simulation_core.types import ExternalSerializationStrategy

from . import model as db
from .general import (
    create_default_scenario,
    create_default_workspace,
    get_engine,
    get_options,
    initialize_database,
)
from .repository import SQLAlchemyRepository


class SQLAlchemyServer:
    """This class is responsible for building a ``SQLAlchemyBackend``. When running inside an
    FastAPI application, this class has the same lifetime as the application. From this class,
    request-scoped ``SQLAlchemyBackend`` instances are created.

    :param dbapi_url: a DB API url string
    :param serializer: a class for instantiating an ``ExternalSerializationStrategy``. Default:
      ``EntityInitDataFormat``
    :param tmpfile_dir: a path to a directory that may be used to store temporary files
    """

    dbapi_url: str
    tmpfile_dir: pathlib.Path
    serializer: ExternalSerializationStrategy

    session_factory: async_sessionmaker[AsyncSession]
    engine: AsyncEngine

    workspace_service_cls: t.Type[WorkspaceService] = WorkspaceService
    dataset_type_service_cls: t.Type[DatasetTypeService] = DatasetTypeService
    entity_type_service_cls: t.Type[EntityTypeService] = EntityTypeService
    attribute_type_service_cls: t.Type[AttributeTypeService] = AttributeTypeService
    model_type_service_cls: t.Type[ModelTypeService] = ModelTypeService
    dataset_service_cls: t.Type[DatasetService] = DatasetService
    scenario_service_cls: t.Type[ScenarioService] = ScenarioService
    update_service_cls: t.Type[UpdateService] = UpdateService

    def __init__(
        self,
        dbapi_url: str,
        tmpfile_dir: pathlib.Path,
        serializer: ExternalSerializationStrategy | None = None,
    ):

        self.dbapi_url = dbapi_url
        self.tmpfile_dir = tmpfile_dir
        self.serializer = serializer or EntityInitDataFormat(
            non_data_dict_keys=NON_DATA_DICT_KEYS + ("dataset",)
        )

    @contextlib.asynccontextmanager
    async def begin(self, **engine_kwargs):
        async with get_engine(self.dbapi_url, **engine_kwargs) as engine:
            self.engine = engine
            self.session_factory = async_sessionmaker(engine)
            yield self

    @contextlib.asynccontextmanager
    async def get_session(self, **session_kwargs):
        async with self.session_factory(**(session_kwargs or {})) as session:
            yield session

    @contextlib.asynccontextmanager
    async def get_backend(self, session_kwargs: dict[str, t.Any] | None = None):
        async with self.get_session(**(session_kwargs or {})) as session:
            try:
                yield await self.get_backend_for_session(session)
            except Exception:
                await session.rollback()
                raise
            else:
                await session.commit()

    async def get_backend_for_session(self, session: AsyncSession):
        options = await get_options(session)
        return await self._with_serializer(self._build_backend(session, options))

    async def setup_db(self, mode: db.DatabaseMode = db.DatabaseMode.SINGLE_SCENARIO):
        async with self.engine.begin() as conn:
            await conn.run_sync(db.Base.metadata.create_all)

        async with self.session_factory() as session:
            await initialize_database(session, mode)
            await session.commit()

    def _build_backend(self, session: AsyncSession, options: db.Options):
        backend = SQLAlchemyBackend(
            session,
            options,
            serializer=self.serializer,
            tmpfile_dir=self.tmpfile_dir,
            workspace_service_cls=self.workspace_service_cls,
            dataset_type_service_cls=self.dataset_type_service_cls,
            entity_type_service_cls=self.entity_type_service_cls,
            attribute_type_service_cls=self.attribute_type_service_cls,
            model_type_service_cls=self.model_type_service_cls,
            dataset_service_cls=self.dataset_service_cls,
            scenario_service_cls=self.scenario_service_cls,
            update_service_cls=self.update_service_cls,
        )
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

    async def _with_serializer(self, backend: SQLAlchemyBackend):
        schema = await backend.attribute_types.as_schema()
        return dataclasses.replace(backend, serializer=self.serializer.with_schema(schema))


@dataclasses.dataclass
class SQLAlchemyBackend:
    session: AsyncSession
    options: db.Options
    serializer: ExternalSerializationStrategy
    workspace_id: UUID | None = None
    scenario_id: UUID | None = None
    single_scenario_mode: bool = False
    single_workspace_mode: bool = False

    tmpfile_dir: pathlib.Path | None = None
    workspace_service_cls: t.Type[WorkspaceService] = WorkspaceService
    dataset_type_service_cls: t.Type[DatasetTypeService] = DatasetTypeService
    entity_type_service_cls: t.Type[EntityTypeService] = EntityTypeService
    attribute_type_service_cls: t.Type[AttributeTypeService] = AttributeTypeService
    model_type_service_cls: t.Type[ModelTypeService] = ModelTypeService
    dataset_service_cls: t.Type[DatasetService] = DatasetService
    scenario_service_cls: t.Type[ScenarioService] = ScenarioService
    update_service_cls: t.Type[UpdateService] = UpdateService

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
        return self.workspace_service_cls(self.repository)

    @property
    def dataset_types(self):
        return self.dataset_type_service_cls(self.repository)

    @property
    def entity_types(self):
        return self.entity_type_service_cls(self.repository)

    @property
    def attribute_types(self):
        return self.attribute_type_service_cls(self.repository)

    @property
    def model_types(self):
        return self.model_type_service_cls(self.repository)

    @property
    def datasets(self):
        return self.dataset_service_cls(self.repository, self.serializer, self.tmpfile_dir)

    @property
    def scenarios(self):
        return self.scenario_service_cls(
            self.repository, single_scenario_mode=self.single_scenario_mode
        )

    @property
    def updates(self):
        return self.update_service_cls(
            self.repository, serializer=self.serializer, tmpfile_dir=self.tmpfile_dir
        )

    async def set_database_mode(self, new_mode: db.DatabaseMode):
        """Change the mode of this database. Upgrading is always possible along the path
        ``SINGLE_SCENARIO`` -> ``SINGLE_WORKSPACE`` -> ``MULTIPLE_WORKSPACES``. Downgrading is only
        possible if a single workspace and/or scenario currently exists in the database

        :param new_mode: the new database mode
        """
        current_mode = self.options.mode
        if current_mode == new_mode:
            return

        match (current_mode, new_mode):
            case (db.DatabaseMode.MULTIPLE_WORKSPACES, db.DatabaseMode.SINGLE_SCENARIO):
                await self._downgrade_to_single_workspace_mode()
                await self._downgrade_to_single_scenario_mode()
            case (db.DatabaseMode.SINGLE_SCENARIO, db.DatabaseMode.MULTIPLE_WORKSPACES):
                await self._upgrade_to_single_workspace_mode()
                await self._upgrade_to_multiple_workspaces_mode()
            case (db.DatabaseMode.MULTIPLE_WORKSPACES, db.DatabaseMode.SINGLE_WORKSPACE):
                await self._downgrade_to_single_workspace_mode()
            case (db.DatabaseMode.SINGLE_WORKSPACE, db.DatabaseMode.MULTIPLE_WORKSPACES):
                await self._upgrade_to_multiple_workspaces_mode()
            case (db.DatabaseMode.SINGLE_WORKSPACE, db.DatabaseMode.SINGLE_SCENARIO):
                await self._downgrade_to_single_scenario_mode()
            case (db.DatabaseMode.SINGLE_SCENARIO, db.DatabaseMode.SINGLE_WORKSPACE):
                await self._upgrade_to_single_workspace_mode()

    async def _upgrade_to_single_workspace_mode(self):
        self.options.mode = db.DatabaseMode.SINGLE_WORKSPACE
        self.options.default_scenario = None
        self.single_scenario_mode = False

    async def _upgrade_to_multiple_workspaces_mode(self):
        self.options.mode = db.DatabaseMode.MULTIPLE_WORKSPACES
        self.options.default_workspace = None
        self.single_workspace_mode = False

    async def _downgrade_to_single_scenario_mode(self):
        scenarios = await self.repository.scenarios.list()
        if len(scenarios) > 1:
            raise InvalidAction(
                "Cannot downgrade to SINGLE_SCENARIO mode when multiple scenarios exist"
            )
        elif len(scenarios) == 1:
            scenario_id = scenarios[0].id
        else:
            if self.workspace_id is None:
                raise ValueError("workspace_id must be set")
            scenario_id = await create_default_scenario(self.session, self.workspace_id)
        self.options.mode = db.DatabaseMode.SINGLE_SCENARIO
        self.options.default_scenario_id = scenario_id
        self.single_scenario_mode = True
        self.scenario_id = scenario_id

    async def _downgrade_to_single_workspace_mode(self):
        workspaces = await self.repository.workspaces.list()
        if len(workspaces) > 1:
            raise InvalidAction(
                "Cannot downgrade to SINGLE_WORKSPACE mode when multiple workspaces exist"
            )
        elif len(workspaces) == 1:
            workspace_id = workspaces[0].id
        else:
            workspace_id = await create_default_workspace(self.session)
        self.options.mode = db.DatabaseMode.SINGLE_WORKSPACE
        self.options.default_workspace_id = workspace_id
        self.single_workspace_mode = True
        self.workspace_id = workspace_id

    def set_options(
        self,
        strict_dataset_types: bool | None = None,
        strict_entity_types: bool | None = None,
        strict_attribute_types: bool | None = None,
        strict_model_types: bool | None = None,
        strict_scenario_datasets: bool | None = None,
        immutable_workspace_names: bool | None = None,
    ):
        """Set various database options for the database

        :param strict_dataset_types: set/unset the ``STRICT_DATASET_TYPES`` option, which governs
          whether to automatically create non-existing dataset types when they are encountered in
          an uploaded dataset
        :param strict_entity_types: set/unset the ``STRICT_ENTITY_TYPES`` option, which governs
          whether to automatically create non-existing entity types when they are encountered in an
          uploaded dataset
        :param strict_attribute_types: set/unset the ``STRICT_ATTRIBUTE_TYPES`` option, which
          governs whether to automatically create non-existing attribute types when they are
          encountered in an uploaded dataset
        :param strict_model_types: set/unset the ``STRICT_MODEL_TYPES`` option, which governs
          whether to automatically create non-existing model types when they are encountered in an
          uploaded scenario config
        :param strict_scenario_datasets: set/unset the ``STRICT_SCENARIO_DATASETS`` option, which
          governs whether to automatically create stubs for non-existing datasets when they are
          encountered in an uploaded scenario config
        :param immutable_workspace_names: set/unset the  ``IMMUTABLE_WORKSPACE_NAMES`` option,
          which governes whether it is allowed to update a workspace name
        """
        if strict_dataset_types is not None:
            self.options.STRICT_DATASET_TYPES = strict_dataset_types
        if strict_entity_types is not None:
            self.options.STRICT_ENTITY_TYPES = strict_entity_types
        if strict_attribute_types is not None:
            self.options.STRICT_ATTRIBUTE_TYPES = strict_attribute_types
        if strict_model_types is not None:
            self.options.STRICT_MODEL_TYPES = strict_model_types
        if strict_scenario_datasets is not None:
            self.options.STRICT_SCENARIO_DATASETS = strict_scenario_datasets
        if immutable_workspace_names is not None:
            self.options.IMMUTABLE_WORKSPACE_NAMES = immutable_workspace_names

    async def update_schema(self):
        schema = await self.attribute_types.as_schema()
        self.serializer = self.serializer.with_schema(schema)
