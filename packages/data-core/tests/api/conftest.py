import typing as t

import pytest
from fastapi.testclient import TestClient

from movici_data_core.api import make_app
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.database.general import initialize_database
from movici_data_core.database.model import DatabaseMode


@pytest.fixture
def dbapi_url(tmp_path_factory):
    tmp_path = tmp_path_factory.mktemp("db") / "db.sqlite"
    return f"sqlite+aiosqlite:///{tmp_path}"


@pytest.fixture
async def app(database_server: SQLAlchemyServer):
    async with database_server.get_session() as session:
        await initialize_database(session, mode=DatabaseMode.MULTIPLE_WORKSPACES)
        await session.commit()
    return make_app(database_server)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def get_json(client: TestClient):
    def _get_json(path: str, method: str = "get", json: t.Any = None, expected_status: int = 200):
        result = client.request(method, url=path, json=json)
        json_response = result.json()
        print(f"got response: {json_response}")  # noqa: T201
        if result.status_code != expected_status:
            assert result.status_code == expected_status
        return result.json()

    return _get_json
