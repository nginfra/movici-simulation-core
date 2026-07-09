from __future__ import annotations

import dataclasses
import itertools
import typing as t
from functools import singledispatchmethod

from movici_simulation_core.core import InitDataHandler
from movici_simulation_core.utils.data_mask import apply_remap_to_data_mask

from ..core.types import ModelAdapterBase, UpdateDataClientBase
from ..exceptions import StreamDone
from ..messages import (
    AcknowledgeMessage,
    ClearDataMessage,
    DataMessage,
    GetDataMessage,
    Message,
    NewTimeMessage,
    PutDataMessage,
    QuitMessage,
    RegistrationMessage,
    RemapMessage,
    ResultMessage,
    UpdateMessage,
    UpdateSeriesMessage,
)
from ..networking.client import RequestClient, Sockets
from ..networking.stream import Stream
from ..types import AutoRemap, DataMask, InternalSerializationStrategy, UpdateData


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
    def _(self, msg: RemapMessage):
        self.connector.remap(msg)
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


T = t.TypeVar("T", bytes, dict)


@dataclasses.dataclass
class ModelConnector(t.Generic[T]):
    model: ModelAdapterBase
    updates: UpdateDataClientBase[T]
    init_data: InitDataHandler
    serialization: InternalSerializationStrategy[T]
    name: t.Optional[str] = None
    data_mask: DataMask = dataclasses.field(init=False, default_factory=dict)
    remapper: RemapMiddleware | None = dataclasses.field(init=False, default=None)

    def initialize(self) -> RegistrationMessage:
        self.data_mask = self.model.initialize(self.init_data)
        return RegistrationMessage(
            pub=self.data_mask["pub"],
            sub=self.data_mask["sub"],
            priority=int(self.model.priority),
        )

    def new_time(self, message: NewTimeMessage):
        self.updates.clear()
        self.model.new_time(message)

    def remap(self, message: RemapMessage) -> None:
        """Process a ``REMAP`` command from the orchestrator. The adapter decides what
        middleware to install; the connector stores the rename dictionaries and rewrites
        its sub mask so subsequent ``GET``s ask for the variant keys. See issue #127."""

        auto_remap = self.model.remap(message)

        if auto_remap.pub or auto_remap.sub:
            self.remapper = RemapMiddleware(message, auto_remap)
        self.data_mask = apply_remap_to_data_mask(self.data_mask, message)

    def update(self, update: UpdateMessage) -> ResultMessage:
        data = self._get_update_data(update)
        result_data, next_time = self.model.update(update, data=data)
        return self._process_result(result_data, next_time)

    def update_series(self, update: UpdateSeriesMessage) -> ResultMessage:
        data_series = (self._get_update_data(upd) for upd in update.updates)
        result_data, next_time = self.model.update_series(update, data=data_series)
        return self._process_result(result_data, next_time)

    def _get_update_data(self, update: UpdateMessage) -> UpdateData:
        if update.has_data and update.address is not None and update.key is not None:
            raw_data = self.updates.get(
                address=update.address, key=update.key, mask=self.data_mask.get("sub")
            )
            if raw_data is None:
                return None
            data = self.serialization.loads(raw_data)
            return self.remapper.rename_incoming_update(data) if self.remapper else data

        return None

    def _process_result(self, data: UpdateData, next_time: t.Optional[int]) -> ResultMessage:
        if data is None:
            return ResultMessage(None, None, next_time=next_time, origin=self.name)
        if self.remapper is not None:
            data = self.remapper.rename_outgoing_update(data)
        result_data = self.serialization.dumps(data)
        address, key = self.updates.put(result_data)
        return ResultMessage(key=key, address=address, next_time=next_time, origin=self.name)

    def close(self, message: QuitMessage):
        self.model.close(message)
        self.updates.close()


class UpdateDataClient(UpdateDataClientBase[bytes]):
    home_address: str
    counter: t.Iterator[str]

    def __init__(self, name: str, home_address: str, sockets: Sockets | None = None):
        self.client = RequestClient(name, sockets)
        self.name = name
        self.home_address = home_address
        self.reset_counter()

    def get(self, address: str, key: str, mask: t.Optional[dict]) -> bytes:
        resp = self.client.request(address, GetDataMessage(key, mask), valid_responses=DataMessage)
        return resp.data

    def put(self, data: bytes) -> t.Tuple[str, str]:
        key = next(self.counter)
        self.client.request(
            self.home_address, PutDataMessage(key, data), valid_responses=AcknowledgeMessage
        )
        return self.home_address, key

    def clear(self):
        self.client.request(
            self.home_address, ClearDataMessage(self.name), valid_responses=AcknowledgeMessage
        )
        self.reset_counter()

    def close(self):
        self.client.close()

    def reset_counter(self):
        self.counter = map(lambda num: f"{self.name}_{num}", itertools.count())


@dataclasses.dataclass
class RemapMiddleware:
    remap: RemapMessage
    auto_remap: AutoRemap

    def rename_incoming_update(self, update: dict):
        if self.remap.sub and self.auto_remap.sub:
            return self._rename_data(update, self.remap.sub)
        return update

    def rename_outgoing_update(self, update: dict):
        if self.remap.pub and self.auto_remap.pub:
            return self._rename_data(update, self.remap.pub)
        return update

    def _rename_data(self, data: dict, mapping: dict):
        def _helper(data: dict, mapping: dict, level: int):
            # updates are nested dictionaries, level 0 is the dataset level, level 1 the entity
            # group level and level 2 the attribute level. At the attribute level we want to do
            # the rename
            if level == 2:
                return {mapping.get(k, k): v for k, v in data.items()}
            return {
                k: (_helper(v, mapping[k], level=level + 1) if k in mapping else v)
                for k, v in data.items()
            }

        try:
            return _helper(data, mapping, level=0)
        except (ValueError, TypeError):
            raise ValueError("Malformed data or mapping") from None
