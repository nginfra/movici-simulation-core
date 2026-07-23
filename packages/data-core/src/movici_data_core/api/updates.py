import typing as t
from uuid import UUID

from fastapi import APIRouter, Depends, Header, Request
from fastapi.responses import FileResponse

from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.file_helpers import (
    get_mimetype,
    infer_filetype_from_filename_or_mimetype,
    store_request_stream_to_disk,
)
from movici_data_core.marshalling import (
    OperationSuccess,
    UpdateListOut,
    UpdateWithDataOut,
)
from movici_simulation_core.types import FileType

from .dependencies import DepBackend, DepScenarioBackend

update_router = APIRouter(prefix="/updates")


def request_filetype(content_type: t.Annotated[str | None, Header()] = None) -> FileType:
    if not content_type:
        return FileType.JSON
    return infer_filetype_from_filename_or_mimetype(mimetype=content_type)


DepContentType = t.Annotated[FileType, Depends(request_filetype)]


@update_router.get("")
async def get_updates(backend: DepScenarioBackend) -> UpdateListOut:
    scenarios = await backend.updates.list()
    return UpdateListOut.from_domain(scenarios)


@update_router.post("")
async def create_update(
    backend: DepScenarioBackend, request: Request, filetype: DepContentType
) -> OperationSuccess:
    tempfile = await store_request_stream_to_disk(request, backend.tmpfile_dir, filetype=filetype)
    result = await backend.updates.store_update_from_file(tempfile, filetype)
    return OperationSuccess.for_path_operation(resource="update", id=result, verb="created")


@update_router.delete("")
async def delete_updates(backend: DepScenarioBackend) -> OperationSuccess:
    await backend.updates.delete_all()
    assert backend.scenario_id is not None
    return OperationSuccess.for_path_operation(
        resource="updates", id=backend.scenario_id, verb="deleted"
    )


@update_router.get("/{update_id}")
async def get_update(
    update_id: UUID, backend: DepBackend, filetype: DepContentType
) -> UpdateWithDataOut:
    path = await backend.updates.get_update_as_file(update_id=update_id, filetype=filetype)
    if path is None:
        raise ResourceDoesNotExist("update", id=update_id)

    return t.cast(UpdateWithDataOut, FileResponse(path, media_type=get_mimetype(filetype)))
