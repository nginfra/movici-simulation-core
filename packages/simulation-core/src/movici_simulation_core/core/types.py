from __future__ import annotations

import abc
import dataclasses
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
from ..types import DataMask, FileType, Result, UpdateData
from ..utils.path import DatasetPath
from .attribute_spec import AttributeSpec
from .priority import Priority

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
    priority: t.ClassVar[int] = int(Priority.REGULAR)

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

    def remap(self, payload: dict) -> t.Optional[bool]:
        """Optional hook for handling a ``REMAP`` command. The default returns ``None`` to
        indicate the model has not implemented this; the adapter then either installs
        transparent rename middleware or raises :class:`RemapError` if the REMAP requires
        many-to-one sub handling. Return ``True`` to take full responsibility for the
        REMAP (the adapter installs no middleware), or ``False`` to let the adapter install
        its default middleware. See issue #127.

        :param payload: the deserialised REMAP payload — a ``dict`` with optional ``pub``
            and ``sub`` keys.
        """
        return None

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


@dataclasses.dataclass
class RemapDecision:
    """Decision returned by :meth:`ModelAdapterBase.remap` telling the connector which
    rename middleware to install. See issue #127.

    Reachable combinations from the default :meth:`ModelAdapterBase.remap` flow:

    * ``Model.remap`` returns ``True`` → ``(install_pub_rename=False, install_sub_rename=False)``
      (the model handles everything itself).
    * ``Model.remap`` returns ``None`` and the sub remap is one-to-one →
      ``(install_pub_rename=True, install_sub_rename=True)`` (the connector handles
      both sides transparently).
    * ``Model.remap`` returns ``False``, or ``None`` with a many-to-one sub remap →
      ``(install_pub_rename=True, install_sub_rename=False)`` (the connector handles
      the pub side, the model is responsible for the sub-side data wrangling).

    The fourth combination — ``(install_pub_rename=False, install_sub_rename=True)`` —
    is intentionally not reachable through ``Model.remap``; subclassing
    :class:`ModelAdapterBase` is the way to produce it for unusual cases.
    """

    install_pub_rename: bool = True
    install_sub_rename: bool = True


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

        Validated here rather than at every consumer so a misconfigured model fails fast
        at registration time with a clear error instead of crashing the orchestrator's
        priority comparison much later.
        """
        value = getattr(self.model, "priority", int(Priority.REGULAR))
        if isinstance(value, bool) or not isinstance(value, int):
            raise TypeError(
                f"{type(self.model).__name__}.priority must be int, got {type(value).__name__}"
            )
        return value

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

    def remap(self, message: RemapMessage) -> RemapDecision:
        """Handle a ``REMAP`` command by consulting the inner model and deciding what
        rename middleware the connector should install. See issue #127.

        The default implementation:

        * delegates to ``self.model.remap(payload)`` first;
        * if the model returns ``True`` (it took full responsibility) — installs no rename
          middleware;
        * if the model returns ``False`` — installs the full set of renames implied by the
          payload;
        * if the model returns ``None`` (no override) — installs full middleware for a
          one-to-one sub remap, and raises :class:`RemapError` if any sub entry is
          many-to-one (multiple variants resolving to the same original) since that case
          fundamentally requires a model-level decision the adapter cannot make.
        """
        payload = {"pub": message.pub, "sub": message.sub}
        result = self.model.remap(payload)
        if result is True:
            return RemapDecision(install_pub_rename=False, install_sub_rename=False)
        many_to_one = _sub_has_many_to_one(message.sub)
        if result is None and many_to_one:
            raise RemapError(
                f"Model '{type(self.model).__name__}' received a many-to-one sub-remap "
                "but its remap() returned None (the default). Override "
                f"`{type(self.model).__name__}.remap` to return True (the model handles "
                "the many-to-one mapping itself, e.g. by registering the variant attribute "
                "fields in its state) or False (the connector still installs the pub-side "
                "rename middleware but you take responsibility for the sub side)."
            )
        # result is False or None (with one-to-one sub): install middleware. For a
        # many-to-one sub the model returned False — it has accepted responsibility on the
        # data side but still wants the connector to manage pub renames. The connector
        # never installs sub-rename middleware for many-to-one (the rename would collide),
        # so toggle that off explicitly.
        return RemapDecision(
            install_pub_rename=True,
            install_sub_rename=not many_to_one,
        )

    def set_schema(self, schema):
        pass


def _sub_has_many_to_one(sub_section: t.Optional[dict]) -> bool:
    """Return True if any entity group in the sub section has more than one variant
    resolving to the same original attribute name."""
    if not sub_section:
        return False
    for entity_groups in sub_section.values():
        if not entity_groups:
            continue
        for mapping in entity_groups.values():
            if not mapping:
                continue
            originals = list(mapping.values())
            if len(originals) != len(set(originals)):
                return True
    return False


class InitDataHandler(t.Protocol):
    def get(self, name: str) -> t.Tuple[t.Optional[FileType], t.Optional[DatasetPath]]: ...
    def ensure_ftype(self, name: str, ftype: FileType): ...


class UpdateDataClientBase(t.Protocol[T]):
    def get(self, address: str, key: str, mask: t.Optional[dict]) -> T: ...
    def put(self, data: T) -> t.Tuple[str, str]: ...
    def clear(self): ...
    def close(self): ...
