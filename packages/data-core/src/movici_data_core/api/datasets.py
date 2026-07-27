import os
import typing as t
from uuid import UUID

import fastapi
from fastapi.responses import FileResponse
from starlette.background import BackgroundTask

from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.file_helpers import (
    base_mimetype,
    infer_filetype_from_filename_or_mimetype,
    store_file_to_disk,
)
from movici_data_core.marshalling import (
    DatasetFilterIn,
    DatasetListOut,
    DatasetSummaryOut,
    DatasetWithDataOut,
    OperationSuccess,
    ShortDatasetIn,
    ShortDatasetOut,
)

from .dependencies import DepBackend, DepWorkspaceBackend

dataset_router = fastapi.APIRouter(prefix="/datasets")


@dataset_router.get("")
async def get_datasets(backend: DepWorkspaceBackend) -> DatasetListOut:
    datasets = await backend.datasets.list()
    return DatasetListOut.from_domain(datasets)


@dataset_router.post("")
async def create_dataset(
    dataset: ShortDatasetIn, backend: DepWorkspaceBackend
) -> OperationSuccess:
    result = await backend.datasets.create(dataset.to_domain())
    return OperationSuccess.for_path_operation(resource="dataset", id=result, verb="created")


@dataset_router.get("/{dataset_id}")
async def get_dataset(dataset_id: UUID, backend: DepBackend) -> ShortDatasetOut:
    dataset = await backend.datasets.get(id=dataset_id)
    if dataset is None:
        raise ResourceDoesNotExist("dataset", id=dataset_id)
    return ShortDatasetOut.from_domain(dataset)


@dataset_router.put("/{dataset_id}")
async def update_dataset(
    dataset_id: UUID, dataset: ShortDatasetIn, backend: DepBackend
) -> OperationSuccess:
    await backend.datasets.update(dataset_id, dataset.to_domain())
    return OperationSuccess.for_path_operation(resource="dataset", id=dataset_id, verb="updated")


@dataset_router.delete("/{dataset_id}")
async def delete_dataset(dataset_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.datasets.delete(dataset_id)
    return OperationSuccess.for_path_operation(resource="dataset", id=dataset_id, verb="deleted")


@dataset_router.get(
    "/{dataset_id}/data",
    responses={
        200: {
            "content": {
                "application/octet-stream": {
                    "schema": {
                        "type": "string",
                        "format": "binary",
                    }
                },
            }
        }
    },
)
async def get_dataset_data(
    dataset_id: UUID,
    backend: DepBackend,
    dataset_filter: t.Annotated[DatasetFilterIn, fastapi.Query()],
    background_tasks: fastapi.BackgroundTasks
):
    # TODO: use accept header to serve msgpack or json

    result = await backend.datasets.get_dataset_as_file(
        dataset_id, dataset_filter=dataset_filter.to_domain()
    )
    if result is None:
        raise ResourceDoesNotExist("dataset", id=dataset_id)
    background_tasks.add_task(os.remove, result)
    return t.cast(
        DatasetWithDataOut, FileResponse(result, background=BackgroundTask(os.remove, result))
    )


@dataset_router.post("/{dataset_id}/data")
async def create_dataset_data(
    dataset_id: UUID,
    data: fastapi.UploadFile,
    backend: DepBackend,
    background_tasks: fastapi.BackgroundTasks,
) -> OperationSuccess:
    if not await backend.datasets.get(id=dataset_id):
        # We also check this in the DatasetService, but we short circuit here to prevent additional
        # work with handling the incoming file
        raise ResourceDoesNotExist("dataset", id=dataset_id)

    mimetype = base_mimetype(data.content_type)
    filetype = infer_filetype_from_filename_or_mimetype(data.filename, mimetype)
    filepath = await store_file_to_disk(data.file, backend.tmpfile_dir, filetype)
    background_tasks.add_task(os.remove, filepath)
    await backend.datasets.update_from_file(dataset_id, filepath, mimetype)
    return OperationSuccess.for_path_operation(
        resource="dataset", id=dataset_id, verb="data created"
    )


@dataset_router.delete("/{dataset_id}/data")
async def delete_dataset_data(dataset_id: UUID, backend: DepBackend) -> OperationSuccess:
    await backend.datasets.prune(dataset_id)
    return OperationSuccess.for_path_operation(
        resource="dataset", id=dataset_id, verb="data deleted"
    )


@dataset_router.get("/{dataset_id}/summary")
async def get_summary(dataset_id: UUID, backend: DepBackend) -> DatasetSummaryOut:
    result = await backend.datasets.get_summary(dataset_id)
    return DatasetSummaryOut.from_domain(result)
