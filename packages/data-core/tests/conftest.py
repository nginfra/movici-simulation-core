import pytest
from movici_data_core.database.model import Base, Workspace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest.fixture
async def session(db):
    create_session = async_sessionmaker(db)
    async with create_session() as session:
        yield session


@pytest.fixture
async def a_workspace(session: AsyncSession):
    workspace = Workspace(name="default", display_name="Default Workspace")
    session.add(workspace)
    await session.flush()
    return workspace
