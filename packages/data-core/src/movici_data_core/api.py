from __future__ import annotations

import dataclasses
import typing as t
from uuid import UUID

import fastapi
import svcs
from fastapi import APIRouter, Depends, FastAPI, Query, Request
from svcs.fastapi import DepContainer

from movici_data_core import domain_model
from movici_data_core.api_model import (
    ResourceSuccess,
    ShortDatasetIn,
    ShortDatasetOut,
    api_model_from_domain,
    api_model_from_domain_many,
)
from movici_data_core.database.backend import SQLAlchemyBackend, SQLAlchemyServer
from movici_data_core.exceptions import InvalidAction, MoviciDataError, ResourceDoesNotExist

DB_API_URL = "sqlite+aiosqlite:///:memory:"


@dataclasses.dataclass
class ServerParams:
    db_api_url: str


async def get_backend(container: DepContainer, workspace: t.Annotated[str | None, Query()] = None):
    factory = container.get(SQLAlchemyServer)
    async with factory.get_backend() as backend:
        if backend.single_workspace_mode:
            yield backend
            return

        if workspace is None:
            raise InvalidAction("supply a workspace id")
        workspace_id = await backend.workspaces.ensure_valid_id(workspace)

        yield backend.for_workspace(t.cast(UUID, workspace_id))


DepBackend = t.Annotated[SQLAlchemyBackend, Depends(get_backend)]
DepDatasetIn = t.Annotated[domain_model.Dataset, Depends(ShortDatasetIn.to_domain)]


dataset_router = fastapi.APIRouter(prefix="/datasets")


@dataset_router.get("/")
async def get_datasets(backend: DepBackend):
    datasets = await backend.datasets.list()
    return api_model_from_domain_many(ShortDatasetOut, datasets)


@dataset_router.post("/")
async def create_dataset(dataset: DepDatasetIn, backend: DepBackend):
    result = await backend.datasets.create(dataset)
    return ResourceSuccess(resource="dataset", id=result, verb="created")


@dataset_router.get("/{dataset_id}")
async def get_dataset(dataset_id: UUID, backend: DepBackend):
    dataset = await backend.datasets.get(id=dataset_id)
    if dataset is None:
        raise ResourceDoesNotExist("dataset", id=dataset_id)
    return api_model_from_domain(ShortDatasetOut, dataset)


@dataset_router.put("/{dataset_id}")
async def update_dataset(dataset_id: UUID, dataset: DepDatasetIn, backend: DepBackend):
    await backend.datasets.update(dataset_id, dataset)
    return ResourceSuccess(resource="dataset", id=dataset_id, verb="updated")


@dataset_router.get("/{dataset_id}/data")
async def get_dataset_data(dataset_id: UUID, backend: DepBackend):
    await backend.datasets.get_dataset_as_file(dataset_id)


DEFAULT_ROUTERS = (dataset_router,)


class MoviciWebApiBuilder:
    def make_app(self):
        pass

    @staticmethod
    async def movici_data_error_handler(request: Request, exc: MoviciDataError):
        return fastapi.responses.JSONResponse(
            {
                "result": "error",
                "status": exc.__status_code__,
                "message": exc.__error_message__,
                "type": exc.__error_id__,
                **(exc.payload() or {}),
            },
            status_code=exc.__status_code__,
        )


def make_app(server: SQLAlchemyServer, routers: t.Iterable[APIRouter] | None = None):
    routers = routers if routers is not None else DEFAULT_ROUTERS

    @svcs.fastapi.lifespan  # type: ignore
    async def lifespan(app_: FastAPI, registry: svcs.Registry):
        async with server.begin():
            await server.setup_db()
            registry.register_value(SQLAlchemyServer, server)
            yield

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(MoviciDataError)
    async def movici_data_error_handler(request: Request, exc: MoviciDataError):
        return fastapi.responses.JSONResponse(
            {
                "result": "error",
                "status": exc.__status_code__,
                "message": exc.__error_message__,
                "type": exc.__error_id__,
                **(exc.payload() or {}),
            },
            status_code=exc.__status_code__,
        )

    for router in routers:
        app.include_router(router)
    return app


app = make_app(SQLAlchemyServer(DB_API_URL))
