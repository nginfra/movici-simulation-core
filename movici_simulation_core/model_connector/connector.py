from __future__ import annotations

import abc
import dataclasses
import enum
import itertools
import logging
import os
import pathlib
import typing as t
from functools import singledispatchmethod

import msgpack
import zmq

from movici_simulation_core.core import Model
from movici_simulation_core.core.data_format import EntityInitDataFormat
from movici_simulation_core.core.schema import PropertySpec
from movici_simulation_core.core.settings import Settings
from movici_simulation_core.exceptions import InvalidMessage
from movici_simulation_core.networking.messages import (
    NewTimeMessage,
    UpdateSeriesMessage,
    RegistrationMessage,
    ResultMessage,
    Message,
    QuitMessage,
    GetDataMessage,
    ErrorMessage,
    UpdateMessage,
    PutDataMessage,
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
)
from movici_simulation_core.networking.stream import (
    Stream,
    get_message_socket,
    MessageSocketAdapter,
)
from movici_simulation_core.types import Timestamp, UpdateData, Result


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

    @handle_message.register
    def _(self, msg: UpdateMessage):
        self.connector.update(msg)

    @handle_message.register
    def _(self, msg: UpdateSeriesMessage):
        self.connector.update_series(msg)

    @handle_message.register
    def _(self, msg: QuitMessage):
        self.connector.close()

    def initialize(self):
        resp = self.connector.initialize()
        self.stream.send(resp)


class DataMask(t.TypedDict):
    pub: dict
    sub: dict


@dataclasses.dataclass
class ModelConnector:
    model: ModelBaseAdapter
    updates: UpdateDataHandler
    init_data: InitDataHandler
    data_mask: t.Optional[DataMask] = None

    def initialize(self) -> RegistrationMessage:
        self.data_mask = self.model.initialize(self.init_data)
        return RegistrationMessage(pub=self.data_mask["pub"], sub=self.data_mask["sub"])

    def new_time(self, message: NewTimeMessage):
        self.model.new_time(message.timestamp)

    def update(self, update: UpdateMessage) -> ResultMessage:
        data = self._get_update_data(update)
        result_data, next_time = self.model.update(update.timestamp, data=data)
        return self._process_result(result_data, next_time)

    def update_series(self, update: UpdateSeriesMessage) -> ResultMessage:
        timestamp = update.updates[0].timestamp if update.updates else None
        data_series = (self._get_update_data(upd) for upd in update.updates)
        result_data, next_time = self.model.update_series(timestamp, data=data_series)
        return self._process_result(result_data, next_time)

    def _get_update_data(self, update: UpdateMessage) -> t.Optional[bytes]:
        if update.has_data:
            return self.updates.get(
                address=update.address, key=update.key, mask=self.data_mask.get("sub")
            )
        return None

    def _process_result(self, data: bytes, next_time: t.Optional[int]) -> ResultMessage:
        address, key = self._send_update_data(data)
        return ResultMessage(key=key, address=address, next_time=next_time)

    def _send_update_data(
        self, result: t.Optional[bytes]
    ) -> t.Tuple[t.Optional[str], t.Optional[str]]:
        if result is None:
            return None, None
        return self.updates.put(result)

    def close(self):
        self.model.close()


@dataclasses.dataclass
class UpdateDataHandler:
    name: str
    home_address: str
    get_socket: t.Callable[[int], MessageSocketAdapter] = get_message_socket
    counter: t.Iterator = dataclasses.field(default=None, init=False)

    def __post_init__(self):
        self.reset_counter()

    def get(self, address: str, key: str, mask: t.Optional[dict]) -> bytes:
        resp = self._request(address, GetDataMessage(key, mask), valid_messages=DataMessage)
        return resp.data

    def put(self, data: bytes) -> t.Tuple[str, str]:
        key = next(self.counter)
        self._request(
            self.home_address, PutDataMessage(key, data), valid_messages=AcknowledgeMessage
        )
        return self.home_address, key

    def clear(self):
        self._request(
            self.home_address, ClearDataMessage(self.name), valid_messages=AcknowledgeMessage
        )
        self.reset_counter()

    def reset_counter(self):
        self.counter = map(lambda num: f"{self.name}_{num}", itertools.count())

    def _request(
        self,
        address,
        msg,
        *,
        valid_messages: t.Union[t.Type[Message], t.Tuple[..., t.Type[Message]], None] = None,
    ):
        with self.get_socket(zmq.REQ) as socket:
            socket.connect(address)
            socket.send(msg)
            resp = socket.recv()
        self.raise_on_invalid_message(resp, valid_messages)
        return resp

    @staticmethod
    def raise_on_invalid_message(
        message,
        valid_messages: t.Optional[t.Union[t.Type[Message], t.Tuple[..., t.Type[Message]]]] = None,
    ):
        if isinstance(message, ErrorMessage):
            raise ValueError(message.error)
        if valid_messages is not None and not isinstance(message, valid_messages):
            raise InvalidMessage(message)


class DatasetType(enum.Enum):
    JSON = (".json",)
    MSGPACK = (".msgpack",)
    CSV = (".csv",)
    OTHER = ()

    @classmethod
    def from_extension(cls, ext):
        for member in cls.__members__.values():
            if ext.lower() in member.value:
                return member
        return cls.OTHER


class DatasetPath(pathlib.Path):
    # subclassing pathlib.Path requires manually setting the flavour
    _flavour = pathlib._windows_flavour if os.name == "nt" else pathlib._posix_flavour

    def read_dict(self):
        return NotImplementedError


class _JsonPath(DatasetPath):
    schema: t.Sequence[PropertySpec] = None

    def read_dict(self):
        return EntityInitDataFormat(self.schema).loads(self.read_text())


def JsonPath(path, schema: t.Sequence[PropertySpec]):
    obj = _JsonPath(path)
    obj.schema = schema
    return obj


class MsgPackPath(DatasetPath):
    def read_dict(self):
        return msgpack.unpackb(self.read_bytes())


@dataclasses.dataclass
class InitDataHandler:
    root: pathlib.Path
    schema: t.Sequence[PropertySpec] = dataclasses.field(default_factory=list)

    def get(self, name: str) -> t.Tuple[DatasetType, DatasetPath]:
        file_walker = (
            pathlib.Path(root) / pathlib.Path(file)
            for root, dirs, files in os.walk(self.root)
            for file in files
        )
        for path in file_walker:
            if path.stem == name:
                return self.get_type_and_path(path)

    def get_type_and_path(self, path) -> t.Tuple[DatasetType, DatasetPath]:
        dtype = DatasetType.from_extension(path.suffix)
        if dtype == DatasetType.JSON:
            return dtype, _JsonPath(path, schema=self.schema)
        else:
            return dtype, DatasetPath(path)


@dataclasses.dataclass
class ModelBaseAdapter(abc.ABC):
    model: Model
    settings: Settings
    logger: logging.Logger

    @abc.abstractmethod
    def initialize(self, init_data_handler: InitDataHandler) -> DataMask:
        raise NotImplementedError

    @abc.abstractmethod
    def new_time(self, new_time: Timestamp):
        raise NotImplementedError

    @abc.abstractmethod
    def update(self, timestamp: Timestamp, data: UpdateData) -> Result:
        raise NotImplementedError

    @abc.abstractmethod
    def update_series(self, timestamp: Timestamp, data: t.Iterable[t.Optional[bytes]]) -> Result:
        raise NotImplementedError

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError
