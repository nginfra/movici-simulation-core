from __future__ import annotations

import dataclasses
import os
import pathlib
import typing as t

from movici_simulation_core.core.types import InitDataHandlerBase
from movici_simulation_core.messages import GetDataMessage, PathMessage
from movici_simulation_core.networking.client import RequestClient, Sockets
from movici_simulation_core.types import FileType
from movici_simulation_core.utils.path import DatasetPath


class InitDataHandler(InitDataHandlerBase):
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


class InitDataClient(RequestClient):
    def __init__(self, name: str, server: str, sockets: Sockets = None):
        super().__init__(name, sockets)
        self.server = server

    def get(self, key: str, mask: t.Optional[dict] = None) -> t.Optional[pathlib.Path]:
        resp = self.request(self.server, GetDataMessage(key, mask), valid_responses=PathMessage)
        return resp.path
