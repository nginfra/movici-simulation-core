import contextlib
import dataclasses
import typing as t
from uuid import UUID

from sqlalchemy import event, func, insert, select, text, update
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import joinedload

from movici_data_core.database.model import (
    DEFAULT_SCENARIO_NAME,
    DEFAULT_SCHEMA_VERSION,
    DEFAULT_WORKSPACE_NAME,
    AttributeDataType,
    AttributeType,
    DatabaseMode,
    Metadata,
    Options,
    Scenario,
    Workspace,
)
from movici_data_core.domain_model import ScenarioStatus, SimulationInfo
from movici_data_core.exceptions import DatabaseAlreadyInitialized, DatabaseNotYetInitialized


@contextlib.asynccontextmanager
async def get_engine(dbapi_url: str, **kwargs):
    engine = create_async_engine(dbapi_url, **kwargs)

    if "sqlite" in dbapi_url:
        # enable foreign keys for every sqlite connection
        @event.listens_for(engine.sync_engine, "engine_connect")
        def engine_connect(conn):
            with conn.begin():
                conn.execute(text("PRAGMA foreign_keys=ON"))

    yield engine
    await engine.dispose()


async def initialize_database(session: AsyncSession, mode: DatabaseMode):
    metadata_count = (await session.scalar(select(func.count(Metadata.id)))) or 0
    options_count = (await session.scalar(select(func.count(Options.id)))) or 0

    if metadata_count > 0 or options_count > 0:
        raise DatabaseAlreadyInitialized
    await session.execute(insert(Metadata).values(id=1, version=DEFAULT_SCHEMA_VERSION))

    workspace_id = None
    scenario_id = None
    if mode in (DatabaseMode.SINGLE_SCENARIO, DatabaseMode.SINGLE_WORKSPACE):
        workspaces_count = (await session.scalar(select(func.count(Options.id)))) or 0
        if workspaces_count > 0:
            raise DatabaseAlreadyInitialized

        workspace_id = await create_default_workspace(session)
        if mode == DatabaseMode.SINGLE_SCENARIO:
            scenario_id = await create_default_scenario(session, workspace_id)

    await session.execute(
        insert(Options).values(
            default_workspace_id=workspace_id,
            default_scenario_id=scenario_id,
            mode=mode,
            **_default_flags(mode),
        )
    )
    await create_default_attribute_types(session)


async def create_default_attribute_types(session: AsyncSession):
    default_attributes = [
        dict(
            name="id",
            has_rowptr=False,
            unit_type=AttributeDataType.INT,
            unit_shape=(),
            unit="",
            description="Entity ID",
        ),
        dict(
            name="geometry.x",
            has_rowptr=False,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(),
            unit="m",
            description="Point geometry x component",
        ),
        dict(
            name="geometry.y",
            has_rowptr=False,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(),
            unit="m",
            description="Point geometry y component",
        ),
        dict(
            name="geometry.linestring_2d",
            has_rowptr=True,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(2,),
            unit="m",
            description="2D linestring geometry",
        ),
        dict(
            name="geometry.linestring_3d",
            has_rowptr=True,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(3,),
            unit="m",
            description="3D linestring geometry",
        ),
        dict(
            name="geometry.polygon",
            has_rowptr=True,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(2,),
            unit="m",
            description="polygon geometry (2D)",
        ),
        dict(
            name="geometry.polygon_2d",
            has_rowptr=True,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(2,),
            unit="m",
            description="2D polygon geometry",
        ),
        dict(
            name="geometry.polygon_3d",
            has_rowptr=True,
            unit_type=AttributeDataType.FLOAT,
            unit_shape=(3,),
            unit="m",
            description="3D polygon geometry",
        ),
    ]
    await session.execute(
        insert(AttributeType), [{**attr, "protected": True} for attr in default_attributes]
    )


async def create_default_workspace(
    session: AsyncSession, name=DEFAULT_WORKSPACE_NAME, display_name=DEFAULT_WORKSPACE_NAME
) -> UUID:
    return t.cast(
        UUID,
        await session.scalar(
            insert(Workspace).returning(Workspace.id).values(name=name, display_name=display_name)
        ),
    )


async def create_default_scenario(
    session: AsyncSession,
    workspace_id: UUID,
    name=DEFAULT_SCENARIO_NAME,
    display_name=DEFAULT_SCENARIO_NAME,
) -> UUID:
    return t.cast(
        UUID,
        await session.scalar(
            insert(Scenario)
            .returning(Scenario.id)
            .values(
                workspace_id=workspace_id,
                name=name,
                display_name=display_name,
                description="",
                status=ScenarioStatus.READY,
                simulation_info=dataclasses.asdict(SimulationInfo.default()),
                epsg_code=0,
            )
        ),
    )


async def get_version(session: AsyncSession):
    metadata = await session.get(Metadata, 1)
    if not metadata:
        raise DatabaseNotYetInitialized
    return metadata.version


async def get_options(session: AsyncSession):
    options = await session.get(Options, 1, options=[joinedload(Options.default_workspace)])
    if not options:
        raise DatabaseNotYetInitialized
    return options


async def set_options(session: AsyncSession, **options):
    await session.execute(update(Options).values(**options))


def _default_flags(mode: DatabaseMode):
    """Return a dictionary of default flags that must be set (to true), based on the ``mode``"""
    if mode == DatabaseMode.MULTIPLE_WORKSPACES:
        return {
            "STRICT_ATTRIBUTE_TYPES": True,
            "STRICT_DATASET_TYPES": True,
            "STRICT_ENTITY_TYPES": True,
            "STRICT_MODEL_TYPES": True,
            "STRICT_SCENARIO_DATASETS": True,
        }
    return {
        "STRICT_ATTRIBUTE_TYPES": False,
        "STRICT_DATASET_TYPES": False,
        "STRICT_ENTITY_TYPES": False,
        "STRICT_MODEL_TYPES": False,
        "STRICT_SCENARIO_DATASETS": False,
    }
