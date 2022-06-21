from __future__ import annotations

import abc
import logging
import typing as t

from ..messages import NewTimeMessage, QuitMessage, UpdateMessage, UpdateSeriesMessage
from ..networking.stream import MessageRouterSocket, Stream
from ..settings import Settings
from ..types import DataMask, FileType, RawResult, RawUpdateData
from ..utils.path import DatasetPath
from .attribute_spec import AttributeSpec


class Plugin:
    @classmethod
    def install(cls, obj: Extensible):
        raise NotImplementedError


class Service(Plugin):
    __service_name__: t.ClassVar[t.Optional[str]] = None
    logger: logging.Logger

    def setup(
        self,
        *,
        settings: Settings,
        stream: Stream,
        logger: logging.Logger,
        socket: MessageRouterSocket,
    ):
        raise NotImplementedError

    def run(self):
        raise NotImplementedError

    def __init_subclass__(cls, **kwargs):
        cls.__service_name__ = kwargs.get("name", cls.__service_name__)

    @classmethod
    def install(cls, obj: Extensible):
        if cls.__service_name__ is None:
            raise ValueError(f"Missing __service_name__ for service {cls.__name__}")
        obj.register_service(cls.__service_name__, cls)


class Model(Plugin):
    __model_name__: t.ClassVar[t.Optional[str]] = None

    def __init__(self, model_config: dict):
        self.config = model_config

    def get_adapter(self) -> t.Type[ModelAdapterBase]:
        raise NotImplementedError

    @classmethod
    def get_schema_attributes(cls) -> t.Iterable[AttributeSpec]:
        return ()

    def __init_subclass__(cls, **kwargs):
        cls.__model_name__ = kwargs.get("name", cls.__model_name__)

    @classmethod
    def install(cls, obj: Extensible):
        if cls.__model_name__ is None:
            raise ValueError(f"Missing __model_name__ for model {cls.__name__}")
        obj.register_model_type(cls.__model_name__, cls)


class Extensible:
    def register_attributes(self, attributes: t.Iterable[AttributeSpec]):
        pass

    def register_model_type(self, identifier: str, model_type: t.Type[Model]):
        pass

    def register_service(
        self, identifier: str, service: t.Type[Service], auto_use=False, daemon=True
    ):
        pass

    def set_strategy(self, tp):
        pass


class ModelAdapterBase(abc.ABC):
    model: Model
    settings: Settings
    logger: logging.Logger

    def __init__(self, model: Model, settings: Settings, logger: logging.Logger):
        self.model = model
        self.settings = settings
        self.logger = logger

    @abc.abstractmethod
    def initialize(self, init_data_handler: InitDataHandlerBase) -> DataMask:
        raise NotImplementedError

    @abc.abstractmethod
    def new_time(self, message: NewTimeMessage):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, message: UpdateMessage, data: RawUpdateData) -> RawResult:
        raise NotImplementedError

    @abc.abstractmethod
    def update_series(
        self, message: UpdateSeriesMessage, data: t.Iterable[t.Optional[bytes]]
    ) -> RawResult:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self, message: QuitMessage):
        raise NotImplementedError

    def set_schema(self, schema):
        pass


class InitDataHandlerBase:
    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]:
        raise NotImplementedError

    def ensure_ftype(self, name: str, ftype: FileType):
        raise NotImplementedError
