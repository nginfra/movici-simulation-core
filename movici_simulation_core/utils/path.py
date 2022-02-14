import os
import pathlib


class SubclassablePath(pathlib.Path):
    # subclassing pathlib.Path requires manually setting the flavour
    _flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour


class DatasetPath(SubclassablePath):
    def read_dict(self):
        raise NotImplementedError
