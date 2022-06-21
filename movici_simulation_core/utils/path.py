from __future__ import annotations

import functools
import os
import pathlib
import typing as t

from movici_simulation_core.types import ExternalSerializationStrategy, FileType


def _dataset_path(cls: t.Type[DatasetPath]):
    # It is not possible to override __init__ of a subclass of pathlib.Path because it has custom
    # initialization method. So instead we use a custom factory function posing as a class
    # constructor, to set additional attributes
    cls._flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour

    @functools.wraps(cls)
    def constructor(
        path,
        filetype: t.Optional[FileType] = None,
        strategy: t.Optional[ExternalSerializationStrategy] = None,
    ):
        obj = cls(path)
        obj.filetype = filetype
        obj.strategy = strategy
        return obj

    return constructor


@_dataset_path
class DatasetPath(pathlib.Path):
    """JsonPath is a subclass of `pathlib.Path` that points to a Movici format dataset file. It has
    one additional method `read_dict` that returns a dictionary of the dataset

    :param path: The location of the the dataset file

    """

    strategy: t.Optional[ExternalSerializationStrategy] = None
    filetype: t.Optional[FileType] = None

    def read_dict(self):
        if self.strategy is None:
            raise ValueError("No (de)serialization strategy set")

        filetype = (
            self.filetype if self.filetype is not None else FileType.from_extension(self.suffix)
        )
        if filetype not in self.strategy.supported_file_types():
            raise TypeError(f"Unsupported filetype {filetype} with extension '{self.suffix}'")

        return self.strategy.loads(self.read_bytes(), filetype)
