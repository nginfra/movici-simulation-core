import pytest
from movici_data_core.database import model as db_model
from movici_data_core.database.general import get_options, initialize_database
from movici_data_core.database.model import Base, DatabaseMode
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.domain_model import (
    AttributeType,
    Dataset,
    DatasetFormat,
    DatasetType,
    EntityType,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from movici_simulation_core.core import DataType


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.fixture
def session_factory(db):
    return async_sessionmaker(db)


@pytest.fixture
async def initialized_db(session_factory, database_mode):
    async with session_factory() as session:
        await initialize_database(session, mode=database_mode)
        await session.commit()


@pytest.fixture
async def session(session_factory, initialized_db):
    async with session_factory() as session:
        yield session


@pytest.fixture
async def repository(session):
    options = await get_options(session)
    return SQLAlchemyRepository(session, options)


@pytest.fixture
async def a_workspace(session: AsyncSession):
    workspace = db_model.Workspace(name="default", display_name="Default Workspace")
    session.add(workspace)
    await session.flush()
    return workspace.to_domain()


@pytest.fixture
async def a_dataset_type(repository: SQLAlchemyRepository):
    return await repository.dataset_types.create(
        DatasetType(name="transport_network", format=DatasetFormat.ENTITY_BASED)
    )


@pytest.fixture
async def an_entity_type(repository: SQLAlchemyRepository):
    return await repository.entity_types.create(EntityType("roads"))


@pytest.fixture
async def an_attribute_type(repository: SQLAlchemyRepository):
    return await repository.attribute_types.create(
        AttributeType(
            name="some.attribute",
            data_type=DataType(float),
            unit="m/s",
            description="a description",
        )
    )


@pytest.fixture
async def a_dataset(repository: SQLAlchemyRepository, a_workspace, a_dataset_type):
    return await repository.datasets.create(
        a_workspace.id,
        Dataset(
            name="a_transport_network",
            display_name="A Transport Network",
            dataset_type=a_dataset_type,
        ),
    )
