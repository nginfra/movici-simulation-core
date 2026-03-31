import pytest
from movici_data_core.database.model import Base, DatabaseMode, Workspace
from movici_data_core.database.repository import SQLAlchemyRepository
from movici_data_core.general import get_options, initialize_database
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
def database_mode():
    return DatabaseMode.MULTIPLE_WORKSPACES


@pytest.fixture
async def session(db):
    create_session = async_sessionmaker(db)
    async with create_session() as session:
        yield session


@pytest.fixture
async def initialized_db(session, database_mode):
    return await initialize_database(session, mode=database_mode)


@pytest.fixture
async def repository(session, initialized_db):
    options = await get_options(session)
    return SQLAlchemyRepository(session, options)


@pytest.fixture
async def a_workspace(session: AsyncSession):
    workspace = Workspace(name="default", display_name="Default Workspace")
    session.add(workspace)
    await session.flush()
    return workspace
