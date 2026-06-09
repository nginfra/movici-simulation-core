import pytest

from movici_data_core.database.backend import SQLAlchemyServer


@pytest.fixture
async def backend(initialized_db: SQLAlchemyServer):
    async with initialized_db.get_backend() as backend:
        yield backend
