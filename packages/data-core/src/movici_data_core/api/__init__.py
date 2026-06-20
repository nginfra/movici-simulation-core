from __future__ import annotations

import asyncio
import contextlib
import logging
import pathlib
import typing as t

import fastapi
from fastapi import APIRouter, FastAPI, Request

from movici_data_core.api.dependencies import SQLALCHEMY_SERVER_KEY
from movici_data_core.database.backend import SQLAlchemyServer
from movici_data_core.database.model import DatabaseMode
from movici_data_core.exceptions import MoviciDataError

from .datasets import dataset_router
from .workspaces import workspace_router

# TODO: make this part of MoviciWebApiBuilder (or similar builder/factory class)
SQLITE_DB_FILE = "movici.db"
DBAPI_URL = f"sqlite+aiosqlite:///{SQLITE_DB_FILE}"
TMPFILE_DIR = "tmp"

DATABASE_MODE = DatabaseMode.SINGLE_SCENARIO
DEFAULT_ROUTERS = (
    dataset_router,
    workspace_router,
)
logger = logging.getLogger(__name__)
logging.basicConfig()


def make_app(server: SQLAlchemyServer, routers: t.Iterable[APIRouter] | None = None):
    routers = routers if routers is not None else DEFAULT_ROUTERS

    @contextlib.asynccontextmanager
    async def lifespan(app_: FastAPI):
        async with server.begin():
            yield {SQLALCHEMY_SERVER_KEY: server}

    app = FastAPI(lifespan=lifespan)

    @app.exception_handler(MoviciDataError)
    async def movici_data_error_handler(request: Request, exc: MoviciDataError):
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
    tmpfile_path = pathlib.Path(TMPFILE_DIR)
    tmpfile_path.mkdir(parents=True, exist_ok=True)

    db_path = pathlib.Path(SQLITE_DB_FILE)
    server = SQLAlchemyServer(DBAPI_URL, tmpfile_dir=tmpfile_path)
    if not db_path.exists():

        async def setup():
            async with server.begin():
                await server.setup_db()

        asyncio.run(setup())
    return make_app(server)


app = make_default_app()
