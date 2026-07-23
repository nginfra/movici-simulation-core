from uuid import UUID

from fastapi import APIRouter

from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.marshalling import (
    OperationSuccess,
    WorkspaceIn,
    WorkspaceListOut,
    WorkspaceOut,
)

from .dependencies import DepBackend, allow_in_modes

workspace_router = APIRouter(
    prefix="/workspaces",
    dependencies=[allow_in_modes("workspace operation", [DatabaseMode.MULTIPLE_WORKSPACES])],
)


@workspace_router.get("")
async def list_workspaces(backend: DepBackend) -> WorkspaceListOut:
    workspace = await backend.workspaces.list()
    return WorkspaceListOut.from_domain(workspace)


@workspace_router.post("")
async def create_workspace(payload: WorkspaceIn, backend: DepBackend) -> OperationSuccess:
    workspace_id = await backend.workspaces.create(payload.to_domain())
    return OperationSuccess.for_path_operation(
        resource="workspace", id=workspace_id, verb="created"
    )


@workspace_router.get("/{workspace_id}")
async def get_workspace(workspace_id: UUID, backend: DepBackend) -> WorkspaceOut:
    workspace = await backend.workspaces.get_with_counts(id=workspace_id)
    if workspace is None:
        raise ResourceDoesNotExist("workspace", id=workspace_id)
    return WorkspaceOut.from_domain(workspace)


@workspace_router.put("/{workspace_id}")
async def update_workspace(
    workspace_id: UUID, payload: WorkspaceIn, backend: DepBackend
) -> OperationSuccess:
    await backend.workspaces.update(workspace_id, payload.to_domain())
    return OperationSuccess.for_path_operation(
        resource="workspace", id=workspace_id, verb="updated"
    )


@workspace_router.delete("/{workspace_id}")
async def delete_workspace(workspace_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.workspaces.delete(id=workspace_id)
    return OperationSuccess.for_path_operation(
        resource="workspace", id=workspace_id, verb="deleted"
    )
