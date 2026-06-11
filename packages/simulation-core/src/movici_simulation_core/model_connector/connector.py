from __future__ import annotations

import copy
import dataclasses
import itertools
import typing as t
from functools import singledispatchmethod

from movici_simulation_core.core import InitDataHandler

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
from ..types import DataMask, InternalSerializationStrategy, UpdateData
from ..utils.data_mask import apply_remap_to_sub_mask


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
    # ``_pub_renames`` and ``_sub_renames`` are populated by :meth:`remap` (see issue #127)
    # and applied transparently in :meth:`_process_result` and :meth:`_get_update_data`
    # respectively. The shapes mirror the ``RemapMessage`` payload:
    #   _pub_renames: {dataset: {entity_group: {original: variant}}}
    #   _sub_renames: {dataset: {entity_group: {variant: original}}}
    # ``_sub_renames`` is only populated when the adapter elected to handle a one-to-one
    # sub remap with middleware — many-to-one is always handled by the model itself.
    _pub_renames: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = dataclasses.field(
        init=False, default_factory=dict
    )
    _sub_renames: t.Dict[str, t.Dict[str, t.Dict[str, str]]] = dataclasses.field(
        init=False, default_factory=dict
    )

    def initialize(self) -> RegistrationMessage:
        self.data_mask = self.model.initialize(self.init_data)
        return RegistrationMessage(
            pub=self.data_mask["pub"],
            sub=self.data_mask["sub"],
            priority=self.model.priority,
        )

    def new_time(self, message: NewTimeMessage):
        self.updates.clear()
        self.model.new_time(message)

    def remap(self, message: RemapMessage) -> None:
        """Process a ``REMAP`` command from the orchestrator. The adapter decides what
        middleware to install; the connector stores the rename dictionaries and rewrites
        its sub mask so subsequent ``GET``s ask for the variant keys. See issue #127."""
        decision = self.model.remap(message)
        if decision.install_pub_rename and message.pub:
            self._pub_renames = _merge_rename_dict(self._pub_renames, message.pub)
        if decision.install_sub_rename and message.sub:
            self._sub_renames = _merge_rename_dict(self._sub_renames, message.sub)
        if message.sub:
            self.data_mask["sub"] = apply_remap_to_sub_mask(self.data_mask.get("sub"), message.sub)

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
            return _apply_sub_renames(data, self._sub_renames)

        return None

    def _process_result(self, data: UpdateData, next_time: t.Optional[int]) -> ResultMessage:
        renamed = _apply_pub_renames(data, self._pub_renames) if data is not None else None
        result_data = self.serialization.dumps(renamed) if renamed is not None else None
        address, key = self._send_update_data(result_data)
        return ResultMessage(key=key, address=address, next_time=next_time, origin=self.name)

    def _send_update_data(
        self, result: t.Optional[T]
    ) -> t.Tuple[t.Optional[str], t.Optional[str]]:
        if result is None:
            return None, None
        return self.updates.put(result)

    def close(self, message: QuitMessage):
        self.model.close(message)
        self.updates.close()


def _apply_pub_renames(
    data: dict, renames: t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]]
) -> dict:
    """Return a copy of ``data`` with publish-side attribute keys renamed per ``renames``
    (``{dataset: {entity_group: {original: variant}}}``). Expects the canonical Movici
    update shape ``{dataset: {entity_group: {attr: value}}}`` and raises ``ValueError`` on
    any other shape — silently passing malformed model output downstream is a confusing
    failure mode."""
    return _rename_data(data, renames, side="pub")


def _apply_sub_renames(
    data: dict, renames: t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]]
) -> dict:
    """Return a copy of ``data`` with subscribe-side attribute keys renamed per ``renames``
    (``{dataset: {entity_group: {variant: original}}}``). Only used for the one-to-one case;
    many-to-one sub remaps are handled by the model directly. Raises ``ValueError`` on
    malformed update data (see :func:`_apply_pub_renames`)."""
    return _rename_data(data, renames, side="sub")


def _rename_data(
    data: dict,
    renames: t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]],
    side: str,
) -> dict:
    if not renames:
        return data
    if not isinstance(data, dict):
        raise ValueError(
            f"REMAP {side} rename received non-dict update data: got {type(data).__name__}"
        )
    out: dict = {}
    for ds, entity_groups in data.items():
        ds_renames = renames.get(ds)
        if not ds_renames:
            out[ds] = entity_groups
            continue
        if not isinstance(entity_groups, dict):
            raise ValueError(
                f"REMAP {side} rename: malformed update for dataset '{ds}'; "
                f"expected dict of entity groups, got {type(entity_groups).__name__}"
            )
        out[ds] = {}
        for eg, attrs in entity_groups.items():
            eg_renames = ds_renames.get(eg)
            if not eg_renames:
                out[ds][eg] = attrs
                continue
            if not isinstance(attrs, dict):
                raise ValueError(
                    f"REMAP {side} rename: malformed update at '{ds}/{eg}'; "
                    f"expected dict of attributes, got {type(attrs).__name__}"
                )
            out[ds][eg] = {eg_renames.get(name, name): value for name, value in attrs.items()}
    return out


def _merge_rename_dict(
    existing: t.Dict[str, t.Dict[str, t.Dict[str, str]]],
    incoming: t.Mapping[str, t.Mapping[str, t.Mapping[str, str]]],
) -> t.Dict[str, t.Dict[str, t.Dict[str, str]]]:
    """Deep-merge an incoming REMAP rename section into the connector's existing one."""
    merged = copy.deepcopy(existing)
    for ds, entity_groups in incoming.items():
        ds_dest = merged.setdefault(ds, {})
        for eg, mapping in entity_groups.items():
            ds_dest.setdefault(eg, {}).update(mapping)
    return merged


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
