import asyncio
import contextlib
import functools
import os
import pathlib
import shutil
import tempfile
import typing as t
from concurrent.futures import ThreadPoolExecutor

from fastapi import Request

from movici_simulation_core.types import FileType

executor = ThreadPoolExecutor(max_workers=10)


@contextlib.contextmanager
def tempfile_delete_on_error(mode="w+b", suffix=None, prefix=None, dir=None):
    file = None
    try:
        with tempfile.NamedTemporaryFile(
            mode=mode, suffix=suffix, prefix=prefix, dir=dir, delete=False
        ) as file:
            yield file
    except Exception:
        try:
            if file is not None:
                os.unlink(file.name)
        except OSError:
            pass
        raise


async def store_file_to_disk(
    source_file: t.BinaryIO, path: pathlib.Path, filetype: FileType, prefix: str = ""
) -> pathlib.Path:
    if not path.is_dir():
        raise ValueError("path must be an existing directory")

    def _store_to_disk():
        with tempfile_delete_on_error(
            suffix=filetype.default_extension, prefix=prefix, dir=path
        ) as destination_file:
            shutil.copyfileobj(source_file, destination_file)
        return pathlib.Path(destination_file.name)

    loop = asyncio.get_running_loop()
    return await loop.run_in_executor(executor, _store_to_disk)


async def store_request_stream_to_disk(
    request: Request, path: pathlib.Path, filetype: FileType, prefix: str = ""
):
    """Asynchronously store a raw request body to disk."""
    if not path.is_dir():
        raise ValueError("path must be an existing directory")

    loop = asyncio.get_running_loop()
    with tempfile_delete_on_error(
        suffix=filetype.default_extension, prefix=prefix, dir=path
    ) as destination_file:
        async for chunk in request.stream():
            await loop.run_in_executor(executor, functools.partial(destination_file.write, chunk))
        return pathlib.Path(destination_file.name)


MIMETYPES = {
    "application/json": FileType.JSON,
    "application/x-msgpack": FileType.MSGPACK,
    "application/msgpack": FileType.MSGPACK,
    "application/x-netcdf": FileType.NETCDF,
    "application/netcdf": FileType.NETCDF,
    "text/csv": FileType.CSV,
}

MIMETYPES_BY_FILETYPE = {
    FileType.JSON: "application/json",
    FileType.MSGPACK: "application/x-msgpack",
    FileType.NETCDF: "application/x-netcdf",
    FileType.CSV: "text/csv",
}


def base_mimetype(content_type: str | None):
    return content_type.split(";")[0].strip() if content_type is not None else None


def infer_filetype_from_filename_or_mimetype(
    filename: str | None = None, mimetype: str | None = None
) -> FileType:
    filename = filename or ""
    mimetype = base_mimetype(mimetype) or ""
    return MIMETYPES.get(mimetype or "", FileType.from_extension(pathlib.Path(filename).suffix))


def get_mimetype(filetype: FileType) -> str | None:
    return MIMETYPES_BY_FILETYPE.get(filetype)
