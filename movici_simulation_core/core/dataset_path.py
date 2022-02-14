import functools
import typing as t

from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.data_tracker.data_format import EntityInitDataFormat
from movici_simulation_core.utils.path import DatasetPath
import msgpack


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
    @functools.wraps(cls)
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
    entity based data

    :param path: The location of the the dataset file
    :param schema: An attribute schema for interpreting the entity based data.

    """,
)
