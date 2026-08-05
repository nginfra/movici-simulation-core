import os
import typing as t
from uuid import UUID

import fastapi
from fastapi import APIRouter, BackgroundTasks, Request
from fastapi.responses import FileResponse

from movici_data_core.database.model import to_domain_or_none
from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.file_helpers import (
    get_mimetype,
    store_request_stream_to_disk,
)
from movici_data_core.marshalling import (
    DatasetFilterIn,
    OperationSuccess,
    UpdateListOut,
    UpdateWithDataOut,
)
from movici_simulation_core.types import FileType

from .dependencies import DepBackend, DepContentType, DepScenarioBackend

update_router = APIRouter(prefix="/updates")


@update_router.get("")
async def get_updates(backend: DepScenarioBackend) -> UpdateListOut:
    scenarios = await backend.updates.list()
    return UpdateListOut.from_domain(scenarios)


@update_router.post("")
async def create_update(
    backend: DepScenarioBackend,
    request: Request,
    filetype: DepContentType,
    background_tasks: BackgroundTasks,
) -> OperationSuccess:
    tempfile = await store_request_stream_to_disk(request, backend.tmpfile_dir, filetype=filetype)
    background_tasks.add_task(os.remove, tempfile)
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
    update_id: UUID,
    backend: DepBackend,
    background_tasks: BackgroundTasks,
    dataset_filter: t.Annotated[DatasetFilterIn, fastapi.Query()] | None = None,
) -> UpdateWithDataOut:
    response_filetype = FileType.JSON
    path = await backend.updates.get_update_as_file(
        update_id=update_id,
        filetype=response_filetype,
        dataset_filter=to_domain_or_none(dataset_filter),
    )
    if path is None:
        raise ResourceDoesNotExist("update", id=update_id)

    background_tasks.add_task(os.remove, path)
    return t.cast(
        UpdateWithDataOut, FileResponse(path, media_type=get_mimetype(response_filetype))
    )
