from __future__ import annotations

import logging
import typing as t
from abc import abstractmethod, ABC

from movici_simulation_core.networking.stream import MessageRouterSocketAdapter, Stream

if t.TYPE_CHECKING:
    from movici_simulation_core.core.simulation import Simulation
    from movici_simulation_core.model_connector.connector import ModelBaseAdapter


class Plugin(t.Protocol):
    @classmethod
    @abstractmethod
    def install(cls, sim: Simulation):
        raise NotImplementedError


class Service(Plugin, ABC):
    logger: logging.Logger

    def setup(
        self,
        *,
        config: dict,
        stream: Stream,
        logger: logging.Logger,
        socket: MessageRouterSocketAdapter,
    ):
        raise NotImplementedError

    @abstractmethod
    def run(self):
        raise NotImplementedError


class Model(Plugin, ABC):
    @abstractmethod
    def __init__(self, model_config: dict):
        raise NotImplementedError

    @abstractmethod
    def get_adapter(self) -> ModelBaseAdapter:
        raise NotImplementedError
