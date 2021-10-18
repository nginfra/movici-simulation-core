from __future__ import annotations

import logging
import typing as t

from movici_simulation_core.networking.stream import MessageRouterSocket, Stream
from movici_simulation_core.utils.settings import Settings

if t.TYPE_CHECKING:
    from movici_simulation_core.model_connector.connector import ModelAdapterBase
    from movici_simulation_core.core.schema import PropertySpec


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
    def get_schema_attributes(cls) -> t.Iterable[PropertySpec]:
        return ()

    def __init_subclass__(cls, **kwargs):
        cls.__model_name__ = kwargs.get("name", cls.__model_name__)

    @classmethod
    def install(cls, obj: Extensible):
        if cls.__model_name__ is None:
            raise ValueError(f"Missing __model_name__ for model {cls.__name__}")
        obj.register_model_type(cls.__model_name__, cls)


class Extensible:
    def register_attributes(self, attributes: t.Iterable[PropertySpec]):
        pass

    def register_model_type(self, identifier: str, model_type: t.Type[Model]):
        pass

    def register_service(
        self, identifier: str, service: t.Type[Service], auto_use=False, daemon=True
    ):
        pass
