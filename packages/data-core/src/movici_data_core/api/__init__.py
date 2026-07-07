from __future__ import annotations

import asyncio
import contextlib
import logging
import pathlib
import tempfile
import typing as t

import fastapi
from fastapi import APIRouter, FastAPI, Request

from movici_data_core.api.dependencies import SQLALCHEMY_SERVER_KEY
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.exceptions import MoviciDataError

from .datasets import dataset_router
from .scenarios import scenario_router
from .schema import (
    attribute_type_router,
    dataset_type_router,
    entity_type_router,
    model_type_router,
)
from .updates import update_router
from .workspaces import workspace_router

DEFAULT_ROUTERS = (
    attribute_type_router,
    dataset_router,
    dataset_type_router,
    entity_type_router,
    model_type_router,
    workspace_router,
    update_router,
    scenario_router,
)

logger = logging.getLogger(__name__)


def make_app(
    server: SQLAlchemyServer,
    routers: t.Iterable[APIRouter] | None = None,
    log_movici_data_errors=False,
):
    routers = routers if routers is not None else DEFAULT_ROUTERS

    @contextlib.asynccontextmanager
    async def lifespan(app_: FastAPI):
        async with server.begin():
            yield {SQLALCHEMY_SERVER_KEY: server}

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(MoviciDataError)
    async def movici_data_error_handler(request: Request, exc: MoviciDataError):
        if log_movici_data_errors:
            logger.exception("An error occured")
        return fastapi.responses.JSONResponse(
            {
                "result": "error",
                "message": exc.__error_message__,
                "type": exc.__error_id__,
                **(exc.payload() or {}),
            },
            status_code=exc.__status_code__,
        )

    for router in routers:
        app.include_router(router)
    return app


def make_default_app():
    tmpfile_path = pathlib.Path(tempfile.mkdtemp(prefix="movici_api_tmp_"))

    db_path = pathlib.Path("movici.db`")
    dbapi_url = f"sqlite+aiosqlite:///{db_path}"
    server = SQLAlchemyServer(dbapi_url, tmpfile_dir=tmpfile_path)
    if not db_path.exists():

        async def setup():
            async with server.begin():
                await server.setup_db()

        asyncio.run(setup())
    return make_app(server)


if __name__ == "__main__":
    logging.basicConfig()
    app = make_default_app()
