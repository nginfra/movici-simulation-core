import typing as t

import pytest
from fastapi.testclient import TestClient

from movici_data_core.api import make_app
from movici_data_core.database.backend import SQLAlchemyServer


@pytest.fixture
async def app(db: SQLAlchemyServer):
    return make_app(db, log_movici_data_errors=True)


@pytest.fixture
def client(app):
    with TestClient(app) as client:
        yield client


@pytest.fixture
def get_json(client: TestClient):
    def _get_json(
        path: str,
        method: str = "get",
        json: t.Any = None,
        expected_status: int | None = None,
        **kwargs,
    ):
        result = client.request(method, url=path, json=json, **kwargs)
        json_response = result.json()
        print(f"got response: {json_response}")  # noqa: T201
        if expected_status is not None:
            assert result.status_code == expected_status
        return result.json()

    return _get_json


@pytest.fixture
def create_scenario_json():
    def _create_scenario(**kwargs):
        defaults = {
            "name": "new_scenario",
            "display_name": "New Scenario",
            "simulation_info": {
                "mode": "time_oriented",
                "reference": 1,
                "start_time": 0,
                "duration": 12,
                "time_scale": 1.4,
            },
            "models": [],
            "datasets": [],
        }
        return {**defaults, **kwargs}

    return _create_scenario


@pytest.fixture
def create_scenario_through_api(get_json, a_workspace, create_scenario_json):
    def _create_scenario(**kwargs):
        return get_json(
            "/scenarios",
            params={"workspace": a_workspace.id},
            method="post",
            json=create_scenario_json(**kwargs),
        )

    return _create_scenario
