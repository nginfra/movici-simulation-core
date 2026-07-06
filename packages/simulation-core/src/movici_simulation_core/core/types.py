from __future__ import annotations

import abc
import logging
import typing as t
from pathlib import Path

from movici_simulation_core.validate import ModelConfigSchema, validate_and_migrate_config

from ..exceptions import RemapError
from ..messages import (
    NewTimeMessage,
    QuitMessage,
    RemapMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from ..networking.stream import BaseStream, MessageRouterSocket
from ..settings import Settings
from ..types import AutoRemap, DataMask, FileType, Priority, Result, UpdateData
from ..utils.path import DatasetPath
from .attribute_spec import AttributeSpec

T = t.TypeVar("T")


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
        stream: BaseStream,
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
    __model_config_schema__: (
        t.ClassVar[Path | ModelConfigSchema] | list[ModelConfigSchema] | None
    ) = None
    # Publishing priority for ownership resolution; solver helpers override this. See
    # issue #127.
    priority: t.ClassVar[int] = Priority.REGULAR

    def __init__(self, model_config: dict, validate_config=True):
        if validate_config:
            model_config = self._ensure_valid_model_config(model_config)
        self.config = model_config

    @classmethod
    def _ensure_valid_model_config(cls, config):
        versions = cls.__model_config_schema__
        if versions is None:
            return config

        if isinstance(versions, Path):
            versions = [ModelConfigSchema(schema=versions)]
        if isinstance(versions, ModelConfigSchema):
            versions = [versions]
        return validate_and_migrate_config(config, versions)

    def get_adapter(self) -> t.Type[ModelAdapterBase]:
        raise NotImplementedError

    def remap(self, payload: RemapMessage) -> AutoRemap:
        """Optional hook for handling a ``REMAP`` command. The default returns ``None`` to
        indicate the model has not implemented this; the adapter then either installs
        transparent rename middleware or raises :class:`RemapError` if the REMAP requires
        many-to-one sub handling. Return ``True`` to take full responsibility for the
        REMAP (the adapter installs no middleware), or ``False`` to let the adapter install
        its default middleware. See issue #127.

        :param payload: the RemapMessage.
        """
        return AutoRemap.default()

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

    @property
    def priority(self) -> int:
        """The model's publishing priority, exposed to the connector so it can be written
        into the ``RegistrationMessage`` sent to the orchestrator. See issue #127.
        """
        return self.model.priority

    @abc.abstractmethod
    def initialize(self, init_data_handler: InitDataHandler) -> DataMask:
        raise NotImplementedError

    @abc.abstractmethod
    def new_time(self, message: NewTimeMessage):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, message: UpdateMessage, data: UpdateData) -> Result:
        raise NotImplementedError

    @abc.abstractmethod
    def update_series(self, message: UpdateSeriesMessage, data: t.Iterable[UpdateData]) -> Result:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self, message: QuitMessage):
        raise NotImplementedError

    def remap(self, message: RemapMessage) -> AutoRemap:
        """Handle a ``REMAP`` command by consulting the inner model and deciding what
        rename middleware the connector should install. See issue #127.

        The default implementation:

        * delegates to ``self.model.remap(payload)`` first;
        * if the model returns ``True`` (it took full responsibility) - installs no rename
          middleware;
        * if the model returns ``False`` - installs full middleware for a
          one-to-one sub remap, and raises :class:`RemapError` if any sub entry is
          many-to-one (multiple variants resolving to the same original) since that case
          fundamentally requires a model-level decision the adapter cannot make.
        """
        result = self.model.remap(message)
        if result.sub and _sub_has_many_to_one(message.sub):
            raise RemapError(
                f"Model '{type(self.model).__name__}' received a many-to-one sub-remap "
                "but its remap() returned AutoRemap(sub=True). Override "
                f"`{type(self.model).__name__}.remap` to return AutoRemap(sub=True) (the model "
                "handles the many-to-one mapping itself, e.g. by registering the variant "
                " attribute fields in its state)"
            )
        return result

    def set_schema(self, schema):
        pass


def _sub_has_many_to_one(sub_section: t.Optional[dict]) -> bool:
    """Return True if any entity group in the sub section has more than one variant
    resolving to the same original attribute name."""
    if sub_section is None:
        return False
    return any(
        len(attrs) != len(set(attrs.values()))
        for eg in sub_section.values()
        for attrs in eg.values()
    )


class InitDataHandler(t.Protocol):
    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]: ...
    def ensure_ftype(self, name: str, ftype: FileType): ...


class UpdateDataClientBase(t.Protocol[T]):
    def get(self, address: str, key: str, mask: t.Optional[dict]) -> T: ...
    def put(self, data: T) -> t.Tuple[str, str]: ...
    def clear(self): ...
    def close(self): ...
