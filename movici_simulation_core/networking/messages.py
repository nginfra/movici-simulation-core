from __future__ import annotations

import dataclasses
import json
import typing as t
from pathlib import Path


@dataclasses.dataclass
class Message:
    @classmethod
    def from_bytes(cls, raw_message: MultipartMessage) -> Message:
        dict_ = json.loads(raw_message[0])
        return cls.from_dict(dict_)

    def to_bytes(self) -> MultipartMessage:
        return [json.dumps(dataclasses.asdict(self)).encode()]

    @classmethod
    def from_dict(cls, dict_: dict):
        return cls(**dict_)


@dataclasses.dataclass
class RegistrationMessage(Message):
    pub: t.Optional[dict]
    sub: t.Optional[dict]


class BaseUpdateMessage:
    key: t.Optional[str]
    address: t.Optional[str]
    origin: t.Optional[str]

    def __post_init__(self):
        if (self.key is None) ^ (self.address is None):
            raise ValueError("'key' and 'address' must either both be filled or both be None ")

    @property
    def has_data(self):
        return self.key is not None and self.address is not None


@dataclasses.dataclass
class UpdateMessage(Message, BaseUpdateMessage):
    timestamp: int
    key: t.Optional[str] = None
    address: t.Optional[str] = None
    origin: t.Optional[str] = None


@dataclasses.dataclass
class UpdateSeriesMessage(Message):
    updates: t.List[UpdateMessage]

    @property
    def timestamp(self):
        if not self.updates:
            return None
        return max(upd.timestamp for upd in self.updates)

    @classmethod
    def from_bytes(cls, raw_message: MultipartMessage) -> Message:
        dict_ = {"updates": [json.loads(raw) for raw in raw_message]}
        return cls.from_dict(dict_)

    def to_bytes(self) -> MultipartMessage:
        return [upd.to_bytes()[0] for upd in self.updates]

    @classmethod
    def from_dict(cls, dict_: dict):
        if updates := dict_.get("updates"):
            dict_["updates"] = [UpdateMessage(**upd) for upd in updates]
        return cls(**dict_)


@dataclasses.dataclass
class PathMessage(Message):
    path: t.Optional[Path]

    @classmethod
    def from_bytes(cls, raw_message: MultipartMessage) -> Message:
        dict_ = json.loads(raw_message[0])
        path = dict_["path"]
        dict_["path"] = Path(path) if path is not None else None
        return cls(**dict_)

    def to_bytes(self) -> MultipartMessage:
        dict_ = dataclasses.asdict(self)
        path = dict_["path"]
        dict_["path"] = str(path) if path is not None else None
        return [json.dumps(dict_).encode()]


@dataclasses.dataclass
class ResultMessage(Message, BaseUpdateMessage):
    """Response to an UpdateMessage"""

    key: t.Optional[str] = None
    address: t.Optional[str] = None
    next_time: t.Optional[int] = None
    origin: t.Optional[str] = None


@dataclasses.dataclass
class NewTimeMessage(Message):
    timestamp: int


@dataclasses.dataclass
class AcknowledgeMessage(Message):
    """Response to an NewTimeMessage or QuitMessage"""

    pass


@dataclasses.dataclass
class QuitMessage(Message):
    pass


@dataclasses.dataclass
class GetDataMessage(Message):
    key: str
    mask: t.Optional[dict] = None


@dataclasses.dataclass
class PutDataMessage(Message):
    key: str
    data: bytes = dataclasses.field(repr=False)
    size: int = dataclasses.field(init=False)

    def __post_init__(self):
        self.size = len(self.data)

    @classmethod
    def from_bytes(cls, raw_message: MultipartMessage) -> Message:
        key, data = raw_message
        return PutDataMessage(key.decode(), data)

    def to_bytes(self) -> MultipartMessage:
        return [self.key.encode(), self.data]


@dataclasses.dataclass
class ClearDataMessage(Message):
    prefix: str


@dataclasses.dataclass
class DataMessage(Message):
    data: bytes = dataclasses.field(repr=False)
    size: int = dataclasses.field(init=False)

    def __post_init__(self):
        self.size = len(self.data)

    @classmethod
    def from_bytes(cls, raw_message: MultipartMessage) -> Message:
        return DataMessage(raw_message[0])

    def to_bytes(self) -> MultipartMessage:
        return [self.data]


@dataclasses.dataclass
class ErrorMessage(Message):
    error: t.Optional[str] = None


MESSAGE_TYPES = {
    b"READY": RegistrationMessage,
    b"UPDATE": UpdateMessage,
    b"UPDATE_SERIES": UpdateSeriesMessage,
    b"RESULT": ResultMessage,
    b"END": QuitMessage,
    b"NEW_TIME": NewTimeMessage,
    b"ACK": AcknowledgeMessage,
    b"GET": GetDataMessage,
    b"PUT": PutDataMessage,
    b"CLEAR": ClearDataMessage,
    b"DATA": DataMessage,
    b"PATH": PathMessage,
    b"ERROR": ErrorMessage,
}

MESSAGE_IDENTIFIERS = {v: k for k, v in MESSAGE_TYPES.items()}


def load_message(msg_type: bytes, *payload: bytes) -> Message:
    cls = MESSAGE_TYPES[msg_type]
    return cls.from_bytes(payload)


def dump_message(message: Message) -> TypedMultipartMessage:
    return [MESSAGE_IDENTIFIERS[type(message)], *message.to_bytes()]


TypedMultipartMessage = MultipartMessage = t.Sequence[bytes]
ModelMessage = t.Tuple[str, Message]
