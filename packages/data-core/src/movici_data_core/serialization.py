import typing as t

import msgpack
import orjson

from movici_data_core.exceptions import SerializationError, UnsupportedFileType
from movici_simulation_core.types import FileType


def load_dict(data: bytes, filetype: FileType) -> dict:
    try:
        if filetype == FileType.JSON:
            return t.cast(dict, orjson.loads(data))
        if filetype == FileType.MSGPACK:
            return t.cast(dict, msgpack.unpackb(data))
    except (OSError, ValueError) as e:
        raise SerializationError from e
    raise UnsupportedFileType(filetype)


def dump_dict(data: dict, filetype: FileType) -> bytes:
    if filetype == FileType.JSON:
        return orjson.dumps(data)
    if filetype == FileType.MSGPACK:
        return t.cast(bytes, msgpack.packb(data))

    raise UnsupportedFileType(filetype)
