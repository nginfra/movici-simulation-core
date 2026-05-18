from __future__ import annotations

import dataclasses
import os
import pathlib
import typing as t

from movici_simulation_core.core.types import InitDataHandler
from movici_simulation_core.messages import GetDataMessage, PathMessage
from movici_simulation_core.networking.client import RequestClient
from movici_simulation_core.types import FileType
from movici_simulation_core.utils.path import DatasetPath


class InitDataClient(InitDataHandler):
    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        raise NotImplementedError

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
class DirectoryInitDataClient(InitDataClient):
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
class ServicedInitDataClient(InitDataClient):
    name: str
    server: str
    client: RequestClient = dataclasses.field(init=False)

    def __post_init__(self):
        self.client = RequestClient(self.name)

    def get(
        self, name: str, mask: dict | None = None
    ) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        resp = self.client.request(
            self.server, GetDataMessage(name, mask), valid_responses=PathMessage
        )
        path = resp.path
        if path is not None:
            return self.get_type_and_path(path)
        return None, None

    def close(self):
        self.client.close()
