import pytest_asyncio
from movici_data_core.model import Base, Workspace
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine


@pytest_asyncio.fixture
async def db():
    engine = create_async_engine("sqlite+aiosqlite://", echo=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return engine


@pytest_asyncio.fixture
async def session(db):
    create_session = async_sessionmaker(db)
    async with create_session() as session:
        yield session


@pytest_asyncio.fixture
async def default_workspace(session: AsyncSession):
    workspace = Workspace(name="default", display_name="Default Workspace")
    session.add(workspace)
    await session.flush()
    return workspace
