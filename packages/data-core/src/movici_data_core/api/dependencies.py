from __future__ import annotations

import typing as t

from fastapi import Depends, Query
from svcs.fastapi import DepContainer

from movici_data_core import domain_model
from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyServer
from movici_data_core.exceptions import InvalidAction


async def get_backend(container: DepContainer):
    factory = container.get(SQLAlchemyServer)
    async with factory.get_backend() as backend:
        yield backend


async def valid_workspace_or_none(
    backend: DepBackend, workspace_q: t.Annotated[str | None, Query(alias="workspace")] = None
):
    if workspace_q is None:
        return None

    return await backend.workspaces.ensure_valid_workspace(workspace_q)


async def get_workspace_backend(backend: DepBackend, workspace: DepWorkspaceOrNone):
    if backend.single_workspace_mode:
        yield backend
        return

    if workspace is None:
        raise InvalidAction("supply a workspace name or id")

    assert workspace.id is not None
    yield backend.for_workspace(workspace.id)


DepBackend = t.Annotated[SQLAlchemyBackend, Depends(get_backend)]
DepWorkspaceOrNone = t.Annotated[domain_model.Workspace | None, Depends(valid_workspace_or_none)]
DepWorkspaceBackend = t.Annotated[SQLAlchemyBackend, Depends(get_workspace_backend)]
