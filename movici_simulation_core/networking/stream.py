import dataclasses
import logging
import typing as t

import zmq

from ..exceptions import InvalidMessage, StreamDone
from ..messages import Message, ModelMessage, MultipartMessage, dump_message, load_message

T = t.TypeVar("T")


@dataclasses.dataclass
class BaseSocket(t.Generic[T]):
    socket: zmq.Socket

    def send(self, payload: T):
        raise NotImplementedError

    def recv(self) -> T:
        raise NotImplementedError


def get_message_socket(socket_type: int, context=None, ident: t.Optional[bytes] = None, **kwargs):
    try:
        adapter: t.Callable[[zmq.Socket], MessageSocket] = {
            zmq.REQ: MessageReqSocket,
            zmq.ROUTER: MessageRouterSocket,
            zmq.DEALER: MessageDealerSocket,
        }[socket_type]
    except KeyError:
        raise TypeError("Only support REQ, ROUTER and DEALER sockets") from None
    context = context or zmq.Context.instance()
    socket = context.socket(socket_type, **kwargs)
    if ident is not None:
        socket.set(zmq.IDENTITY, ident)
    return adapter(socket)


class MessageSocket(BaseSocket[T]):
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

    def close(self, linger: int = -1):
        return self.socket.close(linger)


class MessageRouterSocket(MessageSocket[ModelMessage]):
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


class MessageReqSocket(MessageSocket[Message]):
    def _serialize(self, payload: Message) -> MultipartMessage:
        return dump_message(payload)

    def _deserialize(self, payload: MultipartMessage) -> Message:
        return self.parse_bytes(payload)


class MessageDealerSocket(MessageSocket[Message]):
    def _serialize(self, payload: Message) -> MultipartMessage:
        return [b"", *dump_message(payload)]

    def _deserialize(self, payload: MultipartMessage) -> Message:
        _, *content = payload
        return self.parse_bytes(content)


class Stream(t.Generic[T]):
    def __init__(self, socket: BaseSocket[T], logger: logging.Logger = None):
        self.handler = None
        self.socket = socket
        self.logger = logger

    def set_handler(self, handler: t.Callable[[T], None]) -> None:
        self.handler = handler

    def _log(self, level: t.Union[int, str], msg, **kwargs):
        if self.logger is not None:
            if isinstance(level, int):
                self.logger.log(level, msg, **kwargs)
            else:
                getattr(self.logger, level.lower())(msg, **kwargs)

    def run(self):
        while True:
            try:
                received = self.recv()
                self._log("debug", f"Stream received: {received}")
            except InvalidMessage as e:
                self._log("warning", str(e))
                continue
            if self.handler:
                try:
                    self.handler(received)
                except StreamDone:
                    return

    def recv(self) -> T:
        return self.socket.recv()

    def send(self, payload: T):
        self._log("debug", f"Sending: {payload}")
        rv = self.socket.send(payload)
        return rv
