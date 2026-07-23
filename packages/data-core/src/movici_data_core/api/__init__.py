from __future__ import annotations

import contextlib
import logging
import pathlib
import tempfile
import typing as t
from urllib.parse import urlsplit

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


async def ensure_sqlite_db_exists(server: SQLAlchemyServer):
    """if the ``server`` argument is configured against a sqlite database, ensure that this
    database exists and is propertly initialized. If it is not configured against a sqlite database
    or if the database already exists, this function does nothing. This method must be called with
    the context of ``server.begin()``

    :param server: the ``SQLAlchemyServer`` instance.
    """
    urlsplit_result = urlsplit(server.dbapi_url)
    if not urlsplit_result.scheme.startswith("sqlite"):
        # not a sqlite url
        return
    if not urlsplit_result.path.startswith("/"):
        # in memory db or not a proper dbapi_url
        return
    path = pathlib.Path(urlsplit_result.path.removeprefix("/"))
    if not path.exists():
        await server.setup_db()


def make_app(
    server: SQLAlchemyServer,
    routers: t.Iterable[APIRouter] | None = None,
    log_movici_data_errors=False,
):
    routers = routers if routers is not None else DEFAULT_ROUTERS

    @contextlib.asynccontextmanager
    async def lifespan(app_: FastAPI):
        async with server.begin():
            await ensure_sqlite_db_exists(server)
            yield {SQLALCHEMY_SERVER_KEY: server}

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(MoviciDataError)
    async def movici_data_error_handler(request: Request, exc: MoviciDataError):
        if log_movici_data_errors:
            logger.exception("An error occurred")
        return fastapi.responses.JSONResponse(
            {
                "result": "error",
                "message": exc.__error_message__,
                "type": exc.__error_id__,
                **(exc.payload() or {}),
            },
            status_code=exc.__status_code__,
        )

    @app.exception_handler(500)
    async def handle_server_errors(request: Request, exc: Exception):
        return fastapi.responses.JSONResponse(
            {
                "result": "error",
                "type": "generic_error",
                "message": "An unknown server error occured",
            },
            status_code=500,
        )

    for router in routers:
        app.include_router(router)
    return app


def make_default_app():
    tmpfile_path = pathlib.Path(tempfile.mkdtemp(prefix="movici_api_tmp_"))

    db_path = pathlib.Path("movici.db")
    dbapi_url = f"sqlite+aiosqlite:///{db_path}"
    server = SQLAlchemyServer(dbapi_url, tmpfile_dir=tmpfile_path)
    return make_app(server)
