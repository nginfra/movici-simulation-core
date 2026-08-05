import pathlib
import typing as t

import msgpack
import orjson

from movici_data_core.exceptions import DeserializationError, UnsupportedFileType
from movici_simulation_core.types import ExternalSerializationStrategy, FileType


def load_dict(data: bytes, filetype: FileType) -> dict:
    try:
        if filetype == FileType.JSON:
            result = orjson.loads(data)
        elif filetype == FileType.MSGPACK:
            result = msgpack.unpackb(data)
        else:
            raise UnsupportedFileType(filetype)
    except (OSError, ValueError) as e:
        raise DeserializationError from e

    if not isinstance(result, dict):
        raise DeserializationError

    return result


def dump_dict(data: dict, filetype: FileType) -> bytes:
    if filetype == FileType.JSON:
        return orjson.dumps(data)
    if filetype == FileType.MSGPACK:
        return t.cast(bytes, msgpack.packb(data))

    raise UnsupportedFileType(filetype)


def load_dict_from_file(
    path: pathlib.Path,
    serializer: ExternalSerializationStrategy,
    filetype: FileType | None = None,
    **kwargs,
):
    filetype = filetype or FileType.from_extension(path.suffix)
    if filetype not in serializer.supported_file_types():
        raise UnsupportedFileType(filetype)

    try:
        return serializer.loads(path.read_bytes(), filetype, **kwargs)
    except (TypeError, ValueError) as e:
        # TODO: better error message from serializer.loads
        raise DeserializationError from e
