import contextlib

from movici_data_core.domain_model import Workspace
from movici_data_core.exceptions import InconsistentDatabase
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from .general import get_options
from .model import DatabaseMode, Options, to_domain_or_none
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
    def _build_backend(session: AsyncSession, options: Options):
        if options.mode == DatabaseMode.MULTIPLE_WORKSPACES:
            return MultipleWorkspacesBackend(session, options)

        if (workspace := to_domain_or_none(options.default_workspace)) is None:
            raise InconsistentDatabase("a default workspace is required")

        if options.mode == DatabaseMode.SINGLE_WORKSPACE:
            return SingleWorkspaceBackend(session, options, workspace=workspace)
        if options.mode == DatabaseMode.SINGLE_SCENARIO:
            return SingleScenarioBackend(session, options, workspace=workspace)

        assert False, f"Unknown database mode {options.mode}"


class SQLAlchemyBackend:
    def __init__(self, session: AsyncSession, options: Options):
        self.session = session
        self.options = options

    @property
    def repository(self):
        return SQLAlchemyRepository(self.session, self.options)

    def set_options(
        self,
        strict_dataset_types: bool | None = None,
        strict_entity_types: bool | None = None,
        strict_attributes: bool | None = None,
        strict_model_types: bool | None = None,
    ):
        if strict_dataset_types is not None:
            self.options.STRICT_DATASET_TYPES = strict_dataset_types
        if strict_entity_types is not None:
            self.options.STRICT_ENTITY_TYPES = strict_entity_types
        if strict_attributes is not None:
            self.options.STRICT_ATTRIBUTES = strict_attributes
        if strict_model_types is not None:
            self.options.STRICT_MODEL_TYPES = strict_model_types

    def get_dataset_schema(self):
        pass


class MultipleWorkspacesBackend(SQLAlchemyBackend):
    def for_workspace(self, workspace: Workspace):
        return SingleWorkspaceBackend(self.session, self.options, workspace=workspace)


class SingleWorkspaceBackend(SQLAlchemyBackend):
    def __init__(self, session: AsyncSession, options: Options, workspace: Workspace):
        super().__init__(session, options)
        self.workspace = workspace


class SingleScenarioBackend(SQLAlchemyBackend):
    def __init__(self, session: AsyncSession, options: Options, workspace: Workspace):
        super().__init__(session, options)
        self.workspace = workspace
