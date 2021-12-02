import typing as t

from movici_simulation_core.core.schema import AttributeSchema
from movici_simulation_core.model_connector.init_data import (
    InitDataHandler,
    DatasetPath,
    JsonPath,
    FileType,
    MsgpackPath,
)


class SchemaAwareInitDataHandler(InitDataHandler):
    def __init__(self, handler: InitDataHandler, schema: t.Optional[AttributeSchema]):
        self.handler = handler
        self.schema = schema

    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        dtype, path = self.handler.get(name)
        if dtype is None:
            return None, None
        if dtype == FileType.JSON:
            path = JsonPath(path, self.schema)
        if dtype == FileType.MSGPACK:
            path = MsgpackPath(path, self.schema)
        return dtype, path
