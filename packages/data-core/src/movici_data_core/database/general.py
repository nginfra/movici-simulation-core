from movici_data_core.database.model import (
    DEFAULT_SCHEMA_VERSION,
    DEFAULT_WORKSPACE_NAME,
    DatabaseMode,
    Metadata,
    Options,
    Workspace,
)
from movici_data_core.exceptions import DatabaseAlreadyInitialized, DatabaseNotYetInitialized
from sqlalchemy import func, insert, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload


async def initialize_database(session: AsyncSession, mode: DatabaseMode):
    metadata_count = (await session.scalar(select(func.count(Metadata.id)))) or 0
    options_count = (await session.scalar(select(func.count(Options.id)))) or 0

    if metadata_count > 0 or options_count > 0:
        raise DatabaseAlreadyInitialized
    await session.execute(insert(Metadata).values(id=1, version=DEFAULT_SCHEMA_VERSION))

    workspace_id = None
    if mode in (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE):
        workspaces_count = (await session.scalar(select(func.count(Options.id)))) or 0
        if workspaces_count > 0:
            raise DatabaseAlreadyInitialized

        workspace_id = await session.scalar(
            insert(Workspace)
            .returning(Workspace.id)
            .values(name=DEFAULT_WORKSPACE_NAME, display_name=DEFAULT_WORKSPACE_NAME)
        )

    await session.execute(
        insert(Options).values(
            default_workspace_id=workspace_id, mode=mode, **_default_flags(mode)
        )
    )


async def get_version(session: AsyncSession):
    metadata = await session.get(Metadata, 1)
    if not metadata:
        raise DatabaseNotYetInitialized
    return metadata.version


async def get_options(session: AsyncSession):
    options = await session.get(Options, 1, options=[selectinload(Options.default_workspace)])
    if not options:
        raise DatabaseNotYetInitialized
    return options


def _default_flags(mode: DatabaseMode):
    """Return a dictionary of default flags that must be set (to true), based on the ``mode``"""
    if mode == DatabaseMode.MULTIPLE_WORKSPACES:
        return {
            "STRICT_ATTRIBUTES": True,
            "STRICT_DATASET_TYPES": True,
            "STRICT_ENTITY_TYPES": True,
            "STRICT_MODELS": True,
            "STRICT_MODEL_CONFIGS": True,
        }
    return {}
