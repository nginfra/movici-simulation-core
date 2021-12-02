from __future__ import annotations
import dataclasses
import enum
import os
import pathlib
import typing as t

import msgpack

from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.networking.client import RequestClient, Sockets
from movici_simulation_core.networking.messages import GetDataMessage, PathMessage


class InitDataHandler:
    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        pass

    def get_type_and_path(self, path) -> t.Tuple[FileType, DatasetPath]:
        dtype = FileType.from_extension(path.suffix)
        return dtype, DatasetPath(path)

    def ensure_ftype(self, name: str, ftype: FileType):
        result_ftype, path = self.get(name)
        if result_ftype is None:
            raise ValueError(f"Error retrieving dataset {name}: Not found")
        if result_ftype != ftype:
            raise ValueError(
                f"Error retrieving dataset {name}: Expected {ftype.name}, got {result_ftype.name}"
            )
        return result_ftype, path


@dataclasses.dataclass
class DirectoryInitDataHandler(InitDataHandler):
    root: pathlib.Path

    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        file_walker = (
            pathlib.Path(root) / pathlib.Path(file)
            for root, dirs, files in os.walk(self.root)
            for file in files
        )
        for path in file_walker:
            if path.stem == name:
                return self.get_type_and_path(path)
        return None, None

    def get_type_and_path(self, path) -> t.Tuple[FileType, DatasetPath]:
        dtype = FileType.from_extension(path.suffix)
        return dtype, DatasetPath(path)


@dataclasses.dataclass
class ServicedInitDataHandler(InitDataHandler):
    name: str
    server: str
    client: InitDataClient = dataclasses.field(init=False)

    def __post_init__(self):
        self.client = InitDataClient(self.name, self.server)

    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        path = self.client.get(name)
        if path is not None:
            return self.get_type_and_path(path)
        return None, None

    def close(self):
        self.client.close()


class DatasetPath(pathlib.Path):
    # subclassing pathlib.Path requires manually setting the flavour
    _flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour

    def read_dict(self):
        raise NotImplementedError


class _JsonPath(DatasetPath):
    schema: t.Optional[AttributeSchema] = None

    def read_dict(self):
        return EntityInitDataFormat(self.schema).load_bytes(self.read_bytes())


class _MsgpackPath(DatasetPath):
    schema: t.Optional[AttributeSchema] = None

    def read_dict(self):
        return EntityInitDataFormat(self.schema).load_json(msgpack.unpackb(self.read_bytes()))


def _serialized_dict_path(cls, docstr=None):
    # It is not possible to override __init__ of a subclass of pathlib.Path because it has custom
    # initialization method. So instead we use a custom factory function posing as a class
    # constructor, to set additional attributes
    def constructor(path, schema: t.Optional[AttributeSchema] = None):
        obj = cls(path)
        obj.schema = schema
        return obj

    if docstr is not None:
        constructor.__doc__ = docstr
    return constructor


JsonPath = _serialized_dict_path(
    _JsonPath,
    docstr="""JsonPath is a subclass of `pathlib.Path` that points to JSON dataset file. It has one
    additional method `read_dict` that returns a dictionary of the dataset, assuming entity based
    data

    :param path: The location of the the dataset file
    :param schema: An attribute schema for interpreting the entity based data.
    """,
)
MsgpackPath = _serialized_dict_path(
    _MsgpackPath,
    docstr="""MsgpackPath is a subclass of `pathlib.Path` that points to msgpack dataset file.
    It has one additional method `read_dict` that returns a dictionary of the dataset, assuming
    :param path: The location of the the dataset file
    entity based data

    :param schema: An attribute schema for interpreting the entity based data.
    """,
)


class FileType(enum.Enum):
    JSON = (".json",)
    MSGPACK = (".msgpack",)
    CSV = (".csv",)
    NETCDF = (".nc",)
    OTHER = ()

    @classmethod
    def from_extension(cls, ext):
        for member in cls.__members__.values():
            if ext.lower() in member.value:
                return member
        return cls.OTHER


class InitDataClient(RequestClient):
    def __init__(self, name: str, server: str, sockets: Sockets = None):
        super().__init__(name, sockets)
        self.server = server

    def get(self, key: str, mask: t.Optional[dict] = None) -> t.Optional[pathlib.Path]:
        resp = self.request(self.server, GetDataMessage(key, mask), valid_responses=PathMessage)
        return resp.path
