import asyncio
import contextlib
import os
import pathlib
import shutil
import tempfile
import typing as t
from concurrent.futures import ThreadPoolExecutor

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


MIMETYPES = {
    "application/json": FileType.JSON,
    "application/x-msgpack": FileType.MSGPACK,
    "application/msgpack": FileType.MSGPACK,
    "application/x-netcdf": FileType.NETCDF,
    "application/netcdf": FileType.NETCDF,
    "text/csv": FileType.CSV,
}


def infer_filetype_from_mimetype_or_suffix(filename: str, mimetype: str | None = None):
    return MIMETYPES.get(mimetype or "", FileType.from_extension(pathlib.Path(filename).suffix))
