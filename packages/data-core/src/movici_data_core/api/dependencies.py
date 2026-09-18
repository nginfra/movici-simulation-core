from __future__ import annotations

import typing as t

from fastapi import Depends, Query, Request

from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyServer
from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import InvalidAction
from movici_data_core.services.common import ensure_valid_scenario, ensure_valid_workspace

SQLALCHEMY_SERVER_KEY = "__movici_sqlalchemy_server__"


def server(request: Request) -> SQLAlchemyServer:
    return getattr(request.state, SQLALCHEMY_SERVER_KEY)


async def get_backend(server: DepServer):
    async with server.get_backend() as backend:
        yield backend


async def get_workspace_backend(
    backend: DepBackend, workspace_q: t.Annotated[str | None, Query(alias="workspace")] = None
):
    if backend.single_workspace_mode:
        return backend

    # TODO: Validate authorization
    workspace = await ensure_valid_workspace(workspace_q, repository=backend.repository)

    assert workspace.id is not None
    return backend.for_workspace(workspace.id)


async def get_scenario_backend(
    backend: DepBackend,
    scenario_q: t.Annotated[str | None, Query(alias="scenario")] = None,
    workspace_q: t.Annotated[str | None, Query(alias="workspace")] = None,
):
    if backend.single_scenario_mode:
        return backend

    if not scenario_q:
        raise InvalidAction("supply a scenario name or id")

    scenario = await ensure_valid_scenario(scenario_q, workspace_q, backend.repository)

    assert scenario.id is not None
    return backend.for_scenario(scenario.id)


def allow_in_modes(operation: str, modes: t.Sequence[DatabaseMode]):
    def _disallow(backend: DepBackend):
        if backend.options.mode not in modes:
            raise InvalidAction(f"{operation} is not allowed in this mode")

    return Depends(_disallow)


DepServer = t.Annotated[SQLAlchemyServer, Depends(server)]
DepBackend = t.Annotated[SQLAlchemyBackend, Depends(get_backend, scope="function")]
DepWorkspaceBackend = t.Annotated[
    SQLAlchemyBackend, Depends(get_workspace_backend, scope="function")
]
DepScenarioBackend = t.Annotated[
    SQLAlchemyBackend, Depends(get_scenario_backend, scope="function")
]
