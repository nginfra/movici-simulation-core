from __future__ import annotations

import abc
import dataclasses
import itertools
import logging
import typing as t
from functools import singledispatchmethod

from movici_simulation_core.core import Model
from movici_simulation_core.exceptions import StreamDone
from movici_simulation_core.model_connector.init_data import InitDataHandler
from movici_simulation_core.networking.client import Sockets, RequestClient
from movici_simulation_core.networking.messages import (
    NewTimeMessage,
    UpdateSeriesMessage,
    RegistrationMessage,
    ResultMessage,
    Message,
    QuitMessage,
    GetDataMessage,
    UpdateMessage,
    PutDataMessage,
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
)
from movici_simulation_core.networking.stream import Stream
from movici_simulation_core.types import RawUpdateData, RawResult, DataMask
from movici_simulation_core.utils.settings import Settings


@dataclasses.dataclass
class ConnectorStreamHandler:
    connector: ModelConnector
    stream: Stream[Message]

    def __post_init__(self):
        self.stream.set_handler(self.handle_message)

    @singledispatchmethod
    def handle_message(self, msg: Message):
        raise ValueError("Unknown message")

    @handle_message.register
    def _(self, msg: NewTimeMessage):
        self.connector.new_time(msg)
        self.stream.send(AcknowledgeMessage())

    @handle_message.register
    def _(self, msg: UpdateMessage):
        result = self.connector.update(msg)
        self.stream.send(result)

    @handle_message.register
    def _(self, msg: UpdateSeriesMessage):
        result = self.connector.update_series(msg)
        self.stream.send(result)

    @handle_message.register
    def _(self, msg: QuitMessage):
        self.connector.close(msg)
        self.stream.send(AcknowledgeMessage())
        raise StreamDone

    def initialize(self):
        resp = self.connector.initialize()
        self.stream.send(resp)


@dataclasses.dataclass
class ModelConnector:
    model: ModelAdapterBase
    updates: UpdateDataClient
    init_data: InitDataHandler
    data_mask: t.Optional[DataMask] = dataclasses.field(init=False, default=None)
    name: t.Optional[str] = None

    def initialize(self) -> RegistrationMessage:
        self.data_mask = self.model.initialize(self.init_data)
        return RegistrationMessage(pub=self.data_mask["pub"], sub=self.data_mask["sub"])

    def new_time(self, message: NewTimeMessage):
        self.model.new_time(message)

    def update(self, update: UpdateMessage) -> ResultMessage:
        data = self._get_update_data(update)
        result_data, next_time = self.model.update(update, data=data)
        return self._process_result(result_data, next_time)

    def update_series(self, update: UpdateSeriesMessage) -> ResultMessage:
        data_series = (self._get_update_data(upd) for upd in update.updates)
        result_data, next_time = self.model.update_series(update, data=data_series)
        return self._process_result(result_data, next_time)

    def _get_update_data(self, update: UpdateMessage) -> t.Optional[bytes]:
        if update.has_data:
            return self.updates.get(
                address=update.address, key=update.key, mask=self.data_mask.get("sub")
            )
        return None

    def _process_result(self, data: bytes, next_time: t.Optional[int]) -> ResultMessage:
        address, key = self._send_update_data(data)
        return ResultMessage(key=key, address=address, next_time=next_time, origin=self.name)

    def _send_update_data(
        self, result: t.Optional[bytes]
    ) -> t.Tuple[t.Optional[str], t.Optional[str]]:
        if result is None:
            return None, None
        return self.updates.put(result)

    def close(self, message: QuitMessage):
        self.model.close(message)
        self.updates.close()


class UpdateDataClient(RequestClient):
    home_address: str
    counter: t.Iterator[str]

    def __init__(self, name: str, home_address: str, sockets: Sockets = None):
        super().__init__(name, sockets)
        self.home_address = home_address
        self.reset_counter()

    def get(self, address: str, key: str, mask: t.Optional[dict]) -> bytes:
        resp = self.request(address, GetDataMessage(key, mask), valid_responses=DataMessage)
        return resp.data

    def put(self, data: bytes) -> t.Tuple[str, str]:
        key = next(self.counter)
        self.request(
            self.home_address, PutDataMessage(key, data), valid_responses=AcknowledgeMessage
        )
        return self.home_address, key

    def clear(self):
        self.request(
            self.home_address, ClearDataMessage(self.name), valid_responses=AcknowledgeMessage
        )
        self.reset_counter()

    def reset_counter(self):
        self.counter = map(lambda num: f"{self.name}_{num}", itertools.count())


class ModelAdapterBase(abc.ABC):
    model: Model
    settings: Settings
    logger: logging.Logger

    def __init__(self, model: Model, settings: Settings, logger: logging.Logger):
        self.model = model
        self.settings = settings
        self.logger = logger

    @abc.abstractmethod
    def initialize(self, init_data_handler: InitDataHandler) -> DataMask:
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
