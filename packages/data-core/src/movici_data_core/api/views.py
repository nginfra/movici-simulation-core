from uuid import UUID

from fastapi import APIRouter

from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.marshalling import (
    OperationSuccess,
    ViewIn,
    ViewListOut,
    ViewOut,
)

from .dependencies import DepBackend, DepScenarioBackend

view_router = APIRouter(prefix="/views")


@view_router.get("")
async def list_views(backend: DepScenarioBackend) -> ViewListOut:
    view = await backend.views.list()
    return ViewListOut.from_domain(view)


@view_router.post("")
async def create_view(payload: ViewIn, backend: DepScenarioBackend) -> OperationSuccess:
    view_id = await backend.views.create(payload.to_domain())
    return OperationSuccess.for_path_operation(resource="view", id=view_id, verb="created")


@view_router.get("/{view_id}")
async def get_view(view_id: UUID, backend: DepBackend) -> ViewOut:
    view = await backend.views.get(id=view_id)
    if view is None:
        raise ResourceDoesNotExist("view", id=view_id)
    return ViewOut.from_domain(view)


@view_router.put("/{view_id}")
async def update_view(view_id: UUID, payload: ViewIn, backend: DepBackend) -> OperationSuccess:
    await backend.views.update(view_id, payload.to_domain())
    return OperationSuccess.for_path_operation(resource="view", id=view_id, verb="updated")


@view_router.delete("/{view_id}")
async def delete_view(view_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.views.delete(id=view_id)
    return OperationSuccess.for_path_operation(resource="view", id=view_id, verb="deleted")
