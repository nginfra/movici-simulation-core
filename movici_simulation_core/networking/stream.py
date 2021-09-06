import dataclasses
import logging
import typing as t

import zmq

from .messages import Message, ModelMessage, load_message, dump_message, MultipartMessage
from ..exceptions import InvalidMessage

T = t.TypeVar("T")


@dataclasses.dataclass
class SocketAdapter(t.Generic[T]):
    socket: zmq.Socket

    def send(self, payload: T):
        raise NotImplementedError

    def recv(self) -> T:
        raise NotImplementedError


def get_message_socket(socket_type: int, context=None, **kwargs):
    try:
        adapter: t.Callable[[zmq.Socket], MessageSocketAdapter] = {
            zmq.REQ: MessageReqSocketAdapter,
            zmq.ROUTER: MessageRouterSocketAdapter,
            zmq.DEALER: MessageDealerSocketAdapter,
        }[socket_type]
    except KeyError:
        raise TypeError("Only support REQ, ROUTER and DEALER sockets") from None
    context = context or zmq.Context.instance()
    socket = context.socket(socket_type, **kwargs)
    return adapter(socket)


class MessageSocketAdapter(SocketAdapter[T]):
    def send(self, payload: T):
        """serialize identifier and message into MultipartMessage"""
        return self.socket.send_multipart(self._serialize(payload))

    def recv(self) -> T:
        payload = self.socket.recv_multipart()
        return self._deserialize(payload)

    @staticmethod
    def parse_bytes(payload):
        try:
            msg_type, *content = payload
            message = load_message(msg_type, *content)
        except (KeyError, AttributeError, TypeError, ValueError):
            raise InvalidMessage(f"Invalid message '{payload}'")
        return message

    def _serialize(self, payload: T) -> MultipartMessage:
        raise NotImplementedError

    def _deserialize(self, payload: MultipartMessage) -> T:
        raise NotImplementedError

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return self.socket.__exit__(exc_type, exc_val, exc_tb)

    def connect(self, addr: str):
        return self.socket.connect(addr)

    def bind(self, addr: str):
        return self.socket.bind(addr)


class MessageRouterSocketAdapter(MessageSocketAdapter[ModelMessage]):
    def make_send(self, identifier: str):
        """create a send function that a can be used to send a message to a specific client
        connected to the ZMQ Router
        """

        def send(message: Message):
            return self.send((identifier, message))

        return send

    def _serialize(self, payload: ModelMessage) -> MultipartMessage:
        ident, message = payload
        return [ident.encode(), b"", *dump_message(message)]

    def _deserialize(self, payload: MultipartMessage) -> ModelMessage:
        ident, _, *content = payload
        return ident.decode(), self.parse_bytes(content)


class MessageReqSocketAdapter(MessageSocketAdapter[Message]):
    def _serialize(self, payload: Message) -> MultipartMessage:
        return dump_message(payload)

    def _deserialize(self, payload: MultipartMessage) -> Message:
        return self.parse_bytes(payload)


class MessageDealerSocketAdapter(MessageSocketAdapter[Message]):
    def _serialize(self, payload: Message) -> MultipartMessage:
        return [b"", *dump_message(payload)]

    def _deserialize(self, payload: MultipartMessage) -> Message:
        _, *content = payload
        return self.parse_bytes(content)


class Stream(t.Generic[T]):
    def __init__(self, socket: SocketAdapter[T], logger: logging.Logger = None):
        self.handler = None
        self.socket = socket
        self.logger = logger

    def set_handler(self, handler: t.Callable[[T], None]) -> None:
        self.handler = handler

    def run(self):
        while True:
            try:
                received = self.recv()
            except InvalidMessage as e:
                if self.logger is not None:
                    self.logger.warning(str(e))
                continue
            if self.handler:
                self.handler(received)

    def recv(self) -> T:
        return self.socket.recv()

    def send(self, payload: T):
        return self.socket.send(payload)
