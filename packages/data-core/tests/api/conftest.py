import typing as t

import pytest
from fastapi.testclient import TestClient

from movici_data_core.api import make_app
from movici_data_core.database.backend import SQLAlchemyServer


@pytest.fixture
async def app(db: SQLAlchemyServer):
    return make_app(db)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def get_json(client: TestClient):
    def _get_json(
        path: str, method: str = "get", json: t.Any = None, expected_status: int = 200, **kwargs
    ):
        result = client.request(method, url=path, json=json, **kwargs)
        json_response = result.json()
        print(f"got response: {json_response}")  # noqa: T201
        if result.status_code != expected_status:
            assert result.status_code == expected_status
        return result.json()

    return _get_json
