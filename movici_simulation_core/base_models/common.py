import typing as t

from movici_simulation_core.model_connector import InitDataHandler
from movici_simulation_core.types import ExternalSerializationStrategy, FileType
from movici_simulation_core.utils import strategies
from movici_simulation_core.utils.path import DatasetPath


class EntityAwareInitDataHandler(InitDataHandler):
    def __init__(
        self, handler: InitDataHandler, strategy: t.Optional[ExternalSerializationStrategy] = None
    ):
        self.handler = handler
        self.strategy = strategy or strategies.get_instance(ExternalSerializationStrategy)

    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        ftype, path = self.handler.get(name)
        if ftype is None:
            return None, None
        if ftype in self.strategy.supported_file_types():
            return ftype, DatasetPath(path, filetype=ftype, strategy=self.strategy)
        return ftype, path
