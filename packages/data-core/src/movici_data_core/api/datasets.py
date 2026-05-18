from uuid import UUID

import fastapi
from fastapi.responses import FileResponse

from movici_data_core.exceptions import ResourceDoesNotExist
from movici_data_core.schema import DatasetList, OperationSuccess, ShortDatasetIn, ShortDatasetOut

from .dependencies import DepWorkspaceBackend

dataset_router = fastapi.APIRouter(prefix="/datasets")


@dataset_router.get("/")
async def get_datasets(backend: DepWorkspaceBackend) -> DatasetList:
    datasets = await backend.datasets.list()
    return DatasetList.from_domain(datasets)


@dataset_router.post("/")
async def create_dataset(
    dataset: ShortDatasetIn, backend: DepWorkspaceBackend
) -> OperationSuccess:
    result = await backend.datasets.create(dataset.to_domain())
    return OperationSuccess(resource="dataset", id=result, verb="created")


@dataset_router.get("/{dataset_id}")
async def get_dataset(dataset_id: UUID, backend: DepWorkspaceBackend) -> ShortDatasetOut:
    dataset = await backend.datasets.get(id=dataset_id)
    if dataset is None:
        raise ResourceDoesNotExist("dataset", id=dataset_id)
    return ShortDatasetOut.from_domain(dataset)


@dataset_router.put("/{dataset_id}")
async def update_dataset(
    dataset_id: UUID, dataset: ShortDatasetIn, backend: DepWorkspaceBackend
) -> OperationSuccess:
    await backend.datasets.update(dataset_id, dataset.to_domain())
    return OperationSuccess(resource="dataset", id=dataset_id, verb="updated")


@dataset_router.get("/{dataset_id}/data")
async def get_dataset_data(dataset_id: UUID, backend: DepWorkspaceBackend):
    result = await backend.datasets.get_dataset_as_file(dataset_id)
    return FileResponse(
        result,
    )
